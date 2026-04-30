# Urban Data Workflow MVP

This repository contains a small **LangGraph-based urban data workflow** for collecting, harmonising, profiling, and interpreting heterogeneous urban datasets. It is designed as a **human-in-the-loop, inspectable prototype**: data can be collected from local files and bounded manifest-declared remote sources, processed step by step, and then translated into a bounded AI-assisted interpretation summary.

## What the workflow does

The workflow runs in five stages:

1. **Collect sources** from `data/raw`
2. **Pause for human review** of the collected sources
3. **Process the data** through harmonisation, profiling, compatibility checking, and indicator generation
4. **Pause for human review** before interpretation
5. **Generate an interpretation summary** using a structured LLM step

The interpretation step is intentionally bounded. It does **not** make planning decisions. It creates a structured draft and renders it into a short summary that is meant to support human review.

## Repository structure

```text
project-root/
├── data/
│   ├── fetched/
│   ├── raw/
│   └── source_manifest.json
├── outputs/
│   └── reports/
├── src/
│   ├── collection.py
│   ├── harmonise.py
│   ├── profile.py
│   ├── compatibility.py
│   ├── indicators.py
│   ├── interpretation.py
│   └── schemas.py
├── main.py
└── .env
```

## Input data

Supported local input formats:

- `.csv`
- `.gpkg`

Place your source files in:

```text
data/raw/
```

The workflow automatically scans that folder and loads all supported files.

Optional bounded remote sources can be declared in:

```text
data/source_manifest.json
```

Supported manifest acquisition modes:

- `local_file`
- `remote_file`
- `api`

Supported manifest formats:

- `csv`
- `geopackage`
- `json` for tabular API-style responses, including CKAN-style `result.records`

All remote sources are cached locally in:

```text
data/fetched/
```

This keeps the collection step inspectable and reproducible instead of depending on hidden live fetches during later processing.

## Outputs

Running the workflow creates these files in:

```text
outputs/reports/
```

Generated outputs:

- `collection_report.json` — source acquisition, provenance, and collection-time warnings
- `source_profiles.json` — basic profile for each processed source
- `compatibility_report.json` — simple compatibility assessment across sources
- `interpretation_summary.md` — bounded AI-assisted interpretation summary

## Setup

### 1. Create and activate a virtual environment

Example:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

### 2. Install the required packages

This repository includes a `requirements.txt` file with all required dependencies.

Run:

```bash
pip install -r requirements.txt
```

### 3. Add your Groq API key

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_key_here
```

This is required for the interpretation step.

## How to run the workflow

From the project root, run:

```bash
python main.py
```

You will be asked to confirm two checkpoints:

1. after source collection
2. before interpretation

Reply with `y` or `n`.

- If you stop after collection, the workflow ends there.
- If you continue, the workflow processes the sources and generates outputs.
- If you approve the second checkpoint, it also generates the interpretation summary.

## Step-by-step logic

### 1. Collection

`collection.py` scans `data/raw`, loads optional manifest-declared sources, caches remote fetches to `data/fetched`, and creates a structured `CollectedSource` object for each dataset. Collection metadata includes provenance, acquisition mode, compatibility hints, and explicit warnings.

### 2. Harmonisation

`harmonise.py` applies lightweight cleaning:

- standardises column names
- removes fully empty rows
- updates source metadata

### 3. Profiling

`profile.py` creates JSON-friendly source profiles with basic metadata, missing values, and source information.

### 4. Compatibility check

`compatibility.py` compares the available sources and reports whether they can be directly integrated. In the current MVP, this is mainly used to highlight limitations and suggest next steps.

### 5. Indicator generation

`indicators.py` creates simple source-specific indicators.

Current logic:

- tabular transport data → transport mode summary
- geospatial land-use data → land-use area summary

### 6. Interpretation

`interpretation.py` builds a compact interpretation context from the processed outputs, sends it to the LLM as a structured task, validates the result with Pydantic, and renders it into markdown.

## Workflow design

The workflow is orchestrated in `main.py` with **LangGraph** and uses a shared **Pydantic state model** from `schemas.py`.

This keeps the MVP explicit and inspectable:

- workflow steps are separate nodes
- human review points remain in the loop
- interpretation is structured and validated
- outputs are saved as files for inspection

## Current limitations

This repository is intentionally small in scope.

- Remote collection is bounded to manifest-declared sources rather than open-ended autonomous web discovery
- It currently supports CSV, GeoPackage, and tabular JSON collection paths
- Indicator generation is source-specific and limited to the current example datasets
- The interpretation step is assistive, not autonomous
