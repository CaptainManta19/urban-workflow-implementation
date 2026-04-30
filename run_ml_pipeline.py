from pathlib import Path

from src.feature_engineering import (
    build_feature_tables,
    save_feature_table_specs,
    save_feature_tables,
)
from src.modeling.anomaly import (
    fit_isolation_forest_anomaly,
    fit_local_outlier_factor_anomaly,
    save_anomaly_artifacts,
)
from src.modeling.clustering import (
    fit_gaussian_mixture_typology,
    fit_kmeans_typology,
    save_clustering_artifacts,
)
from src.modeling.evaluation import (
    compare_anomaly_models,
    evaluate_clustering_candidates,
    render_evaluation_markdown,
    save_evaluation_summary,
)


def print_path(label: str, path_value: str | Path | None) -> None:
    if path_value is None:
        return
    print(f"{label}: {path_value}")


def run_pipeline() -> None:
    print("Building feature tables...")
    grid_features, district_features = build_feature_tables()
    feature_manifest = save_feature_tables(grid_features, district_features)
    feature_spec_path = save_feature_table_specs()

    print("Running clustering models...")
    kmeans_artifacts = fit_kmeans_typology(grid_features)
    gmm_artifacts = fit_gaussian_mixture_typology(grid_features)
    kmeans_manifest = save_clustering_artifacts(kmeans_artifacts)
    gmm_manifest = save_clustering_artifacts(gmm_artifacts)

    print("Running anomaly models...")
    iforest_artifacts = fit_isolation_forest_anomaly(
        district_features,
        kmeans_artifacts.district_cluster_mix,
    )
    lof_artifacts = fit_local_outlier_factor_anomaly(
        district_features,
        kmeans_artifacts.district_cluster_mix,
    )
    iforest_manifest = save_anomaly_artifacts(iforest_artifacts)
    lof_manifest = save_anomaly_artifacts(lof_artifacts)

    print("Evaluating model behavior...")
    clustering_evaluation = evaluate_clustering_candidates(grid_features)
    anomaly_evaluation = compare_anomaly_models(
        district_features,
        kmeans_artifacts.district_cluster_mix,
    )
    evaluation_markdown = render_evaluation_markdown(
        clustering_result=clustering_evaluation,
        anomaly_result=anomaly_evaluation,
    )
    evaluation_summary_path = save_evaluation_summary(evaluation_markdown)

    print("\nPipeline completed.")
    print_path("Feature specs", feature_spec_path)
    print_path("Grid features", feature_manifest.grid_feature_path)
    print_path("District features", feature_manifest.district_feature_path)
    print_path("KMeans grid clusters", kmeans_manifest.grid_cluster_path)
    print_path("KMeans cluster profiles", kmeans_manifest.cluster_profile_path)
    print_path("KMeans district cluster mix", kmeans_manifest.district_cluster_mix_path)
    print_path("GaussianMixture grid clusters", gmm_manifest.grid_cluster_path)
    print_path("GaussianMixture cluster profiles", gmm_manifest.cluster_profile_path)
    print_path("GaussianMixture district cluster mix", gmm_manifest.district_cluster_mix_path)
    print_path("IsolationForest district anomalies", iforest_manifest.district_anomaly_path)
    print_path("LocalOutlierFactor district anomalies", lof_manifest.district_anomaly_path)
    print_path("Evaluation summary", evaluation_summary_path)
    print(f"KMeans silhouette: {kmeans_artifacts.silhouette}")
    print(f"GaussianMixture silhouette: {gmm_artifacts.silhouette}")
    if clustering_evaluation.warnings:
        print("Clustering warnings:")
        for warning in clustering_evaluation.warnings:
            print(f"- {warning}")
    if anomaly_evaluation.warnings:
        print("Anomaly warnings:")
        for warning in anomaly_evaluation.warnings:
            print(f"- {warning}")


def main() -> None:
    run_pipeline()


if __name__ == "__main__":
    main()
