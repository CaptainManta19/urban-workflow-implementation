from pathlib import Path

import pandas as pd

from backend.features.engineering import (
    build_feature_tables,
    save_feature_definitions,
    save_feature_tables,
)
from backend.models.anomaly_detection import (
    fit_isolation_forest_anomaly,
    save_anomaly_artifacts,
)
from backend.models.clustering import (
    fit_kmeans_typology,
    save_clustering_artifacts,
)
from backend.models.evaluation import (
    evaluate_clustering_candidates,
    evaluate_isolation_forest,
    render_evaluation_markdown,
    save_evaluation_summary,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def print_stage_start(title: str) -> None:
    print(f"\n{title}...")


def print_stage_done(lines: list[str]) -> None:
    print("Done.")
    for line in lines:
        print(f"- {line}")
    print("")


def format_path(path_value: str | Path | None) -> str:
    if path_value is None:
        return "Not available"
    path = Path(path_value)
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def format_float(value: float | None, decimals: int = 2) -> str:
    if value is None or pd.isna(value):
        return "Not available"
    return f"{value:.{decimals}f}"


def print_warning_section(title: str, warnings: list[str]) -> None:
    if not warnings:
        return
    print(f"\n{title}")
    for warning in warnings:
        print(f"- {warning}")


def ask_to_continue_or_inspect(message: str) -> str:
    while True:
        response = input(f"{message} [y]es / [n]o / [i]nspect details: ").strip().lower()
        if response in {"y", "yes"}:
            return "yes"
        if response in {"n", "no"}:
            return "no"
        if response in {"i", "inspect"}:
            return "inspect"
        print("Please enter 'y', 'n', or 'i'.")


def ask_yes_no(message: str) -> bool:
    while True:
        response = input(f"{message} [y]es / [n]o: ").strip().lower()
        if response in {"y", "yes"}:
            return True
        if response in {"n", "no"}:
            return False
        print("Please enter 'y' or 'n'.")


def review_stage_details(
    continue_message: str,
    detail_title: str,
    detail_lines: list[str],
    stop_message: str,
) -> bool:
    user_choice = ask_to_continue_or_inspect(continue_message)
    if user_choice == "yes":
        return True
    if user_choice == "no":
        print(stop_message)
        return False

    print(f"\n{detail_title}")
    print("-" * len(detail_title))
    for line in detail_lines:
        print(f"- {line}")

    if ask_yes_no(continue_message):
        return True

    print(stop_message)
    return False


def extend_with_warning_lines(
    detail_lines: list[str],
    section_title: str,
    warnings: list[str],
) -> list[str]:
    if not warnings:
        return detail_lines + [f"{section_title}: none"]

    extended_lines = detail_lines + [f"{section_title}:"]
    extended_lines.extend(f"  - {warning}" for warning in warnings)
    return extended_lines


def run_pipeline() -> None:
    print_stage_start("Building feature tables")
    grid_features, district_features = build_feature_tables()
    feature_manifest = save_feature_tables(grid_features, district_features)
    feature_spec_path = save_feature_definitions()
    print_stage_done(
        [
            f"Grid feature rows: {len(grid_features):,}",
            f"District feature rows: {len(district_features):,}",
            f"Outputs: {format_path(feature_manifest.grid_feature_path)}, {format_path(feature_manifest.district_feature_path)}",
        ]
    )
    if not review_stage_details(
        continue_message="Continue to clustering?",
        detail_title="Feature Table Details",
        detail_lines=[
            f"Grid feature rows: {len(grid_features):,}",
            f"District feature rows: {len(district_features):,}",
            f"Grid features saved to: {format_path(feature_manifest.grid_feature_path)}",
            f"District features saved to: {format_path(feature_manifest.district_feature_path)}",
            f"Feature definitions saved to: {format_path(feature_spec_path)}",
            f"Grid feature columns: {len(grid_features.columns):,}",
            f"District feature columns: {len(district_features.columns):,}",
        ],
        stop_message="Workflow stopped after feature table generation.",
    ):
        return

    print_stage_start("Running clustering")
    kmeans_artifacts = fit_kmeans_typology(grid_features)
    kmeans_manifest = save_clustering_artifacts(kmeans_artifacts)
    clustered_cell_count = int(kmeans_artifacts.labeled_grid_features["cluster_label"].notna().sum())
    print_stage_done(
        [
            "Model: KMeans",
            f"Grid cells clustered: {clustered_cell_count:,}",
            f"Cluster count: {kmeans_artifacts.cluster_count}",
            f"Output: {format_path(kmeans_manifest.grid_cluster_path)}",
        ]
    )
    if not review_stage_details(
        continue_message="Continue to anomaly detection?",
        detail_title="Clustering Details",
        detail_lines=[
            "Model: KMeans",
            f"Eligible grid cells: {clustered_cell_count:,}",
            f"Cluster count: {kmeans_artifacts.cluster_count}",
            f"Cluster profiles generated: {len(kmeans_artifacts.cluster_profiles):,}",
            f"Silhouette score: {format_float(kmeans_artifacts.silhouette)}",
            f"Grid clusters saved to: {format_path(kmeans_manifest.grid_cluster_path)}",
            f"Cluster profiles saved to: {format_path(kmeans_manifest.cluster_profile_path)}",
            f"District cluster mix saved to: {format_path(kmeans_manifest.district_cluster_mix_path)}",
            f"Smallest cluster size: {min(profile.cell_count for profile in kmeans_artifacts.cluster_profiles):,}",
            f"Largest cluster size: {max(profile.cell_count for profile in kmeans_artifacts.cluster_profiles):,}",
            "Formal clustering warnings are generated in the evaluation step.",
        ],
        stop_message="Workflow stopped after clustering.",
    ):
        return

    print_stage_start("Running anomaly detection")
    iforest_artifacts = fit_isolation_forest_anomaly(
        district_features,
        kmeans_artifacts.district_cluster_mix,
    )
    iforest_manifest = save_anomaly_artifacts(iforest_artifacts)
    flagged_district_count = sum(record.anomaly_flag for record in iforest_artifacts.anomaly_records)
    print_stage_done(
        [
            "Model: IsolationForest",
            f"Districts scored: {len(iforest_artifacts.anomaly_records):,}",
            f"Districts flagged: {flagged_district_count:,}",
            f"Output: {format_path(iforest_manifest.district_anomaly_path)}",
        ]
    )
    flagged_districts = [
        record.district_name
        for record in iforest_artifacts.anomaly_records
        if record.anomaly_flag
    ]
    if not review_stage_details(
        continue_message="Continue to model evaluation?",
        detail_title="Anomaly Detection Details",
        detail_lines=[
            "Model: IsolationForest",
            f"Districts scored: {len(iforest_artifacts.anomaly_records):,}",
            f"Districts flagged: {flagged_district_count:,}",
            f"Feature count used: {len(iforest_artifacts.feature_columns):,}",
            f"District anomalies saved to: {format_path(iforest_manifest.district_anomaly_path)}",
            (
                f"Flagged districts: {', '.join(flagged_districts)}"
                if flagged_districts
                else "Flagged districts: none"
            ),
            "Formal anomaly warnings are generated in the evaluation step.",
        ],
        stop_message="Workflow stopped after anomaly detection.",
    ):
        return

    print_stage_start("Evaluating model behavior")
    clustering_evaluation = evaluate_clustering_candidates(grid_features)
    anomaly_evaluation = evaluate_isolation_forest(
        district_features,
        kmeans_artifacts.district_cluster_mix,
    )
    evaluation_markdown = render_evaluation_markdown(
        clustering_result=clustering_evaluation,
        anomaly_result=anomaly_evaluation,
    )
    evaluation_summary_path = save_evaluation_summary(evaluation_markdown)
    print_stage_done(
        [
            f"Evaluation summary: {format_path(evaluation_summary_path)}",
            f"Clustering warnings: {len(clustering_evaluation.warnings)}",
            f"Anomaly warnings: {len(anomaly_evaluation.warnings)}",
        ]
    )

    print("\nPipeline completed.")
    review_stage_details(
        continue_message="Finish workflow?",
        detail_title="Evaluation Details",
        detail_lines=extend_with_warning_lines(
            extend_with_warning_lines(
                [
                    f"Evaluation summary saved to: {format_path(evaluation_summary_path)}",
                    f"Clustering warnings: {len(clustering_evaluation.warnings)}",
                    f"Anomaly warnings: {len(anomaly_evaluation.warnings)}",
                ],
                "Clustering warnings",
                clustering_evaluation.warnings,
            ),
            "Anomaly warnings",
            anomaly_evaluation.warnings,
        ),
        stop_message="Workflow finished.",
    )


def main() -> None:
    run_pipeline()


if __name__ == "__main__":
    main()
