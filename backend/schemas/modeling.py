from typing import Literal

from pydantic import BaseModel, Field


FieldStatus = Literal["raw", "cleaned", "derived", "model_generated"]
SpatialResolution = Literal["district", "grid_cell", "mixed"]
ModelName = Literal["kmeans", "isolation_forest"]


class FeatureLineage(BaseModel):
    source_id: str
    source_label: str
    source_path: str | None = None
    source_url: str | None = None
    transformation_summary: str
    notebook_reference: str | None = None
    caveats: list[str] = Field(default_factory=list)


class FeatureColumnSpec(BaseModel):
    name: str
    description: str
    status: FieldStatus
    spatial_resolution: SpatialResolution
    data_type: str
    included_in_v1: bool = True
    used_for_clustering: bool = False
    used_for_anomaly_detection: bool = False
    lineage: list[FeatureLineage] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class FeatureTableSpec(BaseModel):
    name: str
    grain: str
    purpose: str
    columns: list[FeatureColumnSpec] = Field(default_factory=list)


class GridFeatureRecord(BaseModel):
    cell_id: str
    district_name: str | None = None
    district_key: str | None = None
    lu_2018_class: str | None = None
    lu_2018_class_simplified: str | None = None
    height_mean: float | None = None
    height_max: float | None = None
    pt_stop_count: int | None = None
    pt_access_good: bool | None = None
    rent_median_m2_2023: float | None = None
    emvs_units_total: float | None = None
    cluster_features_ready: bool = False
    cluster_label: str | None = None
    cluster_distance_to_centroid: float | None = None


class DistrictFeatureRecord(BaseModel):
    district_name: str
    district_key: str
    district_code: int | None = None
    reference_date: str | None = None
    population_total: float | None = None
    population_male: float | None = None
    population_female: float | None = None
    area_m2: float | None = None
    area_km2: float | None = None
    centroid_lon: float | None = None
    centroid_lat: float | None = None
    population_density_km2: float | None = None
    housing_total: float | None = None
    housing_regulation: float | None = None
    housing_other_programs: float | None = None
    housing_per_1000_residents: float | None = None
    green_area_ha: float | None = None
    green_area_ha_year: int | None = None
    green_area_per_10000: float | None = None
    green_area_per_10000_year: int | None = None
    income_per_person: float | None = None
    income_per_person_year: int | None = None
    household_income: float | None = None
    household_income_year: int | None = None
    unemployment_total: float | None = None
    unemployment_total_year: int | None = None
    unemployment_rate: float | None = None
    unemployment_rate_year: int | None = None
    vulnerability_index: float | None = None
    vulnerability_index_year: int | None = None
    vulnerability_employment: float | None = None
    vulnerability_employment_year: int | None = None
    has_population_data: bool | None = None
    has_housing_data: bool | None = None
    has_green_data: bool | None = None
    has_economy_data: bool | None = None
    has_employment_data: bool | None = None
    has_vulnerability_data: bool | None = None
    grid_cell_count: int | None = None
    grid_height_mean_avg: float | None = None
    grid_height_max_avg: float | None = None
    grid_pt_stop_count_avg: float | None = None
    grid_pt_access_good_share: float | None = None
    grid_green_like_share: float | None = None
    grid_residential_share: float | None = None
    grid_industrial_share: float | None = None
    grid_dense_urban_share: float | None = None
    grid_typology_entropy: float | None = None
    data_coverage_score: float | None = None
    anomaly_score: float | None = None
    anomaly_flag: bool | None = None
    anomaly_top_features: list[str] = Field(default_factory=list)


class ClusteringConfig(BaseModel):
    primary_model: ModelName = "kmeans"
    feature_columns: list[str] = Field(
        default_factory=lambda: [
            "lu_2018_class_simplified",
            "height_mean",
            "height_max",
            "pt_stop_count",
        ]
    )
    excluded_columns: list[str] = Field(
        default_factory=lambda: [
            "pt_access_good",
            "rent_median_m2_2023",
            "emvs_units_total",
        ]
    )
    balanced_feature_contribution: bool = True
    notes: list[str] = Field(
        default_factory=lambda: [
            "Land use should be encoded and scaled alongside numeric features to avoid domination.",
            "The heuristic pt_access_good threshold is excluded from the core v1 clustering input.",
        ]
    )


class AnomalyConfig(BaseModel):
    primary_model: ModelName = "isolation_forest"
    feature_columns: list[str] = Field(
        default_factory=lambda: [
            "population_density_km2",
            "housing_per_1000_residents",
            "green_area_per_10000",
            "income_per_person",
            "household_income",
            "unemployment_rate",
            "vulnerability_index",
            "vulnerability_employment",
            "grid_pt_access_good_share",
            "grid_height_mean_avg",
            "grid_green_like_share",
            "grid_dense_urban_share",
        ]
    )
    notes: list[str] = Field(
        default_factory=lambda: [
            "District cluster composition shares will be appended after clustering aggregation.",
            "Anomaly detection is framed as district-level socio-spatial mismatch, not generic outlier labeling.",
        ]
    )


class ClusterProfile(BaseModel):
    cluster_label: str
    cell_count: int
    share_of_cells: float
    dominant_land_use_class: str | None = None
    mean_height_mean: float | None = None
    mean_height_max: float | None = None
    mean_pt_stop_count: float | None = None
    narrative_label: str | None = None
    caveats: list[str] = Field(default_factory=list)


class DistrictClusterMixRecord(BaseModel):
    district_name: str
    district_key: str
    cluster_shares: dict[str, float] = Field(default_factory=dict)
    dominant_cluster_label: str | None = None


class DistrictAnomalyRecord(BaseModel):
    district_name: str
    district_key: str
    anomaly_score: float
    anomaly_flag: bool
    top_contributing_features: list[str] = Field(default_factory=list)
    interpretation_notes: list[str] = Field(default_factory=list)


class ModelArtifactManifest(BaseModel):
    grid_feature_path: str | None = None
    district_feature_path: str | None = None
    grid_cluster_path: str | None = None
    cluster_profile_path: str | None = None
    district_cluster_mix_path: str | None = None
    district_anomaly_path: str | None = None
