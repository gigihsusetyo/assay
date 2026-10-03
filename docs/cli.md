# Assay CLI Reference

The Assay CLI manages datasets, runs, baselines, and evaluation gates. All commands are run from the terminal after activating the virtual environment.

## Global commands

### `assay version`

Show the Assay version.

```bash
assay version
```

### `assay health`

Check if the Assay API is reachable. Not implemented yet.

```bash
assay health
```

---

## Dataset commands

Datasets are collections of questions with expected answers and contexts.

### `assay dataset create`

Create a new dataset.

```bash
assay dataset create <name> [--description "..."]
```

**Arguments:**
- `name` — Dataset name. Must be unique.

**Options:**
- `--description`, `-d` — Optional description.

**Example:**

```bash
assay dataset create support-faq --description "Customer support FAQ"
```

### `assay dataset list`

List all datasets.

```bash
assay dataset list
```

### `assay dataset show`

Show dataset details, including the number of questions.

```bash
assay dataset show <dataset_id>
```

**Arguments:**
- `dataset_id` — Dataset ID.

**Example:**

```bash
assay dataset show 1
```

### `assay dataset add-question`

Add a question to a dataset.

```bash
assay dataset add-question <dataset_id> \
  --question "..." \
  [--answer "..."] \
  [--context "..."]
```

**Arguments:**
- `dataset_id` — Dataset ID.

**Options:**
- `--question`, `-q` — Question text. Required.
- `--answer`, `-a` — Expected answer. Optional.
- `--context`, `-c` — Expected context. Optional.

**Example:**

```bash
assay dataset add-question 1 \
  --question "How do I reset my password?" \
  --answer "Go to settings and click reset." \
  --context "You can reset your password in settings."
```

### `assay dataset import`

Import a dataset from a JSON file.

```bash
assay dataset import <file_path> [--name "..."] [--description "..."]
```

**Arguments:**
- `file_path` — Path to JSON file.

**Options:**
- `--name`, `-n` — Override dataset name from JSON.
- `--description`, `-d` — Override description from JSON.

**JSON format:**

```json
{
  "name": "dataset-name",
  "description": "Optional description",
  "version": "1.0.0",
  "questions": [
    {
      "question": "...",
      "expected_answer": "...",
      "expected_context": "..."
    }
  ]
}
```

**Example:**

```bash
assay dataset import examples/datasets/indonesian-legal-rag.json
```

### `assay dataset delete`

Delete a dataset and all its questions.

```bash
assay dataset delete <dataset_id> [--yes]
```

**Arguments:**
- `dataset_id` — Dataset ID.

**Options:**
- `--yes`, `-y` — Skip confirmation.

---

## Run commands

Runs are evaluation sessions. Each run points at a RAG endpoint and a dataset.

### `assay run create`

Create a new run.

```bash
assay run create --dataset <id> --name <name> --target <url>
```

**Options:**
- `--dataset`, `-d` — Dataset ID. Required.
- `--name`, `-n` — Run name. Required.
- `--target`, `-t` — Target RAG endpoint URL. Required.

**Example:**

```bash
assay run create --dataset 1 --name run-001 --target http://localhost:9000/query
```

### `assay run list`

List all runs, optionally filtered by dataset.

```bash
assay run list [--dataset <id>]
```

**Options:**
- `--dataset`, `-d` — Filter by dataset ID.

### `assay run show`

Show run details.

```bash
assay run show <run_id>
```

### `assay run execute`

Execute a run: call the target for each question and store results.

```bash
assay run execute <run_id> [--verbose] [--judge]
```

**Arguments:**
- `run_id` — Run ID.

**Options:**
- `--verbose`, `-v` — Show per-question output.
- `--judge` — Use LLM-as-judge for groundedness. Requires `ASSAY_JUDGE_*` environment variables.

**Example:**

```bash
assay run execute 1 --verbose
assay run execute 2 --verbose --judge
```

### `assay run delete`

Delete a run and all its results.

```bash
assay run delete <run_id> [--yes]
```

---

## Baseline commands

Baselines are pinned runs used as reference for comparison.

### `assay baseline create`

Create a baseline from a completed run.

```bash
assay baseline create --name <name> --run <run_id> [--description "..."]
```

**Options:**
- `--name`, `-n` — Baseline name. Required.
- `--run`, `-r` — Run ID to pin. Required.
- `--description`, `-d` — Optional description.

**Example:**

```bash
assay baseline create --name baseline-v1 --run 1 --description "First baseline"
```

### `assay baseline list`

List all baselines.

```bash
assay baseline list
```

### `assay baseline delete`

Delete a baseline.

```bash
assay baseline delete <baseline_id> [--yes]
```

