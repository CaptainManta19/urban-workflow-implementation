# Madrid Urban Workflow

This repository contains a transparent urban data workflow for Madrid and a Dash dashboard for inspecting the resulting data and model outputs.

## What the project does

The workflow:

1. collects local and optional remote sources with provenance tracking
2. pauses for a human review checkpoint after collection
3. builds district-level and 250 m grid-level feature tables
4. runs KMeans clustering on grid features
5. runs IsolationForest anomaly detection on district features
6. writes outputs for inspection in the dashboard

The dashboard supports:

- district-level indicator inspection
- grid-based views for land use, building height, and mobility
- comparison between districts
- a pipeline mode that explains workflow stages and outputs

## Entry points

- `python main.py` runs the full workflow
- `python app.py` starts the dashboard

## Repository structure

```text
project-root/
├── app.py
├── main.py
├── backend/
│   ├── dashboard_data/
│   ├── features/
│   ├── models/
│   ├── schemas/
│   └── workflow/
├── frontend/
│   ├── assets/
│   ├── callbacks.py
│   ├── dashboard_app.py
│   ├── dashboard_logic.py
│   ├── layout.py
│   ├── maps.py
│   ├── panels.py
│   └── pipeline_view.py
├── data/
│   ├── fetched/
│   ├── raw/
│   └── source_catalog.json
├── notebooks/
│   └── combined_dataset.ipynb
└── outputs/
    ├── collection/
    └── ml/
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Input data

Supported local input formats:

- `.csv`
- `.gpkg`

Place local source files in:

```text
data/raw/
```

Optional bounded remote or local source declarations can be defined in:

```text
data/source_catalog.json
```

Supported source types include:

- local files
- remote files
- API responses

Fetched remote sources are cached in:

```text
data/fetched/
```

## Running the workflow

Run the full collection and ML workflow:

```bash
python main.py
```

The CLI is summary-first by default. After source collection, it asks whether to continue or inspect detailed collection output. Later modeling stages use the same concise-first pattern with optional detail views.

## Running the dashboard

Start the dashboard:

```bash
python app.py
```

## Main outputs

Collection outputs are written to:

```text
outputs/collection/
```

Key collection artifact:

- `source_collection_report.json`

ML outputs are written to:

```text
outputs/ml/
```

Key ML artifacts include:

- `grid_features.csv`
- `district_features.csv`
- `feature_definitions.json`
- `grid_clusters_kmeans.csv`
- `cluster_profiles_kmeans.json`
- `district_cluster_mix_kmeans.csv`
- `district_anomalies_isolation_forest.csv`
- `district_anomaly_explanations_isolation_forest.json`
- `model_evaluation_summary.md`

## Notes on the derived grid dataset

The research-derived 250 m grid dataset used in the dashboard and ML workflow is documented in:

```text
notebooks/combined_dataset.ipynb
```

It integrates land use, building height, public transport accessibility, rent, public housing, and district labels into one derived analytical dataset.

## Interpretation

The outputs in this repository are exploratory analytical signals. They should support inspection and discussion, not automated planning decisions.
