# Madrid Urban Workflow Dashboard

This repository contains a transparent urban data workflow for **collecting**, **feature-engineering**, and **analyzing** heterogeneous datasets about Madrid, plus a Dash dashboard for inspecting the resulting evidence.

The current project architecture is centered on:
- bounded source collection with provenance
- explicit district- and grid-level feature tables
- interpretable unsupervised ML
- a dashboard that explains both data and pipeline stages

The repository no longer uses the earlier LangGraph/LLM interpretation workflow as its active architecture.

## What the workflow does

The current workflow runs in these stages:

1. **Collect sources** from `data/raw` and optional manifest-declared sources
2. **Pause for human review** of collected sources and provenance
3. **Build feature tables**
   - `grid_features`
   - `district_features`
4. **Run clustering**
   - urban form/access typology at 250m cell level
5. **Run anomaly detection**
   - district-level socio-spatial mismatch
6. **Generate evaluation outputs**
   - clustering evaluation
   - anomaly evaluation
7. **Inspect results in the dashboard**

## Repository structure

```text
project-root/
├── app.py
├── main.py
├── run_ml_pipeline.py
├── data/
│   ├── fetched/
│   ├── raw/
│   └── source_manifest.json
├── outputs/
│   ├── ml/
│   └── reports/
├── src/
│   ├── collection.py
│   ├── feature_engineering.py
│   ├── ml_schemas.py
│   ├── preprocessing.py
│   ├── dashboard_context.py
│   ├── schemas.py
│   └── modeling/
│       ├── clustering.py
│       ├── anomaly.py
│       └── evaluation.py
└── combined_dataset.ipynb
```

## Input data

Supported local input formats:
- `.csv`
- `.gpkg`

Place source files in:

```text
data/raw/
```

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

All remote sources are cached in:

```text
data/fetched/
```

## Main outputs

The ML pipeline writes outputs to:

```text
outputs/ml/
```

Current outputs include:
- `feature_table_specs.json`
- `grid_features.csv`
- `district_features.csv`
- `grid_clusters_kmeans.csv`
- `cluster_profiles_kmeans.json`
- `district_cluster_mix_kmeans.csv`
- `district_anomalies_isolation_forest.csv`
- `district_anomaly_explanations_isolation_forest.json`
- `model_evaluation_summary.md`

Collection outputs remain in:

```text
outputs/reports/
```

## Modeling design

### Clustering

The clustering layer is framed as **urban form/access typology**.

V1 clustering uses:
- simplified land use
- mean building height
- maximum building height
- public transport stop count

The current dashboard baseline keeps:
- `KMeans`

### Anomaly detection

The anomaly layer is framed as **district-level socio-spatial mismatch**.

It combines:
- district socioeconomic indicators
- district environmental indicators
- aggregated grid features
- district typology composition shares

The current exploratory baseline keeps:
- `IsolationForest`

## Dashboard

The dashboard lives in:

```text
app.py
```

It is intended to:
- show district-level and grid-level evidence
- surface provenance and caveats
- explain the pipeline in a dedicated pipeline mode
- later integrate clustering and anomaly outputs into the right sidebar and topic flow

## How to run

### 1. Create and activate a virtual environment

Example:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the collection + ML pipeline

```bash
python main.py
```

This will:
- run source collection
- show a human review checkpoint
- then run feature engineering, clustering, anomaly detection, and evaluation

### 4. Run the dashboard

```bash
python app.py
```

## Provenance of the cell-based dataset

The research-derived 250m grid dataset used in the dashboard and ML workflow is documented in:

```text
combined_dataset.ipynb
```

That notebook progressively integrates:
- Urban Atlas land use
- Urban Atlas building height
- OpenStreetMap-based public transport features
- district-level rent statistics
- district-level EMVS public housing
- district labels

This grid dataset is therefore a **derived integration product**, not a single direct source.

## Current focus

The current codebase is focused on:
- making transformations inspectable
- preserving provenance
- building defensible ML outputs
- integrating those outputs into the dashboard step by step

The ML outputs should be treated as exploratory analytical layers, not automated planning decisions.
