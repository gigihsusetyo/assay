# Assay

**CI gate for RAG quality regressions.**

Run your production-like RAG against a golden dataset, compare it with a pinned baseline, and fail the build when quality, latency, or cost regress beyond your policy.

If you have ever changed an embedding model, updated a knowledge base, swapped an LLM provider, or tuned chunking and wondered whether the system got better or worse, Assay is for you. It answers one question: did my latest change make things worse?

---

## The Problem

Every time you change something in a RAG system, you face the same question: did this make things better or worse?

Most teams answer this with manual spot checks. Test ten questions. Decide it looks fine. Deploy. Two days later, support tickets spike. The chatbot is giving wrong answers to technical questions. Rollback. The cost problem you were trying to solve is still there.

This is not a tooling problem. It is a decision problem. You need a way to know, before you deploy, whether the change is safe.

Assay is that way.

---

## What Assay Does

1. Takes a dataset of questions with expected answers and contexts.
2. Calls your RAG endpoint for each question.
3. Computes quality metrics (groundedness, context recall) and operational metrics (latency, cost).
4. Compares the results against a baseline.
5. Fails with a non-zero exit code if quality regresses beyond a threshold.

That last step is the point. Assay is not a dashboard. It is a gate.

---

## A Scenario

A SaaS company runs a support chatbot over its documentation. The team wants to swap the embedding model to cut costs.

Without Assay, they change the model in staging, test ten questions manually, and deploy. Two days later, support tickets spike by 40 percent. The chatbot is giving wrong answers to technical questions. They roll back in a panic.

With Assay, they have a golden dataset: 200 real questions with verified answers. They open a pull request that swaps the model. GitHub Actions runs Assay automatically. Assay calls the staging endpoint, compares against the baseline, and produces a report.

```
Assay Report: PR #247
Config: bge-m3 vs text-embedding-3-small

Groundedness        -8.2%   FAIL (threshold -5%)
Context Recall      -3.1%   PASS
P95 Latency         -18%    PASS (better)
Cost per query      -64%    PASS (better)

Verdict: FAILED
Reason: Groundedness dropped below threshold.
Worst failures (7 queries):
  "How do I configure SSO with Okta?"     (groundedness 0.42)
  "What is the rate limit for API v2?"    (groundedness 0.51)
```

The team sees that the new model struggles with exact-match technical terms. They add hybrid search to handle those cases. They rerun Assay. Groundedness improves to -2.1 percent. PASS. They deploy. Costs drop 64 percent. Quality holds.

The team avoided a production incident. They made a decision based on data, not feeling. They have a record of every change and its impact.

---

## What Assay Is Not

- Not a RAG framework. It does not build retrieval, chunking, or embedding pipelines.
- Not a metrics library. It integrates with existing ones like Ragas and DeepEval.
- Not an observability platform. Tracing and dashboards are on the roadmap, not in the MVP.
- Not a general LLM evaluation tool. RAG is the first workload.

Assay evaluates RAG systems. It does not become one.

---

## Status

Early development. The core pipeline works end to end, but the project is not ready for production use yet.

What works today:

