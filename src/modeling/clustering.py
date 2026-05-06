import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.feature_engineering import OUTPUT_DIR
from src.ml_schemas import (
    ClusterProfile,
    ClusteringConfig,
    DistrictClusterMixRecord,
    ModelArtifactManifest,
)


DEFAULT_CLUSTER_COUNT = 3
DEFAULT_RANDOM_STATE = 42


def build_one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:  # pragma: no cover - compatibility with older sklearn
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


@dataclass
class PreparedClusteringData:
    eligible_frame: pd.DataFrame
    feature_matrix: np.ndarray
    land_use_feature_count: int
    numeric_feature_count: int
    feature_names: list[str]


@dataclass
class ClusteringArtifacts:
    model_name: str
    cluster_count: int
    labeled_grid_features: pd.DataFrame
    cluster_profiles: list[ClusterProfile]
    district_cluster_mix: pd.DataFrame
    silhouette: float | None


def build_clustering_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            (
                "land_use",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", build_one_hot_encoder()),
                    ]
                ),
                ["lu_2018_class_simplified"],
            ),
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                ["height_mean", "height_max", "pt_stop_count"],
            ),
        ]
    )


def balance_feature_groups(
    feature_matrix: np.ndarray,
    land_use_feature_count: int,
    numeric_feature_count: int,
) -> np.ndarray:
    balanced = feature_matrix.astype(float, copy=True)

    if land_use_feature_count > 0:
        balanced[:, :land_use_feature_count] /= math.sqrt(land_use_feature_count)

    if numeric_feature_count > 0:
        start = land_use_feature_count
        end = land_use_feature_count + numeric_feature_count
        balanced[:, start:end] /= math.sqrt(numeric_feature_count)

    return balanced


def prepare_clustering_data(
    grid_features: pd.DataFrame,
    config: ClusteringConfig | None = None,
) -> PreparedClusteringData:
    config = config or ClusteringConfig()
    eligible_frame = grid_features.loc[grid_features["cluster_features_ready"]].copy()
    if eligible_frame.empty:
        raise ValueError("No eligible grid cells are available for clustering.")

    preprocessor = build_clustering_preprocessor()
    transformed = preprocessor.fit_transform(eligible_frame[config.feature_columns])

    land_use_encoder = preprocessor.named_transformers_["land_use"].named_steps["encoder"]
    land_use_names = list(
        land_use_encoder.get_feature_names_out(["lu_2018_class_simplified"])
    )
    numeric_names = ["height_mean", "height_max", "pt_stop_count"]

    land_use_feature_count = len(land_use_names)
    numeric_feature_count = len(numeric_names)

    if config.balanced_feature_contribution:
        transformed = balance_feature_groups(
            transformed,
            land_use_feature_count=land_use_feature_count,
            numeric_feature_count=numeric_feature_count,
        )

    return PreparedClusteringData(
        eligible_frame=eligible_frame.reset_index(drop=False).rename(columns={"index": "_source_index"}),
        feature_matrix=np.asarray(transformed, dtype=float),
        land_use_feature_count=land_use_feature_count,
        numeric_feature_count=numeric_feature_count,
        feature_names=land_use_names + numeric_names,
    )


def build_narrative_label(profile: dict) -> str:
    land_use = profile.get("dominant_land_use_class")
    mean_height = profile.get("mean_height_mean")
    mean_pt = profile.get("mean_pt_stop_count")

    if land_use in {
        "Continuous urban fabric (S.L. : > 80%)",
        "Discontinuous dense urban fabric (S.L. : 50% -  80%)",
    }:
        if mean_pt is not None and mean_pt >= 4:
            return "Dense accessible urban fabric"
        return "Dense urban fabric"

    if land_use == "Industrial, commercial, public, military and private units":
        return "Industrial and service fabric"

    if land_use in {
        "Green urban areas",
        "Herbaceous vegetation associations (natural grassland, moors...)",
        "Pastures",
        "Arable land (annual crops)",
    }:
        return "Green and open urban fabric"

    if mean_height is not None and mean_height >= 15 and mean_pt is not None and mean_pt >= 3:
        return "Mid-rise accessible mixed fabric"

    if mean_height is not None and mean_height < 8 and mean_pt is not None and mean_pt <= 1:
        return "Low-rise lower-access fabric"

    return "Mixed urban fabric"


