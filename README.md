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
   - clustering comparison
   - anomaly-model comparison
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
- `grid_clusters_gaussian_mixture.csv`
- `cluster_profiles_gaussian_mixture.json`
- `district_cluster_mix_gaussian_mixture.csv`
- `district_anomalies_isolation_forest.csv`
- `district_anomalies_local_outlier_factor.csv`
- `district_anomaly_explanations_isolation_forest.json`
- `district_anomaly_explanations_local_outlier_factor.json`
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

It currently compares:
- `KMeans`
- `GaussianMixture`

### Anomaly detection

The anomaly layer is framed as **district-level socio-spatial mismatch**.

It combines:
- district socioeconomic indicators
- district environmental indicators
- aggregated grid features
- district typology composition shares

It currently compares:
- `IsolationForest`
- `LocalOutlierFactor`

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

### 1. Clone the repository

```bash
git clone <repo-url>
cd urban-workflow-implementation
```

### 2. Check whether Git LFS is available

This repository requires Git LFS for tracked raw files such as `.gpkg`, `.tif`, and `.xlsx`.

Check whether Git LFS is already installed:

```bash
git lfs version
```

If that command fails, install Git LFS first.

Common installation options:
- macOS with Homebrew: `brew install git-lfs`
- Windows with Winget: `winget install GitHub.GitLFS`
- Linux and other systems: follow the official instructions at `https://git-lfs.com`

If you cannot install Git LFS on the machine, the workflow will not have access to required tracked raw data files.

### 3. Initialise Git LFS and fetch the tracked data

Once Git LFS is installed, run:

```bash
git lfs install
git lfs pull
```

Important:
- Do not use GitHub "Download ZIP" for a reproducible setup. ZIP downloads can contain Git LFS pointer files instead of the real raw data.
- If `data/raw/*.gpkg` opens as a short text file starting with `version https://git-lfs.github.com/spec/v1`, the LFS objects were not fetched yet.

### 4. Create and activate a virtual environment

Example:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

### 6. Run the collection + ML pipeline

```bash
python main.py
```

This will:
- run source collection
- show a human review checkpoint
- then run feature engineering, clustering, anomaly detection, and evaluation

If required Git LFS data files are still unresolved, the collection step will now stop with a clear error message telling you to run `git lfs pull`.

### 7. Run the dashboard

```bash
python app.py
```

## Git LFS troubleshooting

If a raw source is unexpectedly skipped or collection fails on another machine:
- verify Git LFS is installed: `git lfs version`
- from the repository root, run: `git lfs pull`
- check tracked files: `git lfs ls-files`
- if `git lfs` is not found, install Git LFS first via your platform package manager or `https://git-lfs.com`
- avoid copying the repository via GitHub ZIP download if you need the raw data files

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
