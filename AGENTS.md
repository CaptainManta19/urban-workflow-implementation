# AGENTS.md

## Project Overview

This repository implements a transparent urban data workflow for Madrid:

- source collection with provenance tracking
- human review checkpoint after collection
- feature engineering at grid and district levels
- unsupervised ML (KMeans clustering + IsolationForest anomaly detection)
- dashboard-based inspection in `app.py`

Primary entry points:

- `main.py`: collection flow + human approval step + ML pipeline
- `run_ml_pipeline.py`: feature engineering, modeling, and evaluation only
- `app.py`: interactive dashboard

## Approval-First Agent Policy (Required)

The agent must **never make code changes autonomously**.

Before editing, creating, deleting, or renaming any file, the agent must:

1. Explain the proposed change briefly.
2. Ask for explicit user approval.
3. Wait for a clear confirmation.

Allowed without approval:

- read-only exploration (reading files, searching code, explaining behavior)
- proposing plans or patch previews in chat

Not allowed without approval:

- writing code
- changing configuration
- installing dependencies
- running destructive commands

## Build and Run Commands

Set up environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run full collection + ML workflow:

```bash
python main.py
```

Run ML workflow only:

```bash
python run_ml_pipeline.py
```

Run dashboard:

```bash
python app.py
```

## Code Style Guidelines

- Use Python type hints for new/changed functions.
- Follow existing style: small focused functions, dataclasses for structured artifacts, readable naming.
- Keep transformations transparent and auditable; prefer explicit intermediate variables over dense one-liners.
- Preserve compatibility patterns already used in repo (example: graceful fallback branches for library version differences).
- Do not introduce broad architectural changes unless explicitly requested.

## Testing and Validation Instructions

There is currently no dedicated `tests/` suite in this repository.

For any approved code change, run lightweight validation relevant to the changed area:

1. Syntax/import check:

```bash
python -m py_compile main.py run_ml_pipeline.py app.py
```

2. If pipeline code changed, run:

```bash
python run_ml_pipeline.py
```

3. If collection flow changed, run:

```bash
python main.py
```

4. If dashboard code changed, run:

```bash
python app.py
```

When reporting results, mention what was run and what was not run.

## Security and Data-Safety Considerations

- Treat all external/remote data sources as untrusted input; validate schema and required fields before downstream use.
- Avoid hardcoding secrets or tokens; use environment variables for credentials.
- Do not commit sensitive local artifacts (credentials, private datasets, `.env` files).
- Preserve provenance outputs and warnings so data lineage remains inspectable.
- ML outputs are exploratory analytical signals, not automated planning decisions; avoid overstating certainty in generated text/UI.
