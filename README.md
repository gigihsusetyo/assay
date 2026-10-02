# Assay

**The release gate for RAG systems.**

Assay runs a dataset of questions against a RAG endpoint, compares the results to a pinned baseline, and fails the deployment if quality, latency, or cost regress beyond a defined threshold.

If you have ever changed an embedding model, updated a knowledge base, or swapped an LLM provider and wondered whether the system got better or worse, Assay is for you.

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
- Create runs pointing at a RAG endpoint.
- Execute runs: Assay calls the endpoint for each question and stores results.
- Compute groundedness and context recall (simple heuristics for now).
- Compare a run against a pinned baseline.
- Gate: fail with exit code 1 if quality regresses.

What is not done yet:

- LLM-as-judge metrics. Current metrics are token-overlap heuristics.
- Integration with Ragas or DeepEval.
- Docker and docker-compose for the full stack.
- GitHub Action for CI.
- Cloud deployment.
- Real Kubernetes.

---

## Quickstart

Assay runs on Python 3.11.

```bash
git clone https://github.com/gigihsusetyo/assay.git
cd assay
pip install -e ".[dev]"
```

Create a dataset:

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

Create a run pointing at your RAG endpoint:

```bash
assay run create --dataset 1 --name run-001 --target http://localhost:9000/query
```

Execute the run:

```bash
assay run execute 1 --verbose
```

Compare against a baseline:

```bash
assay gate --baseline baseline-v1 --run 1 --policy examples/policy.yaml
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

These are not LLM-as-judge metrics. They are fast, deterministic, and good enough to catch obvious regressions. LLM-as-judge metrics will be added later, along with judge validation against human labels.

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

SQLite is the default for local development. PostgreSQL is the target for production.

---

## Roadmap

**MVP (current):** Core evaluation, CLI, simple metrics, comparison, gate. SQLite for development.

**Phase 2:** Go execution plane for high-concurrency evaluation. Benchmark against Python asyncio to justify it.

**Phase 3:** Real Kubernetes. Deploy to Oracle Cloud Free Tier with k3s. Infrastructure as code.

**Phase 4:** Observability with OpenTelemetry and Prometheus. Regression alerts. PR comments.

A hosted, multi-tenant version is on the longer-term roadmap. The core stays open source.

---

## Development

Assay is developed in GitHub Codespaces. The devcontainer is configured for Python 3.11 with Docker-in-Docker.

Run tests:

```bash
pytest tests/ -v
```

Run the API:

```bash
uvicorn assay.main:app --host 0.0.0.0 --port 8000
```

Run the mock RAG for testing:

```bash
uvicorn examples.mock_rag.app:app --host 0.0.0.0 --port 9000
```

---

## License

Apache 2.0. See [LICENSE](LICENSE).

---

## Links

- Domain: [assay.web.id](https://assay.web.id)
- GitHub: [github.com/gigihsusetyo/assay](https://github.com/gigihsusetyo/assay)
---

## Testing the Gate

This section exists to test the Assay Gate GitHub Action on a pull request.
It will be removed after the test.
