import json
import math
import re
import sqlite3
from pathlib import Path

import pandas as pd

from src.ml_schemas import (
    DistrictFeatureRecord,
    FeatureColumnSpec,
    FeatureLineage,
    FeatureTableSpec,
    GridFeatureRecord,
    ModelArtifactManifest,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
FETCHED_DIR = DATA_DIR / "fetched"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "ml"

BOUNDARIES_PATH = FETCHED_DIR / "madrid_district_boundaries.json"
POPULATION_PATH = FETCHED_DIR / "madrid_population_district_barrio_api.json"
INDICATOR_PANEL_PATH = FETCHED_DIR / "madrid_district_indicator_panel_api.json"
HOUSING_PATH = RAW_DIR / "emvs_housing.csv"
GRID_GPKG_PATH = RAW_DIR / "madrid_grid_250m_lu_height_transport_rent_emvs_district.gpkg"
GRID_LAYER_NAME = "grid_250m_lu_height_transport_rent_emvs_district"
NOTEBOOK_REFERENCE = "combined_dataset.ipynb"

GREEN_LIKE_CLASSES = {
    "Green urban areas",
    "Herbaceous vegetation associations (natural grassland, moors...)",
    "Pastures",
    "Arable land (annual crops)",
}
RESIDENTIAL_CLASSES = {
    "Continuous urban fabric (S.L. : > 80%)",
    "Discontinuous dense urban fabric (S.L. : 50% -  80%)",
}
INDUSTRIAL_CLASSES = {
    "Industrial, commercial, public, military and private units",
}
DENSE_URBAN_CLASSES = {
    "Continuous urban fabric (S.L. : > 80%)",
    "Discontinuous dense urban fabric (S.L. : 50% -  80%)",
}
DISTRICT_COVERAGE_COLUMNS = [
    "population_total",
    "population_density_km2",
    "housing_total",
    "housing_per_1000_residents",
    "green_area_per_10000",
    "income_per_person",
    "household_income",
    "unemployment_rate",
    "vulnerability_index",
    "vulnerability_employment",
    "grid_height_mean_avg",
    "grid_pt_stop_count_avg",
    "grid_green_like_share",
    "grid_dense_urban_share",
]


def parse_spanish_int(value: str) -> int:
    return int(str(value).replace(".", "").strip())


def parse_spanish_float(value: str | int | float | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def normalise_district_name(value: str) -> str:
    return re.sub(r"[\s-]+", "", str(value).casefold())


def extract_year(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"(19|20)\d{2}", str(text))
    return int(match.group(0)) if match else None


def compute_polygon_area_m2(geometry: dict) -> float | None:
    if geometry.get("type") != "Polygon":
        return None

    rings = geometry.get("coordinates", [])
    if not rings:
        return None

    outer_ring = rings[0]
    if len(outer_ring) < 4:
        return None

    # Approximate the polygon area by projecting lon/lat points to Web Mercator
    # before applying the shoelace formula. This avoids a hard dependency on
    # `pyproj` while keeping the estimate stable enough for district density.
    radius = 6_378_137.0
    projected_points = []
    for lon, lat in outer_ring:
        lon_rad = math.radians(lon)
        lat_rad = math.radians(max(min(lat, 89.5), -89.5))
        x = radius * lon_rad
        y = radius * math.log(math.tan(math.pi / 4 + lat_rad / 2))
        projected_points.append((x, y))

    area = 0.0
    for index in range(len(projected_points) - 1):
        x1, y1 = projected_points[index]
        x2, y2 = projected_points[index + 1]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def compute_polygon_centroid(geometry: dict) -> tuple[float | None, float | None]:
    if geometry.get("type") != "Polygon":
        return None, None

    rings = geometry.get("coordinates", [])
    if not rings or not rings[0]:
        return None, None

    outer_ring = rings[0]
    longitudes = [point[0] for point in outer_ring]
    latitudes = [point[1] for point in outer_ring]
    return sum(longitudes) / len(longitudes), sum(latitudes) / len(latitudes)


def load_district_geojson() -> dict:
    with BOUNDARIES_PATH.open("r", encoding="utf-8") as file_handle:
        topology = json.load(file_handle)

    scale = topology["transform"]["scale"]
    translate = topology["transform"]["translate"]
    arcs = topology["arcs"]
    geometries = topology["objects"]["Distritos"]["geometries"]

    features = []
    for geometry in geometries:
        polygon_coordinates = []
        for ring_arc_indices in geometry["arcs"]:
            ring: list[list[float]] = []
            for position, arc_index in enumerate(ring_arc_indices):
                source_arc = arcs[arc_index] if arc_index >= 0 else arcs[~arc_index]
                x = 0
                y = 0
                coordinates: list[list[float]] = []
                for dx, dy in source_arc:
                    x += dx
                    y += dy
                    coordinates.append(
                        [
                            translate[0] + x * scale[0],
                            translate[1] + y * scale[1],
                        ]
                    )
                if arc_index < 0:
                    coordinates = list(reversed(coordinates))
                if position > 0:
                    coordinates = coordinates[1:]
                ring.extend(coordinates)
            if ring and ring[0] != ring[-1]:
                ring.append(ring[0])
            polygon_coordinates.append(ring)

        properties = geometry["properties"]
        features.append(
            {
                "type": "Feature",
                "id": properties["NOMBRE"],
                "properties": properties,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": polygon_coordinates,
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def load_population_frame() -> pd.DataFrame:
    with POPULATION_PATH.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)

    rows = payload["result"]["records"]
    district_rows = [
        row
        for row in rows
        if row.get("distrito") == row.get("barrio")
        and str(row.get("cod_distrito", "")).isdigit()
    ]
    latest_year = max(
        extract_year(row.get("fecha"))
        for row in district_rows
        if extract_year(row.get("fecha")) is not None
    )
    district_rows = [
        row
        for row in district_rows
        if extract_year(row.get("fecha")) == latest_year
    ]

    frame = pd.DataFrame(district_rows)
    frame["population_total"] = frame["num_personas"].apply(parse_spanish_int)
    frame["population_male"] = frame["num_personas_hombres"].apply(parse_spanish_int)
    frame["population_female"] = frame["num_personas_mujeres"].apply(parse_spanish_int)
    frame["district_code"] = frame["cod_distrito"].astype(int)
    frame["district_name"] = frame["distrito"]
    frame["district_key"] = frame["district_name"].apply(normalise_district_name)
    frame["reference_date"] = frame["fecha"]

    return frame[
        [
            "district_code",
            "district_name",
            "district_key",
            "reference_date",
            "population_total",
            "population_male",
            "population_female",
        ]
    ].sort_values("district_code")


def load_indicator_panel_rows() -> list[dict]:
    with INDICATOR_PANEL_PATH.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)

    rows = payload["result"]["records"]
    district_rows = []
    for row in rows:
        code = str(row.get("cod_distrito", "")).strip()
        if not code.isdigit():
            continue
        if int(code) < 1 or int(code) > 21:
            continue
        if row.get("barrio") not in (None, "", "null"):
            continue
        district_rows.append(row)

    return district_rows


def extract_latest_indicator_frame(
    rows: list[dict],
    indicator_name: str,
    value_column_name: str,
) -> pd.DataFrame:
    indicator_rows = [
        row for row in rows
        if row.get("indicador_completo") == indicator_name
    ]
    if not indicator_rows:
        return pd.DataFrame(columns=["district_key", value_column_name, f"{value_column_name}_year"])

    latest_year = max(
        int(str(row["ano"]))
        for row in indicator_rows
        if str(row.get("ano", "")).isdigit()
    )
    latest_rows = [
        row for row in indicator_rows
        if str(row.get("ano", "")) == str(latest_year)
    ]

    frame = pd.DataFrame(latest_rows)
    if "Periodo panel" in frame.columns:
        frame["panel_year"] = frame["Periodo panel"].apply(parse_spanish_float)
        frame = frame.sort_values(by=["panel_year", "_id"], ascending=[True, True], na_position="last")
    frame["district_key"] = frame["distrito"].apply(normalise_district_name)
    frame = frame.drop_duplicates(subset=["district_key"], keep="last")
    frame[value_column_name] = frame["valor_indicador"].apply(parse_spanish_float)
    frame[f"{value_column_name}_year"] = latest_year
    return frame[["district_key", value_column_name, f"{value_column_name}_year"]]


def load_housing_frame() -> pd.DataFrame:
    frame = pd.read_csv(HOUSING_PATH, sep=";", encoding="utf-8", header=1)
    frame = frame.rename(
        columns={
            "DISTRITOS": "district_name",
            "TOTAL": "housing_total",
            "REGLAMENTO ADJUDICACION": "housing_regulation",
            "RESTO PROGRAMAS": "housing_other_programs",
        }
    )
    frame = frame[frame["district_name"] != "TOTAL"].copy()
    frame["district_key"] = frame["district_name"].apply(normalise_district_name)
    for column in ("housing_total", "housing_regulation", "housing_other_programs"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame[
        [
            "district_name",
            "district_key",
            "housing_total",
            "housing_regulation",
            "housing_other_programs",
        ]
    ]


def load_grid_frame() -> pd.DataFrame:
    query = f"""
        SELECT
            cell_id,
            lu_2018_class,
            lu_2018_class_simplified,
            height_mean,
            height_max,
            pt_stop_count,
            pt_access_good,
            rent_median_m2_2023,
            emvs_units_total,
            district_name
        FROM {GRID_LAYER_NAME}
        WHERE district_name IS NOT NULL
    """
    rows = []
    with sqlite3.connect(GRID_GPKG_PATH) as connection:
        cursor = connection.cursor()
        for (
            cell_id,
            land_use_class,
            land_use_class_simplified,
            height_mean,
            height_max,
            pt_stop_count,
            pt_access_good,
            rent_median_m2_2023,
            emvs_units_total,
            district_name,
        ) in cursor.execute(query):
            rows.append(
                {
                    "cell_id": str(cell_id),
                    "district_name": district_name,
                    "district_key": normalise_district_name(district_name),
                    "lu_2018_class": land_use_class,
                    "lu_2018_class_simplified": land_use_class_simplified,
                    "height_mean": height_mean,
                    "height_max": height_max,
                    "pt_stop_count": int(pt_stop_count) if pt_stop_count is not None else None,
                    "pt_access_good": bool(pt_access_good) if pt_access_good is not None else None,
                    "rent_median_m2_2023": rent_median_m2_2023,
                    "emvs_units_total": emvs_units_total,
                }
            )
    return pd.DataFrame(rows)


def build_district_base_frame() -> pd.DataFrame:
    geojson = load_district_geojson()
    population = load_population_frame()
    housing = load_housing_frame()
    indicator_rows = load_indicator_panel_rows()
    green_total = extract_latest_indicator_frame(
        indicator_rows,
        "Superficie de zonas verdes y parques de distrito (ha.)",
        "green_area_ha",
    )
    green_rate = extract_latest_indicator_frame(
        indicator_rows,
        "Superficie de zonas verdes y parques de distrito (ha.) entre número de habitantes *10.000",
        "green_area_per_10000",
    )
    income_person = extract_latest_indicator_frame(
        indicator_rows,
        "Renta media disponible por persona",
        "income_per_person",
    )
    household_income = extract_latest_indicator_frame(
        indicator_rows,
        "Renta neta media anual de los hogares (Urban Audit)",
        "household_income",
    )
    unemployment_total = extract_latest_indicator_frame(
        indicator_rows,
        "Paro registrado (número de personas registradas en SEPE en febrero)",
        "unemployment_total",
    )
    unemployment_rate = extract_latest_indicator_frame(
        indicator_rows,
        "Tasa absoluta de paro registrado (febrero)",
        "unemployment_rate",
    )
    vulnerability_total = extract_latest_indicator_frame(
        indicator_rows,
        "Índice de vulnerabilidad territorial agregado",
        "vulnerability_index",
    )
    vulnerability_employment = extract_latest_indicator_frame(
        indicator_rows,
        "Índice de vulnerabilidad economía y empleo",
        "vulnerability_employment",
    )

    area_rows = []
    for feature in geojson["features"]:
        centroid_lon, centroid_lat = compute_polygon_centroid(feature["geometry"])
        area_rows.append(
            {
                "district_name": feature["properties"]["NOMBRE"],
                "district_key": normalise_district_name(feature["properties"]["NOMBRE"]),
                "area_m2": compute_polygon_area_m2(feature["geometry"]),
                "centroid_lon": centroid_lon,
                "centroid_lat": centroid_lat,
            }
        )

    area_frame = pd.DataFrame(area_rows)
    merged = area_frame.merge(population, on="district_key", how="left", suffixes=("_boundary", ""))
    merged["district_name"] = merged["district_name_boundary"]
    merged["area_km2"] = merged["area_m2"] / 1_000_000
    merged["population_density_km2"] = (
        merged["population_total"] / merged["area_km2"]
    ).round(0)
    merged = merged.merge(
        housing.drop(columns=["district_name"]),
        on="district_key",
        how="left",
    )
    for indicator_frame in (
        green_total,
        green_rate,
        income_person,
        household_income,
        unemployment_total,
        unemployment_rate,
        vulnerability_total,
        vulnerability_employment,
    ):
        merged = merged.merge(indicator_frame, on="district_key", how="left")
    merged["housing_per_1000_residents"] = (
        merged["housing_total"] / merged["population_total"] * 1000
    ).round(2)
    merged["has_population_data"] = merged["population_total"].notna()
    merged["has_housing_data"] = merged["housing_total"].notna()
    merged["has_green_data"] = merged["green_area_per_10000"].notna()
    merged["has_economy_data"] = merged["income_per_person"].notna()
    merged["has_employment_data"] = merged["unemployment_rate"].notna()
    merged["has_vulnerability_data"] = merged["vulnerability_index"].notna()

    return merged


def build_grid_features() -> pd.DataFrame:
    frame = load_grid_frame()
    frame["cluster_features_ready"] = (
        frame["lu_2018_class_simplified"].notna()
        & frame["height_mean"].notna()
        & frame["height_max"].notna()
        & frame["pt_stop_count"].notna()
    )
    frame["cluster_label"] = None
    frame["cluster_distance_to_centroid"] = None

    ordered_columns = list(GridFeatureRecord.model_fields.keys())
    return frame.reindex(columns=ordered_columns)


def compute_share(series: pd.Series, allowed_values: set[str]) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.isin(allowed_values).mean())


def build_district_features(grid_features: pd.DataFrame | None = None) -> pd.DataFrame:
    if grid_features is None:
        grid_features = build_grid_features()

    base = build_district_base_frame()
    aggregated_grid = (
        grid_features.groupby(["district_name", "district_key"], dropna=False)
        .apply(
            lambda district_frame: pd.Series(
                {
                    "grid_cell_count": int(len(district_frame)),
                    "grid_height_mean_avg": district_frame["height_mean"].dropna().mean(),
                    "grid_height_max_avg": district_frame["height_max"].dropna().mean(),
                    "grid_pt_stop_count_avg": district_frame["pt_stop_count"].dropna().mean(),
                    "grid_pt_access_good_share": (
                        district_frame["pt_access_good"].dropna().astype(bool).mean()
                        if district_frame["pt_access_good"].dropna().shape[0] > 0
                        else None
                    ),
                    "grid_green_like_share": compute_share(
                        district_frame["lu_2018_class_simplified"],
                        GREEN_LIKE_CLASSES,
                    ),
                    "grid_residential_share": compute_share(
                        district_frame["lu_2018_class_simplified"],
                        RESIDENTIAL_CLASSES,
                    ),
                    "grid_industrial_share": compute_share(
                        district_frame["lu_2018_class_simplified"],
                        INDUSTRIAL_CLASSES,
                    ),
                    "grid_dense_urban_share": compute_share(
                        district_frame["lu_2018_class_simplified"],
                        DENSE_URBAN_CLASSES,
                    ),
                }
            )
        )
        .reset_index()
    )

    merged = base.merge(
        aggregated_grid,
        on=["district_name", "district_key"],
        how="left",
    )
    merged["grid_typology_entropy"] = None
    merged["anomaly_score"] = None
    merged["anomaly_flag"] = None
    merged["anomaly_top_features"] = [[] for _ in range(len(merged))]
    merged["data_coverage_score"] = merged[DISTRICT_COVERAGE_COLUMNS].notna().mean(axis=1).round(3)

    ordered_columns = list(DistrictFeatureRecord.model_fields.keys())
    return merged.reindex(columns=ordered_columns)


def save_feature_tables(
    grid_features: pd.DataFrame,
    district_features: pd.DataFrame,
    output_dir: Path = OUTPUT_DIR,
) -> ModelArtifactManifest:
    output_dir.mkdir(parents=True, exist_ok=True)
    grid_feature_path = output_dir / "grid_features.csv"
    district_feature_path = output_dir / "district_features.csv"

    grid_features.to_csv(grid_feature_path, index=False)
    district_features.to_csv(district_feature_path, index=False)

    return ModelArtifactManifest(
        grid_feature_path=str(grid_feature_path),
        district_feature_path=str(district_feature_path),
    )


def save_feature_table_specs(
    output_dir: Path = OUTPUT_DIR,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "feature_table_specs.json"
    specs = [spec.model_dump() for spec in build_feature_table_specs()]
    output_path.write_text(
        json.dumps(specs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def build_feature_table_specs() -> list[FeatureTableSpec]:
    grid_notebook_lineage = FeatureLineage(
        source_id="madrid_grid_derived_notebook",
        source_label="Research-derived 250m Madrid grid dataset",
        source_path=str(GRID_GPKG_PATH),
        transformation_summary=(
            "The 250m grid was progressively enriched in the notebook with Urban Atlas land use, "
            "Urban Atlas height, OpenStreetMap transport points, district rent, EMVS public housing, "
            "and district labels."
        ),
        notebook_reference=NOTEBOOK_REFERENCE,
        caveats=[
            "The grid dataset is derived rather than a single direct official source.",
            "Some district-level values are inherited by cells through centroid-based assignment.",
        ],
    )
    district_indicator_lineage = FeatureLineage(
        source_id="madrid_district_indicator_panel",
        source_label="Madrid district indicator panel",
        source_path=str(INDICATOR_PANEL_PATH),
        source_url="https://datos.madrid.es/dataset/300087-0-indicadores-distritos/information",
        transformation_summary="Latest district-level indicator values are extracted and harmonised by district key.",
    )
    population_lineage = FeatureLineage(
        source_id="madrid_population_api",
        source_label="Madrid population district API extract",
        source_path=str(POPULATION_PATH),
        transformation_summary="District-level population totals are filtered to district rows and the latest reference year.",
    )
    housing_lineage = FeatureLineage(
        source_id="emvs_housing_csv",
        source_label="EMVS public housing CSV",
        source_path=str(HOUSING_PATH),
        transformation_summary="District housing totals are cleaned and harmonised by district key.",
    )

    grid_spec = FeatureTableSpec(
        name="grid_features",
        grain="One row per 250m grid cell",
        purpose="Clustering input table plus grid-level provenance-aware dashboard features.",
        columns=[
            FeatureColumnSpec(
                name="cell_id",
                description="Stable grid cell identifier.",
                status="raw",
                spatial_resolution="grid_cell",
                data_type="string",
                lineage=[grid_notebook_lineage],
            ),
            FeatureColumnSpec(
                name="district_name",
                description="District label assigned to the cell in the notebook pipeline.",
                status="derived",
                spatial_resolution="grid_cell",
                data_type="string",
                lineage=[grid_notebook_lineage],
                caveats=["Assigned through centroid-based district join in the notebook."],
            ),
            FeatureColumnSpec(
                name="lu_2018_class_simplified",
                description="Simplified Urban Atlas land-use class used for clustering.",
                status="derived",
                spatial_resolution="grid_cell",
                data_type="string",
                used_for_clustering=True,
                lineage=[grid_notebook_lineage],
            ),
            FeatureColumnSpec(
                name="height_mean",
                description="Mean building height per cell derived from the raster source.",
                status="derived",
                spatial_resolution="grid_cell",
                data_type="float",
                used_for_clustering=True,
                lineage=[grid_notebook_lineage],
            ),
            FeatureColumnSpec(
                name="height_max",
                description="Maximum building height per cell derived from the raster source.",
                status="derived",
                spatial_resolution="grid_cell",
                data_type="float",
                used_for_clustering=True,
                lineage=[grid_notebook_lineage],
            ),
            FeatureColumnSpec(
                name="pt_stop_count",
                description="Count of public transport features inside the cell.",
                status="derived",
                spatial_resolution="grid_cell",
                data_type="integer",
                used_for_clustering=True,
                lineage=[grid_notebook_lineage],
            ),
            FeatureColumnSpec(
                name="pt_access_good",
                description="Heuristic notebook threshold for good PT access.",
                status="derived",
                spatial_resolution="grid_cell",
                data_type="boolean",
                used_for_clustering=False,
                lineage=[grid_notebook_lineage],
                caveats=["Retained for descriptive UI use, excluded from core v1 clustering due to heuristic thresholding."],
            ),
            FeatureColumnSpec(
                name="rent_median_m2_2023",
                description="District-level rent copied to cells for context.",
                status="derived",
                spatial_resolution="grid_cell",
                data_type="float",
                used_for_clustering=False,
                lineage=[grid_notebook_lineage],
                caveats=["Inherited from district values rather than observed at cell level."],
            ),
            FeatureColumnSpec(
                name="emvs_units_total",
                description="District-level EMVS public housing total copied to cells for context.",
                status="derived",
                spatial_resolution="grid_cell",
                data_type="float",
                used_for_clustering=False,
                lineage=[grid_notebook_lineage],
                caveats=["Inherited from district values rather than observed at cell level."],
            ),
        ],
    )
    district_spec = FeatureTableSpec(
        name="district_features",
        grain="One row per Madrid district",
        purpose="District-level anomaly detection table plus sidebar and pipeline summaries.",
        columns=[
            FeatureColumnSpec(
                name="population_total",
                description="Latest district population total.",
                status="cleaned",
                spatial_resolution="district",
                data_type="float",
                lineage=[population_lineage],
            ),
            FeatureColumnSpec(
                name="population_density_km2",
                description="Population density derived from district population and boundary area.",
                status="derived",
                spatial_resolution="district",
                data_type="float",
                used_for_anomaly_detection=True,
                lineage=[population_lineage],
            ),
            FeatureColumnSpec(
                name="housing_per_1000_residents",
                description="EMVS housing total normalized by district population.",
                status="derived",
                spatial_resolution="district",
                data_type="float",
                used_for_anomaly_detection=True,
                lineage=[housing_lineage, population_lineage],
            ),
            FeatureColumnSpec(
                name="green_area_per_10000",
                description="District green-space provision indicator.",
                status="cleaned",
                spatial_resolution="district",
                data_type="float",
                used_for_anomaly_detection=True,
                lineage=[district_indicator_lineage],
            ),
            FeatureColumnSpec(
                name="income_per_person",
                description="District income indicator per person.",
                status="cleaned",
                spatial_resolution="district",
                data_type="float",
                used_for_anomaly_detection=True,
                lineage=[district_indicator_lineage],
            ),
            FeatureColumnSpec(
                name="household_income",
                description="District household income indicator.",
                status="cleaned",
                spatial_resolution="district",
                data_type="float",
                used_for_anomaly_detection=True,
                lineage=[district_indicator_lineage],
            ),
            FeatureColumnSpec(
                name="unemployment_rate",
                description="District unemployment rate indicator.",
                status="cleaned",
                spatial_resolution="district",
                data_type="float",
                used_for_anomaly_detection=True,
                lineage=[district_indicator_lineage],
            ),
            FeatureColumnSpec(
                name="vulnerability_index",
                description="District territorial vulnerability indicator.",
                status="cleaned",
                spatial_resolution="district",
                data_type="float",
                used_for_anomaly_detection=True,
                lineage=[district_indicator_lineage],
            ),
            FeatureColumnSpec(
                name="vulnerability_employment",
                description="District employment vulnerability indicator.",
                status="cleaned",
                spatial_resolution="district",
                data_type="float",
                used_for_anomaly_detection=True,
                lineage=[district_indicator_lineage],
            ),
            FeatureColumnSpec(
                name="grid_green_like_share",
                description="Share of cells with green-like land-use classes in the district.",
                status="derived",
                spatial_resolution="district",
                data_type="float",
                used_for_anomaly_detection=True,
                lineage=[grid_notebook_lineage],
            ),
            FeatureColumnSpec(
                name="grid_dense_urban_share",
                description="Share of dense urban cells in the district.",
                status="derived",
                spatial_resolution="district",
                data_type="float",
                used_for_anomaly_detection=True,
                lineage=[grid_notebook_lineage],
            ),
        ],
    )
    return [grid_spec, district_spec]


def build_feature_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    grid_features = build_grid_features()
    district_features = build_district_features(grid_features)
    return grid_features, district_features
