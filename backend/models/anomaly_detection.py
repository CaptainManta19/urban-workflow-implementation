from dataclasses import dataclass
from pathlib import Path
import ast

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest

from backend.features.engineering import OUTPUT_DIR
from backend.schemas.modeling import (
    AnomalyConfig,
    DistrictAnomalyRecord,
    ModelArtifactManifest,
)


DEFAULT_RANDOM_STATE = 42
DEFAULT_CONTAMINATION = 0.10
DEFAULT_N_ESTIMATORS = 300


@dataclass
class PreparedAnomalyData:
    merged_frame: pd.DataFrame
    feature_matrix: np.ndarray
    feature_columns: list[str]
    eligible_index: pd.Index
    scaled_feature_frame: pd.DataFrame


@dataclass
class AnomalyArtifacts:
    model_name: str
    scored_district_features: pd.DataFrame
    anomaly_records: list[DistrictAnomalyRecord]
    feature_columns: list[str]


def expand_cluster_shares(district_cluster_mix: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in district_cluster_mix.iterrows():
        flat_row = {
            "district_name": row["district_name"],
            "district_key": row["district_key"],
            "dominant_cluster_label": row.get("dominant_cluster_label"),
        }
        cluster_shares = row.get("cluster_shares", {}) or {}
        if isinstance(cluster_shares, str):
            cluster_shares = ast.literal_eval(cluster_shares)
        for cluster_label, share in cluster_shares.items():
            flat_row[f"cluster_share_{cluster_label}"] = float(share)
        rows.append(flat_row)
    return pd.DataFrame(rows)


def merge_district_typology_features(
    district_features: pd.DataFrame,
    district_cluster_mix: pd.DataFrame,
) -> pd.DataFrame:
    cluster_share_frame = expand_cluster_shares(district_cluster_mix)
    merged = district_features.merge(
        cluster_share_frame,
        on=["district_name", "district_key"],
        how="left",
    )

    cluster_share_columns = [
        column for column in merged.columns
        if column.startswith("cluster_share_cluster_")
    ]
    for column in cluster_share_columns:
        merged[column] = merged[column].fillna(0.0)

    return merged


def build_anomaly_feature_columns(
    merged_frame: pd.DataFrame,
    config: AnomalyConfig | None = None,
) -> list[str]:
    config = config or AnomalyConfig()
    feature_columns = list(config.feature_columns)
    cluster_share_columns = sorted(
        column for column in merged_frame.columns
        if column.startswith("cluster_share_cluster_")
    )
    feature_columns.extend(cluster_share_columns)
    return feature_columns


def prepare_anomaly_data(
    district_features: pd.DataFrame,
    district_cluster_mix: pd.DataFrame,
    config: AnomalyConfig | None = None,
) -> PreparedAnomalyData:
    merged_frame = merge_district_typology_features(
        district_features=district_features,
        district_cluster_mix=district_cluster_mix,
    )
    feature_columns = build_anomaly_feature_columns(merged_frame, config=config)

    eligible_mask = merged_frame[feature_columns].notna().any(axis=1)
    eligible_frame = merged_frame.loc[eligible_mask].copy()
    if eligible_frame.empty:
        raise ValueError("No eligible district rows are available for anomaly detection.")

    preprocessing = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    feature_matrix = preprocessing.fit_transform(eligible_frame[feature_columns])
    scaled_feature_frame = pd.DataFrame(
        feature_matrix,
        index=eligible_frame.index,
        columns=feature_columns,
    )

    return PreparedAnomalyData(
        merged_frame=merged_frame,
        feature_matrix=np.asarray(feature_matrix, dtype=float),
        feature_columns=feature_columns,
        eligible_index=eligible_frame.index,
        scaled_feature_frame=scaled_feature_frame,
    )


def rank_top_contributing_features(
    scaled_feature_row: pd.Series,
    limit: int = 3,
) -> list[str]:
    ranked = scaled_feature_row.abs().sort_values(ascending=False)
    return [str(column) for column in ranked.head(limit).index]


def build_interpretation_notes(
    scaled_feature_row: pd.Series,
    top_features: list[str],
) -> list[str]:
    notes = []
    for feature_name in top_features:
        value = scaled_feature_row[feature_name]
        direction = "higher" if value > 0 else "lower"
        notes.append(
            f"{feature_name} is unusually {direction} than the district average pattern."
        )
    return notes


def build_anomaly_records(
    scored_frame: pd.DataFrame,
    scaled_feature_frame: pd.DataFrame,
) -> list[DistrictAnomalyRecord]:
    records: list[DistrictAnomalyRecord] = []
    eligible_scored = scored_frame.loc[scaled_feature_frame.index]

    for row_index, row in eligible_scored.iterrows():
        top_features = rank_top_contributing_features(scaled_feature_frame.loc[row_index])
        interpretation_notes = build_interpretation_notes(
            scaled_feature_frame.loc[row_index],
            top_features=top_features,
        )
        records.append(
            DistrictAnomalyRecord(
                district_name=str(row["district_name"]),
                district_key=str(row["district_key"]),
                anomaly_score=float(row["anomaly_score"]),
                anomaly_flag=bool(row["anomaly_flag"]),
                top_contributing_features=top_features,
                interpretation_notes=interpretation_notes,
            )
        )

    return records


def fit_isolation_forest_anomaly(
    district_features: pd.DataFrame,
    district_cluster_mix: pd.DataFrame,
    config: AnomalyConfig | None = None,
    contamination: float = DEFAULT_CONTAMINATION,
    random_state: int = DEFAULT_RANDOM_STATE,
    n_estimators: int = DEFAULT_N_ESTIMATORS,
) -> AnomalyArtifacts:
    prepared = prepare_anomaly_data(
        district_features=district_features,
        district_cluster_mix=district_cluster_mix,
        config=config,
    )
    model = IsolationForest(
        contamination=contamination,
        random_state=random_state,
        n_estimators=n_estimators,
    )
    model.fit(prepared.feature_matrix)

    raw_scores = model.score_samples(prepared.feature_matrix)
    anomaly_scores = -raw_scores
    predictions = model.predict(prepared.feature_matrix)
    anomaly_flags = predictions == -1

    scored = prepared.merged_frame.copy()
    scored["anomaly_score"] = np.nan
    scored["anomaly_flag"] = None
    scored["anomaly_top_features"] = [[] for _ in range(len(scored))]

    scored.loc[prepared.eligible_index, "anomaly_score"] = anomaly_scores
    scored.loc[prepared.eligible_index, "anomaly_flag"] = anomaly_flags

    anomaly_records = build_anomaly_records(scored, prepared.scaled_feature_frame)
    top_feature_lookup = {
        record.district_key: record.top_contributing_features
        for record in anomaly_records
    }
    for row_index, row in scored.iterrows():
        district_key = row["district_key"]
        scored.at[row_index, "anomaly_top_features"] = top_feature_lookup.get(district_key, [])

    return AnomalyArtifacts(
        model_name="isolation_forest",
        scored_district_features=scored,
        anomaly_records=anomaly_records,
        feature_columns=prepared.feature_columns,
    )


def save_anomaly_artifacts(
    artifacts: AnomalyArtifacts,
    output_dir: Path = OUTPUT_DIR,
) -> ModelArtifactManifest:
    output_dir.mkdir(parents=True, exist_ok=True)

    district_anomaly_path = output_dir / f"district_anomalies_{artifacts.model_name}.csv"
    district_explanation_path = output_dir / f"district_anomaly_explanations_{artifacts.model_name}.json"

    artifacts.scored_district_features.to_csv(district_anomaly_path, index=False)
    pd.DataFrame([record.model_dump() for record in artifacts.anomaly_records]).to_json(
        district_explanation_path,
        orient="records",
        indent=2,
    )

    return ModelArtifactManifest(
        district_anomaly_path=str(district_anomaly_path),
    )