def build_cluster_profiles(
    labeled_frame: pd.DataFrame,
    cluster_column: str,
) -> list[ClusterProfile]:
    profiles: list[ClusterProfile] = []
    total_cells = len(labeled_frame)

    for cluster_label, cluster_frame in labeled_frame.groupby(cluster_column):
        dominant_land_use = None
        land_use_counts = cluster_frame["lu_2018_class_simplified"].dropna().value_counts()
        if not land_use_counts.empty:
            dominant_land_use = str(land_use_counts.idxmax())

        profile = {
            "cluster_label": str(cluster_label),
            "cell_count": int(len(cluster_frame)),
            "share_of_cells": round(len(cluster_frame) / total_cells, 4),
            "dominant_land_use_class": dominant_land_use,
            "mean_height_mean": cluster_frame["height_mean"].dropna().mean(),
            "mean_height_max": cluster_frame["height_max"].dropna().mean(),
            "mean_pt_stop_count": cluster_frame["pt_stop_count"].dropna().mean(),
        }
        profile["narrative_label"] = build_narrative_label(profile)

        profiles.append(
            ClusterProfile(
                cluster_label=profile["cluster_label"],
                cell_count=profile["cell_count"],
                share_of_cells=profile["share_of_cells"],
                dominant_land_use_class=profile["dominant_land_use_class"],
                mean_height_mean=profile["mean_height_mean"],
                mean_height_max=profile["mean_height_max"],
                mean_pt_stop_count=profile["mean_pt_stop_count"],
                narrative_label=profile["narrative_label"],
                caveats=[
                    "The label is an interpretive summary of the cluster profile rather than a ground-truth urban category.",
                ],
            )
        )

    return sorted(profiles, key=lambda item: item.cluster_label)


def build_district_cluster_mix(
    labeled_frame: pd.DataFrame,
    cluster_column: str,
) -> pd.DataFrame:
    records = []
    for (district_name, district_key), district_frame in labeled_frame.groupby(
        ["district_name", "district_key"],
        dropna=False,
    ):
        cluster_shares = (
            district_frame[cluster_column]
            .value_counts(normalize=True)
            .sort_index()
            .to_dict()
        )
        records.append(
            DistrictClusterMixRecord(
                district_name=str(district_name),
                district_key=str(district_key),
                cluster_shares={str(key): float(value) for key, value in cluster_shares.items()},
                dominant_cluster_label=(
                    str(max(cluster_shares, key=cluster_shares.get))
                    if cluster_shares
                    else None
                ),
            ).model_dump()
        )
    return pd.DataFrame(records)


def attach_cluster_assignments(
    grid_features: pd.DataFrame,
    eligible_frame: pd.DataFrame,
    cluster_labels: np.ndarray,
    distance_values: np.ndarray | None = None,
    probability_values: np.ndarray | None = None,
) -> pd.DataFrame:
    labeled = grid_features.copy()
    label_strings = [f"cluster_{int(label)}" for label in cluster_labels]

    labeled.loc[eligible_frame["_source_index"], "cluster_label"] = label_strings

    if distance_values is not None:
        labeled.loc[
            eligible_frame["_source_index"],
            "cluster_distance_to_centroid",
        ] = distance_values.tolist()

    if probability_values is not None:
        labeled.loc[
            eligible_frame["_source_index"],
            "cluster_distance_to_centroid",
        ] = (1.0 - probability_values).tolist()

    return labeled


def fit_kmeans_typology(
    grid_features: pd.DataFrame,
    cluster_count: int = DEFAULT_CLUSTER_COUNT,
    random_state: int = DEFAULT_RANDOM_STATE,
    config: ClusteringConfig | None = None,
) -> ClusteringArtifacts:
    prepared = prepare_clustering_data(grid_features, config=config)
    model = KMeans(n_clusters=cluster_count, random_state=random_state, n_init=20)
    cluster_labels = model.fit_predict(prepared.feature_matrix)
    distances = np.linalg.norm(
        prepared.feature_matrix - model.cluster_centers_[cluster_labels],
        axis=1,
    )
    labeled = attach_cluster_assignments(
        grid_features,
        prepared.eligible_frame,
        cluster_labels,
        distance_values=distances,
    )
    labeled_eligible = labeled.loc[labeled["cluster_label"].notna()].copy()
    silhouette = None
    if labeled_eligible["cluster_label"].nunique() > 1:
        silhouette = float(silhouette_score(prepared.feature_matrix, cluster_labels))

    return ClusteringArtifacts(
        model_name="kmeans",
        cluster_count=cluster_count,
        labeled_grid_features=labeled,
        cluster_profiles=build_cluster_profiles(labeled_eligible, "cluster_label"),
        district_cluster_mix=build_district_cluster_mix(labeled_eligible, "cluster_label"),
        silhouette=silhouette,
    )

def save_clustering_artifacts(
    artifacts: ClusteringArtifacts,
    output_dir: Path = OUTPUT_DIR,
) -> ModelArtifactManifest:
    output_dir.mkdir(parents=True, exist_ok=True)

    grid_cluster_path = output_dir / f"grid_clusters_{artifacts.model_name}.csv"
    cluster_profile_path = output_dir / f"cluster_profiles_{artifacts.model_name}.json"
    district_cluster_mix_path = output_dir / f"district_cluster_mix_{artifacts.model_name}.csv"

    artifacts.labeled_grid_features.to_csv(grid_cluster_path, index=False)
    pd.DataFrame([profile.model_dump() for profile in artifacts.cluster_profiles]).to_json(
        cluster_profile_path,
        orient="records",
        indent=2,
    )
    artifacts.district_cluster_mix.to_csv(district_cluster_mix_path, index=False)

    return ModelArtifactManifest(
        grid_cluster_path=str(grid_cluster_path),
        cluster_profile_path=str(cluster_profile_path),
        district_cluster_mix_path=str(district_cluster_mix_path),
    )