---

## Gate command

The gate command compares a run against a baseline and fails if quality regresses.

### `assay gate`

Compare a run against a baseline and fail if quality regresses.

```bash
assay gate --baseline <name> --run <id> --policy <path> [--failures <n>] [--format <fmt>]
```

**Options:**
- `--baseline`, `-b` — Baseline name. Required.
- `--run`, `-r` — Current run ID. Required.
- `--policy`, `-p` — Policy file path. Default: `examples/policy.yaml`.
- `--failures`, `-f` — Number of worst failures to show. Default: 5.
- `--format`, `-o` — Output format: `text` (default), `json`, `junit`.

**Exit codes:**
- `0` — Passed.
- `1` — Failed (quality regressed).
- `2` — Error (invalid input, missing baseline, etc).

**Text output (default):**

```bash
assay gate --baseline baseline-v1 --run 2 --policy examples/policy.yaml
```

Output:

```
Assay Report
Baseline: baseline-v1 (run 1)
Current:  run 2

┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━┓
┃ Metric         ┃ Baseline ┃ Current ┃ Δ abs  ┃ Δ %   ┃ Status ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━┩
│ groundedness   │ 0.800    │ 0.734   │ -0.066 │ -8.2% │ FAIL   │
│ context_recall │ 0.790    │ 0.770   │ -0.020 │ -2.5% │ PASS   │
│ p95_latency_ms │ 1420.000 │ 1180.000│ -240.0 │ -16.9%│ PASS   │
│ avg_cost_usd   │ 0.008    │ 0.003   │ -0.005 │ -62.5%│ PASS   │
└────────────────┴──────────┴─────────┴────────┴───────┴────────┘

Verdict: FAILED
  - groundedness dropped by 8.2% (threshold 5.0% relative)

Worst failures:
  Q1 "How do I configure SSO with Okta?": 0.81 -> 0.42 (delta -0.39)
  ...
```

**JSON output (for machine parsing):**

```bash
assay gate --baseline baseline-v1 --run 2 --policy examples/policy.yaml --format json
```

Output:

```json
{
  "baseline_name": "baseline-v1",
  "baseline_run_id": 1,
  "current_run_id": 2,
  "passed": false,
  "reasons": ["groundedness dropped by 8.2% (threshold 5.0% relative)"],
  "metrics": [
    {
      "name": "groundedness",
      "baseline": 0.8,
      "current": 0.734,
      "delta_absolute": -0.066,
      "delta_percent": -8.2,
      "threshold_value": 5.0,
      "threshold_type": "relative",
      "higher_is_better": true,
      "passed": false
    }
  ],
  "worst_failures": [...]
}
```

**JUnit output (for CI systems):**

```bash
assay gate --baseline baseline-v1 --run 2 --policy examples/policy.yaml --format junit
```

Output:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="assay-gate" tests="4" failures="1">
  <testcase name="groundedness" classname="assay">
    <failure message="groundedness regressed. Baseline=0.8, Current=0.734, 
      Delta=-0.0660 (-8.20%), Threshold=5.0 relative" />
  </testcase>
  ...
</testsuite>
```

The JUnit format is useful for CI systems that display test results. Each metric becomes a test case. Failed metrics become failures.

---

## Result commands

Results are per-question evaluation outputs.

### `assay result list`

List results for a run.

```bash
assay result list --run <run_id> [--limit <n>]
```

**Options:**
- `--run`, `-r` — Run ID. Required.
- `--limit`, `-l` — Maximum number of results. Default: 20.

**Example:**

```bash
assay result list --run 1
```

---

## Question commands

### `assay question list`

List questions in a dataset.

```bash
assay question list --dataset <dataset_id> [--limit <n>]
```

**Options:**
- `--dataset`, `-d` — Dataset ID. Required.
- `--limit`, `-l` — Maximum number of questions. Default: 20.

**Example:**

```bash
assay question list --dataset 1
```

---

## Typical workflow

```bash
# 1. Import a dataset
assay dataset import examples/datasets/indonesian-legal-rag.json

# 2. Create a run pointing at your RAG endpoint
assay run create --dataset 2 --name run-001 --target http://localhost:9000/query

# 3. Execute the run
assay run execute 1 --verbose

# 4. Pin it as a baseline
assay baseline create --name baseline-v1 --run 1

# 5. Make a change to your RAG system, create a new run
assay run create --dataset 2 --name run-002 --target http://localhost:9000/query

# 6. Execute the new run
assay run execute 2 --verbose

# 7. Compare against the baseline
assay gate --baseline baseline-v1 --run 2 --policy examples/policy.yaml

# 8. If it passes, exit code is 0. If it fails, exit code is 1.
```