- Create datasets and add questions via CLI or API.
- Import datasets from JSON files.
- Create runs pointing at a RAG endpoint.
- Execute runs: Assay calls the endpoint for each question and stores results.
- Compute groundedness and context recall with simple heuristics.
- Optionally use LLM-as-judge for groundedness (BYOK).
- Validate the judge against human labels (Cohen's kappa).
- Compare a run against a pinned baseline.
- Gate: fail with exit code 1 if quality regresses.

What is not done yet:

- Integration with Ragas or DeepEval.
- Cloud deployment.
- Real Kubernetes.
- Bias probes for judge validation.

---

## Quickstart

Assay runs on Python 3.11.

```bash
git clone https://github.com/gigihsusetyo/assay.git
cd assay
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Create a dataset manually:

```bash
assay dataset create support-faq --description "Customer support FAQ"
```

Add a question:

```bash
assay dataset add-question 1 \
  --question "How do I reset my password?" \
  --answer "Go to settings and click reset." \
  --context "You can reset your password in settings."
```

Or import a dataset from a JSON file:

```bash
assay dataset import examples/datasets/indonesian-legal-rag.json
```

The repo ships with a sample dataset of 10 questions from Indonesian legal regulations. It comes from [wahyyuht/skripsi-data](https://huggingface.co/datasets/wahyyuht/skripsi-data) on Hugging Face, under CC BY 4.0.

Create a run pointing at your RAG endpoint:

```bash
assay run create --dataset 2 --name run-001 --target http://localhost:9000/query
```

Execute the run:

```bash
assay run execute 1 --verbose
```

Pin the run as a baseline:

```bash
assay baseline create --name baseline-v1 --run 1 --description "First baseline"
```

List baselines:

```bash
assay baseline list
```

Compare a new run against the baseline:

```bash
assay gate --baseline baseline-v1 --run 2 --policy examples/policy.yaml
```

If the run passes, exit code is 0. If it fails, exit code is 1. If something is wrong with the input, exit code is 2.

---

## The Target Adapter Contract

Assay does not care what is inside your RAG system. It calls a standard HTTP endpoint and expects a standard response.

Request:

```json
{
  "question": "How do I configure SSO with Okta?",
  "dataset_id": "support-golden-v3",
  "run_id": "run_2026_09_29_001"
}
```

Response:

```json
{
  "answer": "To configure SSO with Okta...",
  "retrieved_contexts": [
    {"text": "...", "source": "docs/sso.md", "score": 0.87}
  ],
  "latency_ms": 1240,
  "cost_usd": 0.0032,
  "metadata": {"model": "gpt-4", "embedding": "text-embedding-3-small"}
}
```

Any RAG system that implements this contract can be evaluated.

---

## The Regression Policy

A policy is a YAML file that defines acceptable regression thresholds.

```yaml
version: 1
thresholds:
  groundedness: 5.0
  context_recall: 5.0
  p95_latency_ms: 20.0
  avg_cost_usd: 20.0
```

Numbers are percentages. For quality metrics, the threshold is the maximum allowed drop. For latency and cost, the threshold is the maximum allowed increase.

---

## Metrics

For the MVP, Assay uses simple heuristic metrics.

**Groundedness** measures how much of the answer is supported by the retrieved contexts. It is the fraction of answer tokens that appear in the contexts. Range 0.0 to 1.0.

**Context recall** measures how much of the expected context was retrieved. It is the fraction of expected context tokens that appear in retrieved contexts. Returns None if no expected context is provided.

These are regression signals, not correctness guarantees.

Token overlap catches obvious drift. It does not catch semantic errors. An answer that says "rate limit is 1000" when the context says "rate limit is 100" will score high on groundedness, because most tokens overlap. That is a real limitation.

For semantic correctness, use LLM-as-judge. Assay supports it via Bring Your Own Key (BYOK). See ADR-004 for details.

The point of these metrics is not to tell you whether your RAG is good. It is to tell you whether your latest change made it worse.

---

## Architecture

```
                    ┌───────────────────────┐
                    │      Assay CLI        │
                    │  assay run            │
                    │  assay compare        │
                    │  assay gate           │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Python FastAPI      │
                    │                       │
                    │  datasets             │
                    │  runs                 │
                    │  metrics              │
                    │  comparison           │
                    │  regression policy    │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   PostgreSQL / SQLite │
                    │                       │
                    │  datasets             │
                    │  runs                 │
                    │  results              │
                    │  baselines            │
                    └───────────────────────┘

Target adapters:
  Assay → HTTP RAG endpoint
```

SQLite is the default for local development. PostgreSQL is the target for production. Assay is tested with Supabase as a managed PostgreSQL provider.

---

## Roadmap

**Phase 1 — Trust (current):**
Golden datasets, baselines, regression policies, CLI, CI gate, JSON output, PR comments.

**Phase 2 — Quality and Scale:**
Ragas integration, LLM-as-judge with human calibration, failure analysis. Go execution plane for high-concurrency evaluation, benchmarked against Python asyncio. Parallel execution and caching.

**Phase 3 — Deployment and Observability:**
Kubernetes deployment with k3s. OpenTelemetry traces, historical regressions, alerts, dashboards.

A hosted, multi-tenant version is on the longer-term roadmap. The core stays open source.

## Development

Assay runs on Python 3.11. The recommended development setup:

1. Clone the repository.
2. Create a virtual environment: `python3.11 -m venv .venv`.
3. Activate it: `source .venv/bin/activate`.
4. Install dependencies: `pip install -e ".[dev]"`.
5. Create a `.env` file with your database URL. See `.env.example` for the format.
6. Run tests: `pytest tests/ -v`.

### Database

For local development, SQLite works out of the box. Set the default in `.env`:

```
ASSAY_DATABASE_URL=sqlite:///./assay.db
```

For production, PostgreSQL is the target. Assay is tested with [Supabase](https://supabase.com) as a managed PostgreSQL provider. Use the Session Pooler connection string, not the direct connection, because the direct connection is IPv6-only and may not work from all networks.

### Running the services

Run the API:

```bash
uvicorn assay.main:app --host 0.0.0.0 --port 8000
```

Run the mock RAG for testing:

```bash
python -m uvicorn examples.mock_rag.app:app --host 0.0.0.0 --port 9000
```

### Docker

A Dockerfile is included. To build:

```bash
docker build -t assay:dev .
```

Note: Docker Desktop 4.15.0 is the last version that runs on macOS Catalina. On newer systems, any recent Docker version works.

---

## License

Apache 2.0. See [LICENSE](LICENSE).

---

## Links

- Live demo: [assay-6pji.onrender.com](https://assay-6pji.onrender.com)
- API docs: [assay-6pji.onrender.com/docs](https://assay-6pji.onrender.com/docs)
- Domain: [assay.web.id](https://assay.web.id)
- GitHub: [github.com/gigihsusetyo/assay](https://github.com/gigihsusetyo/assay)

