from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.feature_engineering import OUTPUT_DIR
from src.modeling.anomaly import (
    AnomalyArtifacts,
    fit_isolation_forest_anomaly,
)
from src.modeling.clustering import (
    ClusteringArtifacts,
    fit_kmeans_typology,
)


DEFAULT_K_RANGE = (3, 4, 5, 6, 7)
TINY_CLUSTER_SHARE_THRESHOLD = 0.01
SMALL_CLUSTER_SHARE_THRESHOLD = 0.05


@dataclass
class ClusteringEvaluationResult:
    summary_frame: pd.DataFrame
    warnings: list[str]


@dataclass
class AnomalyEvaluationResult:
    summary_frame: pd.DataFrame
    warnings: list[str]


def summarize_clustering_artifacts(artifacts: ClusteringArtifacts) -> dict:
    cluster_sizes = [profile.cell_count for profile in artifacts.cluster_profiles]
    cluster_shares = [profile.share_of_cells for profile in artifacts.cluster_profiles]
    smallest_share = min(cluster_shares) if cluster_shares else None
    largest_share = max(cluster_shares) if cluster_shares else None
    tiny_cluster_count = sum(share < TINY_CLUSTER_SHARE_THRESHOLD for share in cluster_shares)
    small_cluster_count = sum(share < SMALL_CLUSTER_SHARE_THRESHOLD for share in cluster_shares)

    return {
        "model_name": artifacts.model_name,
        "cluster_count": artifacts.cluster_count,
        "silhouette": artifacts.silhouette,
        "profile_count": len(artifacts.cluster_profiles),
        "min_cluster_size": min(cluster_sizes) if cluster_sizes else None,
        "max_cluster_size": max(cluster_sizes) if cluster_sizes else None,
        "smallest_cluster_share": smallest_share,
        "largest_cluster_share": largest_share,
        "tiny_cluster_count": tiny_cluster_count,
        "small_cluster_count": small_cluster_count,
    }


def collect_clustering_warnings(summary_frame: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    for _, row in summary_frame.iterrows():
        model_name = row["model_name"]
        cluster_count = int(row["cluster_count"])
        silhouette = row["silhouette"]
        if pd.notna(silhouette) and float(silhouette) < 0.25:
            warnings.append(
                f"{model_name} with k={cluster_count} has a weak silhouette score below 0.25."
            )
        if pd.notna(row["tiny_cluster_count"]) and int(row["tiny_cluster_count"]) > 0:
            warnings.append(
                f"{model_name} with k={cluster_count} produced at least one tiny cluster below 1% of eligible cells."
            )
        if pd.notna(row["small_cluster_count"]) and int(row["small_cluster_count"]) >= 2:
            warnings.append(
                f"{model_name} with k={cluster_count} produced multiple small clusters below 5% of eligible cells."
            )
    return warnings


def evaluate_clustering_candidates(
    grid_features: pd.DataFrame,
    k_values: tuple[int, ...] = DEFAULT_K_RANGE,
) -> ClusteringEvaluationResult:
    rows = []
    for cluster_count in k_values:
        kmeans_artifacts = fit_kmeans_typology(grid_features, cluster_count=cluster_count)
        rows.append(summarize_clustering_artifacts(kmeans_artifacts))

    summary_frame = pd.DataFrame(rows).sort_values(
        by=["model_name", "cluster_count"],
        ascending=[True, True],
    )
    warnings = collect_clustering_warnings(summary_frame)
    return ClusteringEvaluationResult(summary_frame=summary_frame, warnings=warnings)


def rank_anomaly_records(artifacts: AnomalyArtifacts) -> pd.DataFrame:
    return (
        artifacts.scored_district_features[
            ["district_name", "district_key", "anomaly_score", "anomaly_flag", "anomaly_top_features"]
        ]
        .sort_values("anomaly_score", ascending=False)
        .reset_index(drop=True)
    )


def evaluate_isolation_forest(
    district_features: pd.DataFrame,
    district_cluster_mix: pd.DataFrame,
) -> AnomalyEvaluationResult:
    iforest = fit_isolation_forest_anomaly(district_features, district_cluster_mix)
    summary_frame = rank_anomaly_records(iforest)

    warnings: list[str] = []
    flagged_count = int(summary_frame["anomaly_flag"].eq(True).sum())
    if flagged_count > 0:
        warnings.append(
            "IsolationForest anomaly flags are exploratory and sensitive to the small district count."
        )
    warnings.append(
        "The top-ranked districts are more defensible as a relative mismatch signal than as a hard anomaly diagnosis."
    )

    return AnomalyEvaluationResult(
        summary_frame=summary_frame,
        warnings=warnings,
    )


def render_evaluation_markdown(
    clustering_result: ClusteringEvaluationResult,
    anomaly_result: AnomalyEvaluationResult,
) -> str:
    lines = [
        "# Model Evaluation Summary",
        "",
        "## Clustering",
        "",
        clustering_result.summary_frame.to_markdown(index=False),
        "",
    ]
    if clustering_result.warnings:
        lines.append("Warnings:")
        for warning in clustering_result.warnings:
            lines.append(f"- {warning}")
        lines.append("")

        lines.extend(
        [
            "## Anomaly Detection",
            "",
            anomaly_result.summary_frame.to_markdown(index=False),
            "",
        ]
    )
    if anomaly_result.warnings:
        lines.append("Warnings:")
        for warning in anomaly_result.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines)


def save_evaluation_summary(
    markdown_text: str,
    output_dir: Path = OUTPUT_DIR,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "model_evaluation_summary.md"
    output_path.write_text(markdown_text, encoding="utf-8")
    return output_path
