import json
import re
import sqlite3
import struct
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import ALL, Dash, Input, Output, State, callback_context, dcc, html, no_update
from pyproj import Geod, Transformer


PROJECT_ROOT = Path(__file__).resolve().parent
BOUNDARIES_PATH = PROJECT_ROOT / "data" / "fetched" / "madrid_district_boundaries.json"
POPULATION_PATH = PROJECT_ROOT / "data" / "fetched" / "madrid_population_district_barrio_api.json"
INDICATOR_PANEL_PATH = PROJECT_ROOT / "data" / "fetched" / "madrid_district_indicator_panel_api.json"
HOUSING_PATH = PROJECT_ROOT / "data" / "raw" / "emvs_housing.csv"
GRID_GPKG_PATH = PROJECT_ROOT / "data" / "raw" / "madrid_grid_250m_lu_height_transport_rent_emvs_district.gpkg"
DEFAULT_DISTRICT = "Centro"
DEFAULT_TOPIC = "population"
GEOD = Geod(ellps="WGS84")
GRID_TRANSFORMER = Transformer.from_crs(3035, 4326, always_xy=True)
DEFAULT_MOBILITY_THRESHOLD = 2
MOBILITY_SLIDER_MAX = 10
MAP_UIREVISION = "district-map-shared-view"
DEFAULT_VIEW_MODE = "display"
DEFAULT_DISPLAY_SELECTION_MODE = "inspect"
DEFAULT_PIPELINE_STAGE = "representation"


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


def build_lucide_icon(svg_inner: str) -> html.Img:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="#111827" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{svg_inner}</svg>"
    )
    return html.Img(
        src=f"data:image/svg+xml;utf8,{quote(svg)}",
        className="topic-icon-svg",
        alt="",
        draggable="false",
    )


def build_lucide_icon_data_uri(svg_inner: str, stroke: str = "#111827") -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" '
        f'stroke="{stroke}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{svg_inner}</svg>"
    )
    return f"data:image/svg+xml;utf8,{quote(svg)}"


def normalise_district_name(value: str) -> str:
    return re.sub(r"[\s-]+", "", str(value).casefold())


def extract_year(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"(19|20)\d{2}", str(text))
    return int(match.group(0)) if match else None


def decode_arc(arc_index: int, arcs: list, scale: list[float], translate: list[float]) -> list[list[float]]:
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

    return coordinates


def build_ring(arc_indices: list[int], arcs: list, scale: list[float], translate: list[float]) -> list[list[float]]:
    ring: list[list[float]] = []

    for position, arc_index in enumerate(arc_indices):
        coordinates = decode_arc(arc_index, arcs, scale, translate)
        if position > 0:
            coordinates = coordinates[1:]
        ring.extend(coordinates)

    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])

    return ring


def load_district_geojson() -> dict:
    with BOUNDARIES_PATH.open("r", encoding="utf-8") as file_handle:
        topology = json.load(file_handle)

    scale = topology["transform"]["scale"]
    translate = topology["transform"]["translate"]
    arcs = topology["arcs"]
    geometries = topology["objects"]["Distritos"]["geometries"]

    features = []
    for geometry in geometries:
        polygon_coordinates = [
            build_ring(ring_arc_indices, arcs, scale, translate)
            for ring_arc_indices in geometry["arcs"]
        ]
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


def geopackage_envelope_size(flags: int) -> int:
    envelope_code = (flags >> 1) & 0b111
    if envelope_code == 0:
        return 0
    if envelope_code == 1:
        return 32
    if envelope_code in (2, 3):
        return 48
    if envelope_code == 4:
        return 64
    raise ValueError(f"Unsupported GeoPackage envelope code: {envelope_code}")


def parse_wkb_polygon(data: bytes, offset: int) -> list[list[tuple[float, float]]]:
    endian_flag = data[offset]
    byte_order = "<" if endian_flag == 1 else ">"
    wkb_type = struct.unpack(f"{byte_order}I", data[offset + 1:offset + 5])[0]
    if wkb_type != 3:
        raise ValueError(f"Unsupported WKB geometry type: {wkb_type}")

    ring_count = struct.unpack(f"{byte_order}I", data[offset + 5:offset + 9])[0]
    cursor = offset + 9
    rings: list[list[tuple[float, float]]] = []
    for _ in range(ring_count):
        point_count = struct.unpack(f"{byte_order}I", data[cursor:cursor + 4])[0]
        cursor += 4
        ring: list[tuple[float, float]] = []
        for _ in range(point_count):
            x = struct.unpack(f"{byte_order}d", data[cursor:cursor + 8])[0]
            y = struct.unpack(f"{byte_order}d", data[cursor + 8:cursor + 16])[0]
            cursor += 16
            ring.append((x, y))
        rings.append(ring)
    return rings


def parse_geopackage_polygon(blob: bytes) -> list[list[list[float]]]:
    if blob[:2] != b"GP":
        raise ValueError("Unsupported geometry blob format")
    flags = blob[3]
    header_size = 8 + geopackage_envelope_size(flags)
    rings_projected = parse_wkb_polygon(blob, header_size)
    rings_lon_lat: list[list[list[float]]] = []
    for ring in rings_projected:
        transformed_ring = []
        for x, y in ring:
            lon, lat = GRID_TRANSFORMER.transform(x, y)
            transformed_ring.append([lon, lat])
        rings_lon_lat.append(transformed_ring)
    return rings_lon_lat


def load_grid_layer() -> tuple[pd.DataFrame, dict]:
    query = """
        SELECT
            cell_id,
            geom,
            lu_2018_class_simplified,
            height_mean,
            height_max,
            pt_stop_count,
            pt_access_good,
            district_name
        FROM grid_250m_lu_height_transport_rent_emvs_district
        WHERE district_name IS NOT NULL
    """
    rows = []
    features = []
    with sqlite3.connect(GRID_GPKG_PATH) as connection:
        cursor = connection.cursor()
        for cell_id, geom_blob, land_use_class, height_mean, height_max, pt_stop_count, pt_access_good, district_name in cursor.execute(query):
            polygon_coordinates = parse_geopackage_polygon(geom_blob)
            district_key = normalise_district_name(district_name)
            canonical_district_name = DISTRICT_NAME_BY_KEY.get(district_key, district_name)
            rows.append(
                {
                    "cell_id": cell_id,
                    "district_name": canonical_district_name,
                    "district_key": normalise_district_name(canonical_district_name),
                    "lu_2018_class_simplified": land_use_class,
                    "height_mean": height_mean,
                    "height_max": height_max,
                    "pt_stop_count": int(pt_stop_count),
                    "pt_access_good": bool(pt_access_good),
                }
            )
            features.append(
                {
                    "type": "Feature",
                    "id": cell_id,
                    "properties": {
                        "cell_id": cell_id,
                        "district_name": canonical_district_name,
                        "lu_2018_class_simplified": land_use_class,
                        "height_mean": height_mean,
                        "height_max": height_max,
                        "pt_stop_count": int(pt_stop_count),
                        "pt_access_good": bool(pt_access_good),
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": polygon_coordinates,
                    },
                }
            )

    return pd.DataFrame(rows), {"type": "FeatureCollection", "features": features}


def compute_polygon_area_m2(geometry: dict) -> float | None:
    if geometry.get("type") != "Polygon":
        return None

    rings = geometry.get("coordinates", [])
    if not rings:
        return None

    outer_ring = rings[0]
    if len(outer_ring) < 4:
        return None

    longitudes = [point[0] for point in outer_ring]
    latitudes = [point[1] for point in outer_ring]
    area_m2, _ = GEOD.polygon_area_perimeter(longitudes, latitudes)
    return abs(area_m2)


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


def build_district_frame() -> pd.DataFrame:
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


DISTRICT_GEOJSON = load_district_geojson()
DISTRICT_FRAME = build_district_frame()
DISTRICT_NAME_BY_KEY = {
    normalise_district_name(name): name
    for name in DISTRICT_FRAME["district_name"].drop_duplicates()
}
GRID_FRAME, GRID_GEOJSON = load_grid_layer()
MOBILITY_GRID_FRAME = GRID_FRAME[GRID_FRAME["pt_stop_count"] > 0].copy()
MOBILITY_GRID_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        feature for feature in GRID_GEOJSON["features"]
        if feature["properties"]["pt_stop_count"] > 0
    ],
}
MOBILITY_MAX_THRESHOLD = int(MOBILITY_GRID_FRAME["pt_stop_count"].max())
LAND_USE_COLOR_MAP = {
    "Herbaceous vegetation associations (natural grassland, moors...)": "#d7ead2",
    "Green urban areas": "#b8ddb3",
    "Pastures": "#e3efd6",
    "Arable land (annual crops)": "#efe7b7",
    "Continuous urban fabric (S.L. : > 80%)": "#d8c7b6",
    "Discontinuous dense urban fabric (S.L. : 50% -  80%)": "#e5d9ca",
    "Industrial, commercial, public, military and private units": "#d4d8de",
    "Other roads and associated land": "#e6e7ea",
    "Other": "#ececec",
    "Land without current use": "#e7dfd3",
    "Airports": "#d7dbe8",
}
LAND_USE_ALL_VALUE = "__all__"


def build_grid_caches(frame: pd.DataFrame, geojson: dict) -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    frame_cache: dict[str, pd.DataFrame] = {}
    geojson_cache: dict[str, dict] = {}
    for district_name in sorted(frame["district_name"].dropna().unique()):
        district_frame = frame[frame["district_name"] == district_name].copy()
        frame_cache[district_name] = district_frame
        district_cell_ids = set(district_frame["cell_id"].tolist())
        geojson_cache[district_name] = {
            "type": "FeatureCollection",
            "features": [
                feature
                for feature in geojson["features"]
                if feature["properties"]["cell_id"] in district_cell_ids
            ],
        }
    return frame_cache, geojson_cache


LAND_USE_DISTRICT_FRAME_CACHE, LAND_USE_DISTRICT_GEOJSON_CACHE = build_grid_caches(GRID_FRAME, GRID_GEOJSON)
MOBILITY_DISTRICT_FRAME_CACHE, MOBILITY_DISTRICT_GEOJSON_CACHE = build_grid_caches(MOBILITY_GRID_FRAME, MOBILITY_GRID_GEOJSON)


def build_metric_options(topic: str) -> list[dict[str, str]]:
    if topic == "height":
        return [
            {"label": "Mean building height", "value": "height_mean"},
            {"label": "Maximum building height", "value": "height_max"},
        ]
    if topic == "land_use":
        return [
            {"label": "Simplified land use", "value": "lu_2018_class_simplified"},
        ]
    if topic == "mobility":
        return [
            {"label": "Bus stops per 250m cell", "value": "pt_stop_count"},
        ]
    if topic == "housing":
        return [
            {"label": "EMVS housing total", "value": "housing_total"},
            {"label": "EMVS units per 1,000 residents", "value": "housing_per_1000_residents"},
        ]
    if topic == "green":
        return [
            {"label": "Green area total (ha)", "value": "green_area_ha"},
            {"label": "Green area per 10,000 residents", "value": "green_area_per_10000"},
        ]
    if topic == "economy":
        return [
            {"label": "Income per person", "value": "income_per_person"},
            {"label": "Household income", "value": "household_income"},
        ]
    if topic == "employment":
        return [
            {"label": "Registered unemployment", "value": "unemployment_total"},
            {"label": "Unemployment rate", "value": "unemployment_rate"},
        ]
    if topic == "vulnerability":
        return [
            {"label": "Territorial vulnerability index", "value": "vulnerability_index"},
            {"label": "Employment vulnerability index", "value": "vulnerability_employment"},
        ]
    return [
        {"label": "Population total", "value": "population_total"},
        {"label": "Population density", "value": "population_density_km2"},
    ]


def get_selected_grid_districts(district_names: list[str] | None) -> list[str]:
    return canonicalise_selected_districts(district_names)


def build_combined_grid_context(
    frame_cache: dict[str, pd.DataFrame],
    geojson_cache: dict[str, dict],
    district_names: list[str] | None,
) -> tuple[pd.DataFrame, dict]:
    selected_districts = get_selected_grid_districts(district_names)
    if not selected_districts:
        return GRID_FRAME.head(0).copy(), {"type": "FeatureCollection", "features": []}

    frame_parts = [
        frame_cache.get(district_name, GRID_FRAME.head(0).copy())
        for district_name in selected_districts
    ]
    combined_frame = pd.concat(frame_parts, ignore_index=True) if frame_parts else GRID_FRAME.head(0).copy()

    features = []
    seen_feature_ids: set[str] = set()
    for district_name in selected_districts:
        district_geojson = geojson_cache.get(district_name, {"type": "FeatureCollection", "features": []})
        for feature in district_geojson.get("features", []):
            feature_id = str(feature.get("id"))
            if feature_id in seen_feature_ids:
                continue
            seen_feature_ids.add(feature_id)
            features.append(feature)

    return combined_frame, {"type": "FeatureCollection", "features": features}


def get_land_use_class_values(district_name: str | list[str] | None) -> list[str]:
    if isinstance(district_name, list):
        district_frame, _ = build_combined_grid_context(
            LAND_USE_DISTRICT_FRAME_CACHE,
            LAND_USE_DISTRICT_GEOJSON_CACHE,
            district_name,
        )
    elif district_name is None:
        district_frame = pd.DataFrame()
    else:
        district_frame = LAND_USE_DISTRICT_FRAME_CACHE.get(district_name, pd.DataFrame())
    return sorted(district_frame["lu_2018_class_simplified"].dropna().unique().tolist())


def build_land_use_filter_options(district_name: str | list[str] | None) -> list[dict[str, str]]:
    classes = get_land_use_class_values(district_name)
    return [{"label": class_name, "value": class_name} for class_name in classes]


def normalise_land_use_filter_values(selected_values: list[str] | None, district_name: str | list[str] | None) -> list[str]:
    available_values = get_land_use_class_values(district_name)
    if not available_values:
        return []
    if selected_values is None:
        return available_values
    return [value for value in selected_values if value in available_values]


def get_land_use_filter_label(selected_values: list[str] | None, district_name: str | list[str] | None) -> str:
    available_values = get_land_use_class_values(district_name)
    normalized_values = normalise_land_use_filter_values(selected_values, district_name)
    if len(normalized_values) == len(available_values):
        return "All classes"
    if not normalized_values:
        return "No classes selected"
    if len(normalized_values) == 1:
        return normalized_values[0]
    return f"{len(normalized_values)} classes selected"


def build_land_use_filter_menu(district_name: str | list[str] | None, selected_values: list[str] | None) -> list[html.Div | html.Button]:
    normalized_values = normalise_land_use_filter_values(selected_values, district_name)
    children = []
    children.append(
        html.Div(
            [
                html.Button("Select all", id={"type": "land-use-filter-action", "value": "select_all"}, n_clicks=0, className="filter-select-action"),
                html.Button("Clear all", id={"type": "land-use-filter-action", "value": "clear_all"}, n_clicks=0, className="filter-select-action"),
            ],
            className="filter-select-actions",
        )
    )
    for option in build_land_use_filter_options(district_name):
        is_active = option["value"] in normalized_values
        class_name = "filter-select-option filter-select-option-active" if is_active else "filter-select-option"
        children.append(
            html.Button(
                [
                    html.Span(
                        className="filter-select-swatch",
                        style={"backgroundColor": LAND_USE_COLOR_MAP.get(option["value"], "#e5e7eb")},
                    ),
                    html.Span(option["label"], className="filter-select-option-label"),
                ],
                id={"type": "land-use-filter-option", "value": option["value"]},
                n_clicks=0,
                className=class_name,
            )
        )
    return children


def get_metric_label(topic: str, value: str) -> str:
    for option in build_metric_options(topic):
        if option["value"] == value:
            return option["label"]
    return build_metric_options(topic)[0]["label"]


def build_metric_menu(topic: str, selected_value: str) -> list[html.Button]:
    children = []
    for option in build_metric_options(topic):
        is_active = option["value"] == selected_value
        class_name = "filter-select-option filter-select-option-active" if is_active else "filter-select-option"
        children.append(
            html.Button(
                option["label"],
                id={"type": "metric-option", "value": option["value"]},
                n_clicks=0,
                className=class_name,
            )
        )
    return children


def format_metric_value_for_hover(topic: str, metric: str, district_row: pd.Series) -> str:
    if topic == "population":
        if metric == "population_total":
            return f"{int(district_row['population_total']):,}"
        return format_density(district_row["population_density_km2"])
    if topic == "housing":
        if metric == "housing_total":
            return f"{int(district_row['housing_total']):,}" if pd.notna(district_row["housing_total"]) else "No data"
        return format_housing_rate(district_row["housing_per_1000_residents"])
    if topic == "green":
        if metric == "green_area_ha":
            return format_float(district_row["green_area_ha"], " ha")
        return format_float(district_row["green_area_per_10000"], " ha / 10k")
    if topic == "economy":
        if metric == "income_per_person":
            return format_float(district_row["income_per_person"], " €", 0)
        return format_float(district_row["household_income"], " €", 0)
    if topic == "employment":
        if metric == "unemployment_total":
            return format_float(district_row["unemployment_total"], "", 0)
        return format_float(district_row["unemployment_rate"], "%", 2)
    if topic == "vulnerability":
        if metric == "vulnerability_index":
            return format_float(district_row["vulnerability_index"])
        return format_float(district_row["vulnerability_employment"])
    return "Not available"


def build_hover_chip(label: str, tone: str = "neutral") -> html.Span:
    return html.Span(label, className=f"map-hover-chip map-hover-chip-{tone}")


def build_hover_card(
    hover_data: dict | None,
    topic: str,
    metric: str,
    mobility_threshold: int = DEFAULT_MOBILITY_THRESHOLD,
    land_use_filter: list[str] | None = None,
) -> html.Div:
    if not hover_data or not hover_data.get("points"):
        return html.Div()

    point = hover_data["points"][0]
    district_name = resolve_click_district_name(point, DEFAULT_DISTRICT)
    canonical_district_name = DISTRICT_NAME_BY_KEY.get(normalise_district_name(district_name), district_name)
    district_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == canonical_district_name].iloc[0]

    topic_label_map = {
        "population": "Population & density",
        "housing": "Housing",
        "green": "Green",
        "economy": "Economy",
        "employment": "Employment",
        "vulnerability": "Vulnerability",
        "mobility": "Mobility",
        "land_use": "Land use / green context",
        "height": "Building height",
    }
    source_label_map = {
        "population": "Official district dataset",
        "housing": "Official district dataset",
        "green": "Official district dataset",
        "economy": "Official district dataset",
        "employment": "Official district dataset",
        "vulnerability": "Official district dataset",
        "mobility": "Processed 250m spatial layer",
        "land_use": "Processed 250m spatial layer",
        "height": "Processed 250m spatial layer",
    }
    spatial_unit_map = {
        "population": "District",
        "housing": "District",
        "green": "District",
        "economy": "District",
        "employment": "District",
        "vulnerability": "District",
        "mobility": "250m grid cell",
        "land_use": "250m grid cell",
        "height": "250m grid cell",
    }
    metric_label = get_metric_label(topic, metric)
    chips: list[html.Span] = []
    focus_label = metric_label
    focus_value = ""
    rows: list[html.Div] = []
    notice: html.Div | None = None

    if topic == "housing":
        has_data = bool(district_row["has_housing_data"])
        if not has_data:
            notice = html.Div(
                [
                    html.Div("Housing data missing", className="map-hover-notice-title"),
                    html.Div("This district has no matching EMVS housing value in the current source."),
                ],
                className="map-hover-notice",
            )
        else:
            focus_value = format_metric_value_for_hover(topic, metric, district_row)
            rows.extend(
                [
                    html.Div([html.Span("Population", className="map-hover-row-label"), html.Span(f"{int(district_row['population_total']):,}", className="map-hover-row-value")], className="map-hover-row"),
                ]
            )
    elif topic == "mobility":
        custom_data = point.get("customdata") or []
        hovered_stops = point.get("z")
        if not isinstance(hovered_stops, (int, float)) and isinstance(custom_data, (list, tuple)) and len(custom_data) > 1:
            hovered_stops = custom_data[1]
        focus_label = "Hovered cell"
        focus_value = f"{int(hovered_stops):,} stops" if hovered_stops is not None else "Not available"
        rows.extend(
            [
                html.Div([html.Span("Threshold", className="map-hover-row-label"), html.Span(f"{mobility_threshold}+", className="map-hover-row-value")], className="map-hover-row"),
            ]
        )
    elif topic == "land_use":
        custom_data = point.get("customdata") or []
        hovered_class = custom_data[1] if isinstance(custom_data, (list, tuple)) and len(custom_data) > 1 else None
        district_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(canonical_district_name, GRID_FRAME.head(0).copy())
        selected_classes = normalise_land_use_filter_values(land_use_filter, canonical_district_name)
        dominant_class = district_cells["lu_2018_class_simplified"].value_counts().idxmax() if not district_cells.empty else "Not available"
        focus_label = "Hovered class"
        focus_value = hovered_class or "Not available"
        if len(selected_classes) != len(get_land_use_class_values(canonical_district_name)):
            chips.append(build_hover_chip(f"Visible: {len(selected_classes)} classes", "accent"))
        rows.extend(
            [
                html.Div([html.Span("Dominant class", className="map-hover-row-label"), html.Span(dominant_class, className="map-hover-row-value")], className="map-hover-row"),
                html.Div([html.Span("Scope", className="map-hover-row-label"), html.Span("Selected district cells", className="map-hover-row-value")], className="map-hover-row"),
            ]
        )
    elif topic == "height":
        custom_data = point.get("customdata") or []
        mean_value = custom_data[1] if isinstance(custom_data, (list, tuple)) and len(custom_data) > 1 else None
        max_value = custom_data[2] if isinstance(custom_data, (list, tuple)) and len(custom_data) > 2 else None
        if metric == "height_mean":
            focus_label = "Hovered cell mean"
            focus_value = f"{mean_value:.1f} m" if isinstance(mean_value, (int, float)) else "Not available"
        else:
            focus_label = "Hovered cell max"
            focus_value = f"{max_value:.1f} m" if isinstance(max_value, (int, float)) else "Not available"
        rows.extend(
            [
                html.Div([html.Span("Mean height", className="map-hover-row-label"), html.Span(f"{mean_value:.1f} m" if isinstance(mean_value, (int, float)) else "Not available", className="map-hover-row-value")], className="map-hover-row"),
                html.Div([html.Span("Max height", className="map-hover-row-label"), html.Span(f"{max_value:.1f} m" if isinstance(max_value, (int, float)) else "Not available", className="map-hover-row-value")], className="map-hover-row"),
            ]
        )
    else:
        has_column_map = {
            "population": "has_population_data",
            "green": "has_green_data",
            "economy": "has_economy_data",
            "employment": "has_employment_data",
            "vulnerability": "has_vulnerability_data",
        }
        has_data = bool(district_row[has_column_map.get(topic, "has_population_data")])
        if not has_data:
            chips.append(build_hover_chip("No data", "danger"))
        focus_value = format_metric_value_for_hover(topic, metric, district_row)

    if not focus_value and notice is not None:
        focus_label = "Hovered district"
        focus_value = canonical_district_name

    metadata_rows = html.Div(
        [
            html.Div(
                [
                    html.Span("Data source", className="map-hover-meta-label"),
                    html.Span(source_label_map[topic], className="map-hover-meta-value"),
                ],
                className="map-hover-meta-row",
            ),
            html.Div(
                [
                    html.Span("Spatial unit", className="map-hover-meta-label"),
                    html.Span(spatial_unit_map[topic], className="map-hover-meta-value"),
                ],
                className="map-hover-meta-row",
            ),
        ],
        className="map-hover-meta",
    )

    return html.Div(
        [
            html.Div(
                [
                    html.Div(canonical_district_name, className="map-hover-title"),
                    html.Div(topic_label_map[topic], className="map-hover-subtitle"),
                ],
                className="map-hover-header",
            ),
            html.Div(
                [
                    html.Div(focus_label, className="map-hover-focus-label"),
                    html.Div(focus_value, className="map-hover-focus-value"),
                ],
                className="map-hover-focus",
            ),
            notice if notice is not None else None,
            metadata_rows,
            html.Div(chips, className="map-hover-chip-row") if chips else None,
            html.Div(rows, className="map-hover-rows"),
        ],
        className="map-hover-card",
    )


ICON_HOUSING = build_lucide_icon(
    '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/>'
    '<path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
)
ICON_POPULATION = build_lucide_icon(
    '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>'
    '<circle cx="9" cy="7" r="4"/>'
    '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/>'
    '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
)
ICON_GREEN = build_lucide_icon(
    '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/>'
    '<path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>'
)
ICON_LAND_USE = build_lucide_icon(
    '<rect x="3" y="3" width="18" height="18" rx="2"/>'
    '<path d="M3 12h18"/>'
    '<path d="M12 3v18"/>'
)
ICON_HEIGHT = build_lucide_icon(
    '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/>'
    '<path d="M6 12H4a2 2 0 0 0-2 2v8h4"/>'
    '<path d="M18 9h2a2 2 0 0 1 2 2v11h-4"/>'
    '<path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/>'
)
ICON_MOBILITY = build_lucide_icon(
    '<rect width="16" height="16" x="4" y="3" rx="2"/>'
    '<path d="M4 11h16"/>'
    '<path d="M12 3v8"/>'
    '<path d="m8 19-2 3"/>'
    '<path d="m18 22-2-3"/>'
    '<path d="M8 15h.01"/><path d="M16 15h.01"/>'
)
ICON_ECONOMY = build_lucide_icon(
    '<path d="M4 10h12"/>'
    '<path d="M4 14h9"/>'
    '<path d="M19 6a7.7 7.7 0 0 0-5.2-2A7.9 7.9 0 0 0 6 12c0 4.4 3.5 8 7.8 8 2 0 3.8-.8 5.2-2"/>'
)
ICON_EMPLOYMENT = build_lucide_icon(
    '<path d="M16 20V4a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v16"/>'
    '<rect width="20" height="14" x="2" y="6" rx="2"/>'
    '<path d="M12 12h.01"/>'
    '<path d="M8 12h.01"/>'
    '<path d="M16 12h.01"/>'
)
ICON_VULNERABILITY = build_lucide_icon(
    '<path d="m10.29 3.86-7.24 12.54A2 2 0 0 0 4.82 19h14.36a2 2 0 0 0 1.73-3l-7.19-12.54a2 2 0 0 0-3.43 0Z"/>'
    '<path d="M12 9v4"/>'
    '<path d="M12 17h.01"/>'
)
ICON_CLOSE = build_lucide_icon(
    '<path d="M18 6 6 18"/>'
    '<path d="m6 6 12 12"/>'
)
ICON_SEARCH = build_lucide_icon(
    '<circle cx="11" cy="11" r="7"/>'
    '<path d="m21 21-4.3-4.3"/>'
)
PIPELINE_STAGE_SOURCE_ICON = build_lucide_icon_data_uri(
    '<ellipse cx="12" cy="5" rx="6" ry="3"/>'
    '<path d="M6 5v6c0 1.7 2.7 3 6 3s6-1.3 6-3V5"/>'
    '<path d="M6 11v6c0 1.7 2.7 3 6 3s6-1.3 6-3v-6"/>',
    stroke="#22c55e",
)
PIPELINE_STAGE_CLEANING_ICON = build_lucide_icon_data_uri(
    '<path d="M4 5h16"/><path d="M7 5v14"/><path d="M17 5v14"/><path d="M10 10h4"/><path d="M9 14h6"/>',
    stroke="#22c55e",
)
PIPELINE_STAGE_PREP_ICON = build_lucide_icon_data_uri(
    '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><rect x="4" y="17" width="16" height="4" rx="1"/>',
    stroke="#111827",
)
PIPELINE_STAGE_VALIDATE_ICON = build_lucide_icon_data_uri(
    '<circle cx="12" cy="12" r="8"/><path d="m9 12 2 2 4-4"/>',
    stroke="#22c55e",
)
PIPELINE_STAGE_REPRESENT_ICON = build_lucide_icon_data_uri(
    '<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M8 20h8"/><path d="M12 17v3"/>',
    stroke="#22c55e",
)


def build_district_options(
    district_names: list[str] | None = None,
    selected_districts: list[str] | None = None,
) -> list[dict[str, str]]:
    if district_names is None:
        district_names = DISTRICT_FRAME["district_name"].drop_duplicates().tolist()
    selected_set = set(canonicalise_selected_districts(selected_districts))

    return [
        {
            "label": html.Div(
                [
                    html.Span(className="district-checkbox"),
                    html.Span(district_name, className="district-label"),
                ],
                className=(
                    "district-option-row district-option-row-selected"
                    if district_name in selected_set
                    else "district-option-row"
                ),
            ),
            "value": district_name,
        }
        for district_name in district_names
    ]


def normalise_district_sequence(selected_values: list[str] | None, limit: int | None = None) -> list[str]:
    if not selected_values:
        return []

    canonical_values: list[str] = []
    for value in selected_values:
        if not value:
            continue
        canonical_name = DISTRICT_NAME_BY_KEY.get(normalise_district_name(value), value)
        if canonical_name not in canonical_values:
            canonical_values.append(canonical_name)

    return canonical_values[:limit] if limit is not None else canonical_values


def canonicalise_selected_districts(selected_values: list[str] | None) -> list[str]:
    return normalise_district_sequence(selected_values, limit=2)


def get_primary_selected_district(selected_values: list[str] | None) -> str:
    selected_districts = canonicalise_selected_districts(selected_values)
    return selected_districts[0] if selected_districts else DEFAULT_DISTRICT


def get_secondary_selected_district(selected_values: list[str] | None) -> str | None:
    selected_districts = canonicalise_selected_districts(selected_values)
    return selected_districts[1] if len(selected_districts) > 1 else None


def get_active_map_district(selected_values: list[str] | None) -> str:
    selected_districts = canonicalise_selected_districts(selected_values)
    if not selected_districts:
        return DEFAULT_DISTRICT
    return selected_districts[-1]


def build_selection_title(selected_values: list[str] | None) -> str:
    selected_districts = canonicalise_selected_districts(selected_values)
    if not selected_districts:
        return "Madrid"
    if len(selected_districts) == 2:
        return f"{selected_districts[0]} vs {selected_districts[1]}"
    return selected_districts[0]


def get_legend_title(label: str) -> str:
    line_break_map = {
        "Population density (people/km²)": "Population density<br>(people/km²)",
        "EMVS units per 1,000 residents": "EMVS units per<br>1,000 residents",
        "Green area per 10,000 residents": "Green area per<br>10,000 residents",
        "Bus stops per 250m cell": "Bus stops per<br>250m cell",
        "Registered unemployment": "Registered<br>unemployment",
        "Territorial vulnerability index": "Territorial vulnerability<br>index",
        "Employment vulnerability index": "Employment vulnerability<br>index",
        "Mean building height": "Mean building<br>height",
        "Maximum building height": "Maximum building<br>height",
        "Building height (m)": "Building height<br>(m)",
    }
    return line_break_map.get(label, label)


def get_colorbar_title_config(label: str, font_size: int = 12) -> dict:
    return {
        "text": f'{get_legend_title(label)}<br><span style="font-size:12px;">&nbsp;</span>',
        "font": {"color": "#334155", "size": font_size},
        "side": "top",
    }


def get_colorbar_config(
    label: str,
    *,
    thickness: int,
    length: float,
    x: float = 0.02,
    font_size: int = 12,
) -> dict:
    return {
        "title": get_colorbar_title_config(label, font_size=font_size),
        "thickness": thickness,
        "len": length,
        "y": 0.5,
        "x": x,
        "xanchor": "left",
        "outlinewidth": 0,
        "bgcolor": "rgba(255,255,255,0.78)",
        "tickfont": {"color": "#64748b", "size": 11},
    }


def topic_button_class(topic: str | None, button_topic: str, is_enabled: bool) -> str:
    class_name = "topic-icon-button"
    if topic == button_topic and is_enabled:
        class_name += " topic-icon-button-active"
    if not is_enabled:
        class_name += " topic-icon-button-disabled"
    return class_name


def is_compare_selection_mode(view_mode: str | None, display_selection_mode: str | None) -> bool:
    return view_mode == "display" and display_selection_mode == "compare"


def resolve_click_district_name(point: dict, fallback: str) -> str:
    custom_data = point.get("customdata")

    if isinstance(custom_data, (list, tuple)) and custom_data:
        candidate = custom_data[0]
        if isinstance(candidate, str):
            return DISTRICT_NAME_BY_KEY.get(normalise_district_name(candidate), candidate)

    if isinstance(custom_data, str):
        return DISTRICT_NAME_BY_KEY.get(normalise_district_name(custom_data), custom_data)

    point_location = point.get("location", fallback)
    if isinstance(point_location, str):
        return DISTRICT_NAME_BY_KEY.get(normalise_district_name(point_location), point_location)

    return fallback


def build_choropleth(metric: str, topic: str):
    label_lookup = {
        "population_total": "Population (2024)",
        "population_density_km2": "Population density (people/km²)",
        "housing_total": "EMVS housing total",
        "housing_per_1000_residents": "EMVS units per 1,000 residents",
        "green_area_ha": "Green area (ha)",
        "green_area_per_10000": "Green area per 10,000 residents",
        "income_per_person": "Income per person",
        "household_income": "Household income",
        "pt_stop_count": "Bus stops per 250m cell",
        "unemployment_total": "Registered unemployment",
        "unemployment_rate": "Unemployment rate",
        "vulnerability_index": "Territorial vulnerability index",
        "vulnerability_employment": "Employment vulnerability index",
    }
    legend_title = label_lookup[metric]

    figure_frame = DISTRICT_FRAME.copy()
    display_metric = f"{metric}_display"
    figure_frame[display_metric] = figure_frame[metric].fillna(-1)
    availability_column_map = {
        "population": "has_population_data",
        "housing": "has_housing_data",
        "green": "has_green_data",
        "economy": "has_economy_data",
        "employment": "has_employment_data",
        "vulnerability": "has_vulnerability_data",
    }
    availability_column = availability_column_map[topic]
    max_value = figure_frame[metric].max()
    if pd.isna(max_value):
        max_value = 1

    figure = px.choropleth(
        figure_frame,
        geojson=DISTRICT_GEOJSON,
        locations="district_name",
        featureidkey="id",
        color=display_metric,
        hover_name="district_name",
        hover_data={
            "district_code": True,
            "population_total": ":,",
            "population_density_km2": ":,",
            "housing_total": ":,",
            "housing_per_1000_residents": ":.2f",
            "green_area_ha": ":.2f",
            "green_area_per_10000": ":.2f",
            "income_per_person": ":.0f",
            "household_income": ":.0f",
            "unemployment_total": ":.0f",
            "unemployment_rate": ":.2f",
            "vulnerability_index": ":.2f",
            "vulnerability_employment": ":.2f",
            "area_km2": ":.2f",
            availability_column: True,
            "district_name": False,
            display_metric: False,
        },
        color_continuous_scale=[
            [0.0, "#d1d5db"],
            [0.000001, "#d1d5db"],
            [0.0000011, "#f7fcb9"],
            [0.35, "#7fcdbb"],
            [0.7, "#2c7fb8"],
            [1.0, "#253494"],
        ],
        range_color=(-1, max_value),
        labels={display_metric: label_lookup[metric]},
    )

    figure.update_geos(fitbounds="locations", visible=False)
    figure.update_traces(hoverinfo="none", hovertemplate=None)
    figure.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="white",
        plot_bgcolor="white",
        coloraxis_colorbar={
            **get_colorbar_config(
                legend_title,
                thickness=16,
                length=0.78,
            ),
            "bgcolor": "rgba(255,255,255,0.82)",
        },
        uirevision=MAP_UIREVISION,
    )
    figure.update_geos(
        fitbounds="locations",
        visible=False,
        projection_type="mercator",
        domain={"x": [0.1, 0.98], "y": [0.02, 0.98]},
    )
    unavailable = figure_frame[~figure_frame[availability_column]].dropna(subset=["centroid_lon", "centroid_lat"])
    if not unavailable.empty:
        figure.add_scattergeo(
            lon=unavailable["centroid_lon"],
            lat=unavailable["centroid_lat"],
            text=["!"] * len(unavailable),
            mode="text",
            textfont={"size": 18, "color": "#4b5563"},
            hoverinfo="skip",
            showlegend=False,
        )
    return figure


def add_selected_district_outlines(figure, district_names: list[str] | None):
    selected_districts = canonicalise_selected_districts(district_names)
    outline_styles = [
        {"color": "#111827", "width": 2.8},
        {"color": "#dc2626", "width": 2.2},
    ]

    for index, district_name in enumerate(reversed(selected_districts)):
        selected_features = [
            feature for feature in DISTRICT_GEOJSON["features"]
            if feature["id"] == district_name
        ]
        style = outline_styles[min(index, len(outline_styles) - 1)]
        for feature in selected_features:
            for ring in feature["geometry"]["coordinates"]:
                lon = [point[0] for point in ring]
                lat = [point[1] for point in ring]
                figure.add_trace(
                    go.Scattergeo(
                        lon=lon,
                        lat=lat,
                        mode="lines",
                        line=style,
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )
    return figure


def add_hovered_district_outline(figure, hovered_district_name: str | None, selected_district_names: list[str] | None):
    if not hovered_district_name:
        return figure

    canonical_name = DISTRICT_NAME_BY_KEY.get(normalise_district_name(hovered_district_name), hovered_district_name)
    if canonical_name in canonicalise_selected_districts(selected_district_names):
        return figure

    hovered_features = [
        feature for feature in DISTRICT_GEOJSON["features"]
        if feature["id"] == canonical_name
    ]
    for feature in hovered_features:
        for ring in feature["geometry"]["coordinates"]:
            lon = [point[0] for point in ring]
            lat = [point[1] for point in ring]
            figure.add_trace(
                go.Scattergeo(
                    lon=lon,
                    lat=lat,
                    mode="lines",
                    line={"color": "rgba(100,116,139,0.68)", "width": 1.6},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
    return figure


def build_grid_base_figure():
    base_figure = go.Figure()
    base_figure.add_trace(
        go.Choropleth(
            geojson=DISTRICT_GEOJSON,
            locations=DISTRICT_FRAME["district_name"],
            z=[1] * len(DISTRICT_FRAME),
            featureidkey="id",
            customdata=DISTRICT_FRAME["district_name"],
            colorscale=[[0, "rgba(148,163,184,0.03)"], [1, "rgba(148,163,184,0.03)"]],
            showscale=False,
            marker_line_color="rgba(100,116,139,0.22)",
            marker_line_width=0.85,
            hoverinfo="none",
            hovertemplate=None,
        )
    )
    base_figure.update_geos(
        fitbounds="locations",
        visible=False,
        projection_type="mercator",
        domain={"x": [0.1, 0.98], "y": [0.02, 0.98]},
    )
    return base_figure


def build_mobility_map(threshold: int, district_names: list[str] | None):
    district_frame, district_geojson = build_combined_grid_context(
        MOBILITY_DISTRICT_FRAME_CACHE,
        MOBILITY_DISTRICT_GEOJSON_CACHE,
        district_names,
    )
    filtered = district_frame[district_frame["pt_stop_count"] >= threshold].copy()
    if filtered.empty:
        filtered = district_frame.head(0).copy()

    base_figure = build_grid_base_figure()

    grid_figure = px.choropleth(
        filtered,
        geojson=district_geojson,
        locations="cell_id",
        featureidkey="id",
        color="pt_stop_count",
        hover_name="district_name",
        hover_data={
            "district_name": False,
            "pt_stop_count": True,
            "pt_access_good": True,
            "cell_id": False,
        },
        custom_data=["district_name", "pt_stop_count"],
        color_continuous_scale=[
            [0.0, "#f3f7fb"],
            [0.35, "#dce8f5"],
            [0.7, "#b9cde3"],
            [1.0, "#8ea9c6"],
        ],
        labels={"pt_stop_count": "Bus stops per 250m cell"},
    )
    grid_figure.update_traces(
        marker_line_width=0.15,
        marker_line_color="rgba(255,255,255,0.28)",
        hoverinfo="none",
        hovertemplate=None,
    )
    for trace in grid_figure.data:
        base_figure.add_trace(trace)

    base_figure.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="white",
        plot_bgcolor="white",
        coloraxis={
            "colorscale": [
                [0.0, "#dbeafe"],
                [0.35, "#93c5fd"],
                [0.7, "#3b82f6"],
                [1.0, "#1d4ed8"],
            ],
        },
        coloraxis_colorbar={
            **get_colorbar_config(
                "Bus stops per 250m cell",
                thickness=14,
                length=0.78,
            ),
        },
        uirevision=MAP_UIREVISION,
    )
    return base_figure


def build_land_use_map(district_names: list[str] | None, selected_classes: list[str] | None = None):
    district_frame, district_geojson = build_combined_grid_context(
        LAND_USE_DISTRICT_FRAME_CACHE,
        LAND_USE_DISTRICT_GEOJSON_CACHE,
        district_names,
    )
    filtered = district_frame.copy()
    selected_classes = normalise_land_use_filter_values(selected_classes, district_names)
    if len(selected_classes) != len(get_land_use_class_values(district_names)):
        filtered = filtered[filtered["lu_2018_class_simplified"].isin(selected_classes)].copy()
    base_figure = build_grid_base_figure()
    figure = px.choropleth(
        filtered,
        geojson=district_geojson,
        locations="cell_id",
        featureidkey="id",
        color="lu_2018_class_simplified",
        hover_name="district_name",
        hover_data={
            "district_name": False,
            "lu_2018_class_simplified": True,
            "cell_id": False,
        },
        custom_data=["district_name", "lu_2018_class_simplified"],
        color_discrete_map=LAND_USE_COLOR_MAP,
        labels={"lu_2018_class_simplified": "Simplified land use"},
    )
    figure.update_traces(
        marker_line_width=0.08,
        marker_line_color="rgba(255,255,255,0.22)",
        hoverinfo="none",
        hovertemplate=None,
        showlegend=False,
    )
    for trace in figure.data:
        base_figure.add_trace(trace)
    base_figure.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="white",
        plot_bgcolor="white",
        uirevision=MAP_UIREVISION,
    )
    return base_figure


def build_height_map(district_names: list[str] | None, metric: str):
    district_frame, district_geojson = build_combined_grid_context(
        LAND_USE_DISTRICT_FRAME_CACHE,
        LAND_USE_DISTRICT_GEOJSON_CACHE,
        district_names,
    )
    filtered = district_frame[district_frame[metric].notna()].copy()
    base_figure = build_grid_base_figure()
    figure = px.choropleth(
        filtered,
        geojson=district_geojson,
        locations="cell_id",
        featureidkey="id",
        color=metric,
        hover_name="district_name",
        hover_data={
            "district_name": False,
            "height_mean": ":.1f",
            "height_max": ":.1f",
            "cell_id": False,
        },
        custom_data=["district_name", "height_mean", "height_max"],
        color_continuous_scale=[
            [0.0, "#f6efe8"],
            [0.35, "#e9d6c6"],
            [0.7, "#d1ae93"],
            [1.0, "#a76f52"],
        ],
        labels={
            "height_mean": "Mean building height",
            "height_max": "Maximum building height",
        },
    )
    hover_line = "Mean height: %{z:.1f} m" if metric == "height_mean" else "Maximum height: %{z:.1f} m"
    figure.update_traces(
        marker_line_width=0.08,
        marker_line_color="rgba(255,255,255,0.22)",
        hoverinfo="none",
        hovertemplate=None,
    )
    for trace in figure.data:
        base_figure.add_trace(trace)
    base_figure.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="white",
        plot_bgcolor="white",
        coloraxis_colorbar={
            **get_colorbar_config(
                "Building height (m)",
                thickness=14,
                length=0.78,
            ),
        },
        uirevision=MAP_UIREVISION,
    )
    return base_figure


def format_density(value: float) -> str:
    if pd.isna(value):
        return "Not available"
    return f"{int(value):,} people/km²"


def format_housing_rate(value: float) -> str:
    if pd.isna(value):
        return "Not available"
    return f"{value:.2f} units / 1,000 residents"


def format_float(value: float, suffix: str = "", decimals: int = 2) -> str:
    if pd.isna(value):
        return "Not available"
    return f"{value:,.{decimals}f}{suffix}"


def build_info_panel(
    district_name: str,
    metric: str,
    topic: str,
    mobility_threshold: int = DEFAULT_MOBILITY_THRESHOLD,
    land_use_filter: list[str] | None = None,
) -> html.Div:
    canonical_district_name = DISTRICT_NAME_BY_KEY.get(normalise_district_name(district_name), district_name)
    district_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == canonical_district_name].iloc[0]
    district_name = canonical_district_name
    sources_text = "Madrid district boundaries"
    reference_date = "Not available yet"
    if topic == "land_use":
        district_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(district_name, GRID_FRAME.head(0).copy()).copy()
        visible_cells = district_cells
        selected_classes = normalise_land_use_filter_values(land_use_filter, district_name)
        available_classes = get_land_use_class_values(district_name)
        if len(selected_classes) != len(available_classes):
            visible_cells = district_cells[district_cells["lu_2018_class_simplified"].isin(selected_classes)].copy()
        dominant_class = (
            district_cells["lu_2018_class_simplified"].value_counts().idxmax()
            if not district_cells.empty
            else "Not available"
        )
        green_like_classes = {
            "Green urban areas",
            "Herbaceous vegetation associations (natural grassland, moors...)",
            "Pastures",
            "Arable land (annual crops)",
        }
        green_like_share = (
            district_cells["lu_2018_class_simplified"].isin(green_like_classes).mean() * 100
            if not district_cells.empty
            else 0
        )
        topic_label = "Land use / green context"
        filtered_view = len(selected_classes) != len(available_classes)
        metric_label = "Visible land-use selection" if filtered_view else "Dominant land-use class"
        metric_value = f"{len(selected_classes)} classes selected" if filtered_view else dominant_class
        key_finding = (
            (
                f"{district_name} currently shows {len(visible_cells):,} visible cells across "
                f"{len(selected_classes)} selected land-use classes."
            )
            if filtered_view
            else (
                f"{district_name} is dominated by {dominant_class.lower()} in the research-derived land-use grid, "
                f"with {green_like_share:.0f}% of cells falling into green or open-land classes."
            )
        )
        meaning_text = (
            "This view shows how 250m cells in the selected district are classified in the simplified Urban Atlas land-use layer. "
            "It gives spatial context rather than a single district score."
        )
        production_text = (
            "Land-use classes were attached to the 250m research grid and rendered directly as a categorical spatial layer. "
            "The right panel summarizes the selected district by its dominant class and broad green/open-land share."
        )
        caveat_line = "This is a simplified research-derived land-use layer and should be read as spatial context, not parcel-level zoning."
        sources_text = "Research-derived combined grid layer (Urban Atlas based) + Madrid district boundaries"
        reference_date = "Urban Atlas 2018 within research-derived combined grid layer"
    elif topic == "height":
        district_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(district_name, GRID_FRAME.head(0).copy()).copy()
        height_cells = district_cells[district_cells["height_mean"].notna()].copy()
        mean_height = height_cells["height_mean"].mean() if not height_cells.empty else None
        max_height = height_cells["height_max"].max() if not height_cells.empty else None
        topic_label = "Building height"
        metric_label = "Mean building height" if metric == "height_mean" else "Maximum building height"
        metric_value = (
            "No data available yet"
            if height_cells.empty
            else (f"{mean_height:.1f} m" if metric == "height_mean" else f"{max_height:.1f} m")
        )
        key_finding = (
            f"{district_name} does not have building-height cells available yet in this research-derived layer."
            if height_cells.empty
            else (
                f"{district_name} has an average building height of {mean_height:.1f} m "
                f"and a maximum observed cell height of {max_height:.1f} m."
            )
        )
        meaning_text = (
            "This view shows building-height variation across 250m cells inside the selected district. "
            "It works as spatial evidence for urban form rather than an administrative district indicator."
        )
        production_text = (
            "Building-height values were attached to the research grid and rendered directly as a continuous spatial layer. "
            "The right panel summarizes the selected district using the cells that have height information."
        )
        caveat_line = "Height values are grid-derived research outputs and should be read as generalized building-height context, not exact individual-building measurements."
        sources_text = "Research-derived combined grid layer (height raster based) + Madrid district boundaries"
        reference_date = "Research-derived combined grid layer"
    elif topic == "mobility":
        district_cells = MOBILITY_GRID_FRAME.loc[MOBILITY_GRID_FRAME["district_name"] == district_name].copy()
        cells_above_threshold = district_cells.loc[district_cells["pt_stop_count"] >= mobility_threshold]
        has_data = not district_cells.empty
        topic_label = "Mobility"
        metric_label = "Bus stops per 250m cell"
        if has_data:
            metric_value = f"{len(cells_above_threshold):,} cells at threshold"
            key_finding = (
                f"{district_name} has {len(cells_above_threshold):,} grid cells with at least "
                f"{mobility_threshold} bus stops in the research-derived mobility layer."
            )
            meaning_text = (
                "This view uses 250m grid cells to show where public transport stops concentrate within and across districts. "
                "It works as spatial evidence rather than a district-native administrative indicator."
            )
            production_text = (
                "Bus-stop counts were attached to 250m grid cells in the research notebook workflow and are rendered directly as a spatial evidence layer. "
                "The right panel remains district-first by summarizing the selected district's cells."
            )
            caveat_line = "This is a research-derived grid layer; it shows stop concentration by cell, not full transit service quality."
            reference_date = "Research-derived grid layer based on notebook inputs"
        else:
            metric_value = "No data available yet"
            key_finding = f"{district_name} does not have mobility grid data available yet for this MVP slice."
            meaning_text = "This district remains visible, but the current research-derived mobility layer did not yield matching grid cells yet."
            production_text = "The district geometry comes from the Madrid boundary file. The mobility grid layer did not yield matching cells for this district."
            caveat_line = "Research-derived spatial layers may have partial coverage depending on the notebook output."
        sources_text = "Research-derived combined grid layer + Madrid district boundaries"
    elif topic == "housing":
        has_data = bool(district_row["has_housing_data"])
        topic_label = "Housing"
        metric_label = "EMVS housing total" if metric == "housing_total" else "EMVS units per 1,000 residents"
        metric_value = (
            "No data available yet"
            if not has_data
            else (
                f"{int(district_row['housing_total']):,}"
                if metric == "housing_total"
                else format_housing_rate(district_row["housing_per_1000_residents"])
            )
        )
        key_finding = (
            f"{district_name} does not have housing data available yet for this MVP slice."
            if not has_data
            else (
                f"{district_name} has {int(district_row['housing_total']):,} EMVS housing allocations in the current source, "
                f"equivalent to {format_housing_rate(district_row['housing_per_1000_residents'])}."
            )
        )
        meaning_text = (
            "This district remains visible on the map so missing topic coverage is explicit instead of hidden."
            if not has_data
            else (
                "This view shows district-level public housing allocation in the EMVS source. It is not a full housing market indicator, "
                "but it gives a transparent public-housing-oriented comparison across districts."
            )
        )
        production_text = (
            "The district geometry comes from the Madrid boundary file. The current housing dataset did not yield a matching value yet, so the district is shown as unavailable."
            if not has_data
            else (
                "Housing values come from the local EMVS housing CSV. The per-1,000-residents rate is derived by combining the EMVS total with district population totals."
            )
        )
        reference_date = "EMVS adjudications from 1/06/2015 to 30/04/2023" if has_data else "Not available yet"
        caveat_line = "EMVS values describe public housing allocation, not total housing supply or affordability."
        sources_text = "EMVS housing CSV + Madrid Population API + Madrid district boundaries"
    elif topic == "green":
        has_data = bool(district_row["has_green_data"])
        topic_label = "Green"
        metric_label = "Green area total (ha)" if metric == "green_area_ha" else "Green area per 10,000 residents"
        metric_value = (
            "No data available yet"
            if not has_data
            else (
                format_float(district_row["green_area_ha"], " ha")
                if metric == "green_area_ha"
                else format_float(district_row["green_area_per_10000"], " ha / 10,000 residents")
            )
        )
        key_finding = (
            f"{district_name} does not have green-space data available yet for this MVP slice."
            if not has_data
            else (
                f"{district_name} has {format_float(district_row['green_area_ha'], ' ha')} of district green space, "
                f"equivalent to {format_float(district_row['green_area_per_10000'], ' ha / 10,000 residents')}."
            )
        )
        meaning_text = (
            "This district remains visible on the map so missing topic coverage is explicit instead of hidden."
            if not has_data
            else "This view shows district-level green-space provision from the municipal indicator panel."
        )
        production_text = (
            "The district geometry comes from the Madrid boundary file. The current green-space dataset did not yield a matching value yet, so the district is shown as unavailable."
            if not has_data
            else "Green-space values come from the Madrid district indicator panel and are displayed at district level."
        )
        reference_date = f"Indicator year {int(district_row['green_area_per_10000_year'])}" if has_data and not pd.isna(district_row.get("green_area_per_10000_year")) else "Not available yet"
        caveat_line = "This is district-level green-space provision, not direct park accessibility from a specific address."
        sources_text = "Madrid district indicator panel + Madrid district boundaries"
    elif topic == "economy":
        has_data = bool(district_row["has_economy_data"])
        topic_label = "Economy"
        metric_label = "Income per person" if metric == "income_per_person" else "Household income"
        metric_value = (
            "No data available yet"
            if not has_data
            else (
                format_float(district_row["income_per_person"], " €", 0)
                if metric == "income_per_person"
                else format_float(district_row["household_income"], " €", 0)
            )
        )
        key_finding = (
            f"{district_name} does not have economy data available yet for this MVP slice."
            if not has_data
            else (
                f"{district_name} records {format_float(district_row['income_per_person'], ' €', 0)} income per person "
                f"and {format_float(district_row['household_income'], ' €', 0)} household income in the current panel."
            )
        )
        meaning_text = (
            "This district remains visible on the map so missing topic coverage is explicit instead of hidden."
            if not has_data
            else "This view adds district-level income context from the municipal indicator panel."
        )
        production_text = (
            "The district geometry comes from the Madrid boundary file. The current economy dataset did not yield a matching value yet, so the district is shown as unavailable."
            if not has_data
            else "Income values come from the Madrid district indicator panel and are displayed at district level."
        )
        reference_date = f"Indicator year {int(district_row['income_per_person_year'])}" if has_data and not pd.isna(district_row.get("income_per_person_year")) else "Not available yet"
        caveat_line = "These are panel indicators and should be read as district context, not household-level distributions."
        sources_text = "Madrid district indicator panel + Madrid district boundaries"
    elif topic == "employment":
        has_data = bool(district_row["has_employment_data"])
        topic_label = "Employment"
        metric_label = "Registered unemployment" if metric == "unemployment_total" else "Unemployment rate"
        metric_value = (
            "No data available yet"
            if not has_data
            else (
                format_float(district_row["unemployment_total"], "", 0)
                if metric == "unemployment_total"
                else format_float(district_row["unemployment_rate"], "%", 2)
            )
        )
        key_finding = (
            f"{district_name} does not have employment data available yet for this MVP slice."
            if not has_data
            else (
                f"{district_name} records {format_float(district_row['unemployment_total'], '', 0)} registered unemployed people "
                f"and an unemployment rate of {format_float(district_row['unemployment_rate'], '%', 2)}."
            )
        )
        meaning_text = (
            "This district remains visible on the map so missing topic coverage is explicit instead of hidden."
            if not has_data
            else "This view adds district-level unemployment context from the municipal indicator panel."
        )
        production_text = (
            "The district geometry comes from the Madrid boundary file. The current employment dataset did not yield a matching value yet, so the district is shown as unavailable."
            if not has_data
            else "Employment values come from the Madrid district indicator panel and are displayed at district level."
        )
        reference_date = f"Indicator year {int(district_row['unemployment_rate_year'])}" if has_data and not pd.isna(district_row.get("unemployment_rate_year")) else "Not available yet"
        caveat_line = "These values reflect registered unemployment indicators, not the full labor market picture."
        sources_text = "Madrid district indicator panel + Madrid district boundaries"
    elif topic == "vulnerability":
        has_data = bool(district_row["has_vulnerability_data"])
        topic_label = "Vulnerability"
        metric_label = "Territorial vulnerability index" if metric == "vulnerability_index" else "Employment vulnerability index"
        metric_value = (
            "No data available yet"
            if not has_data
            else (
                format_float(district_row["vulnerability_index"])
                if metric == "vulnerability_index"
                else format_float(district_row["vulnerability_employment"])
            )
        )
        key_finding = (
            f"{district_name} does not have vulnerability data available yet for this MVP slice."
            if not has_data
            else (
                f"{district_name} shows a territorial vulnerability index of {format_float(district_row['vulnerability_index'])} "
                f"and an employment vulnerability index of {format_float(district_row['vulnerability_employment'])}."
            )
        )
        meaning_text = (
            "This district remains visible on the map so missing topic coverage is explicit instead of hidden."
            if not has_data
            else "This view adds district-level vulnerability context from the municipal indicator panel."
        )
        production_text = (
            "The district geometry comes from the Madrid boundary file. The current vulnerability dataset did not yield a matching value yet, so the district is shown as unavailable."
            if not has_data
            else "Vulnerability values come from the Madrid district indicator panel and are displayed at district level."
        )
        reference_date = f"Indicator year {int(district_row['vulnerability_index_year'])}" if has_data and not pd.isna(district_row.get("vulnerability_index_year")) else "Not available yet"
        caveat_line = "These are composite municipal panel indices and should be read as comparative context rather than direct causal explanations."
        sources_text = "Madrid district indicator panel + Madrid district boundaries"
    else:
        has_data = bool(district_row["has_population_data"])
        topic_label = "Population & density"
        metric_label = "Population total" if metric == "population_total" else "Population density"
        metric_value = (
            "No data available yet"
            if not has_data
            else (
                f"{int(district_row['population_total']):,}"
                if metric == "population_total"
                else format_density(district_row["population_density_km2"])
            )
        )
        density_text = format_density(district_row["population_density_km2"]) if has_data else "Not available yet"
        reference_date = district_row["reference_date"] if has_data else "Not available yet"
        key_finding = (
            f"{district_name} does not have data available yet for this first MVP slice."
            if not has_data
            else (
                f"{district_name} has {district_row['population_total']:,} residents and a population density "
                f"of {density_text}."
            )
        )
        meaning_text = (
            "This district remains visible on the map so missing topic coverage is explicit instead of hidden."
            if not has_data
            else (
                "This first MVP view shows district-scale demographic intensity. It is a district-native "
                "indicator, so the values are directly comparable across Madrid districts."
            )
        )
        production_text = (
            "The district geometry comes from the Madrid boundary file. The current topic dataset did not yield a matching value yet, so the district is shown as unavailable."
            if not has_data
            else (
                "Population totals come from the Madrid population API. Density is derived by combining "
                "district population totals with district boundary areas from the Madrid boundary file."
            )
        )
        caveat_line = "Density is derived from administrative district area, not built-up area."
        sources_text = "Madrid Population API + Madrid district boundaries"

    return html.Div(
        [
            html.H2(district_name, className="panel-title"),
            html.P(topic_label, className="panel-subtitle"),
            html.Div(
                [
                    html.H3(metric_value, className="metric-value"),
                    html.P(metric_label, className="metric-label"),
                ],
                className="metric-card",
            ),
            html.Div(
                [
                    html.H4("Key finding"),
                    html.P(key_finding),
                    html.H4("What this means"),
                    html.P(meaning_text),
                    html.H4("How this was produced"),
                    html.P(production_text),
                    html.H4("Assumptions / caveats"),
                    html.Ul(
                        [
                            html.Li("The current view uses district totals only, not barrio detail."),
                            html.Li(caveat_line),
                            html.Li("Districts without matching topic data are shown in grey with an icon overlay."),
                        ]
                    ),
                    html.H4("Sources"),
                    html.P(sources_text),
                    html.H4("Reference date"),
                    html.P(str(reference_date)),
                ],
                className="panel-body",
            ),
        ],
        className="right-panel-content",
    )


def build_topic_prompt_panel(district_name: str, is_comparison: bool = False):
    guidance_text = (
        "Choose a shared topic to open both district sidebars and compare them with the same lens."
        if is_comparison
        else "Choose a topic to open this district's explanation and metric summary."
    )
    return html.Div(
        [
            html.H2(district_name, className="panel-title"),
            html.P("District selected", className="panel-subtitle"),
            html.Div(
                [
                    html.H3("Select a topic", className="metric-value"),
                    html.P("Topic picker unlocked", className="metric-label"),
                ],
                className="metric-card",
            ),
            html.Div(
                [
                    html.H4("Next step"),
                    html.P(guidance_text),
                    html.H4("Why this is hidden"),
                    html.P(
                        "Topic views stay locked until a district is selected so the dashboard keeps a clear district-first flow."
                    ),
                ],
                className="panel-body",
            ),
        ],
        className="right-panel-content",
    )


def build_district_sidebar(panel_children, panel_position: int):
    return html.Div(
        panel_children,
        className=f"district-sidebar district-sidebar-{panel_position}",
    )


def build_map_info_bubble(message: str):
    return html.Div(
        [
            html.Button(
                "i",
                className="inline-info-chip map-inline-info-chip",
                tabIndex=-1,
            ),
            html.Div(
                [
                    html.Div("Comparison note", className="inline-info-bubble-title"),
                    html.Div(message),
                ],
                className="inline-info-bubble map-inline-info-bubble",
            ),
        ],
        className="inline-info-wrap map-selection-info-wrap",
    )


def build_toolbar_info_bubble(message: str, title: str = "Note"):
    return html.Div(
        [
            html.Button(
                "i",
                className="inline-info-chip map-inline-info-chip",
                tabIndex=-1,
            ),
            html.Div(
                [
                    html.Div(title, className="inline-info-bubble-title"),
                    html.Div(message),
                ],
                className="inline-info-bubble map-inline-info-bubble",
            ),
        ],
        className="inline-info-wrap toolbar-info-wrap",
    )


PIPELINE_STAGES = [
    {
        "id": "source_intake",
        "title": "Source intake",
        "subtitle": "Collect topic inputs",
        "status": "Complete",
        "icon": PIPELINE_STAGE_SOURCE_ICON,
    },
    {
        "id": "cleaning",
        "title": "Cleaning & harmonisation",
        "subtitle": "Standardise formats",
        "status": "Complete",
        "icon": PIPELINE_STAGE_CLEANING_ICON,
    },
    {
        "id": "topic_preparation",
        "title": "Topic preparation",
        "subtitle": "Prepare view-ready metrics",
        "status": "Active",
        "icon": PIPELINE_STAGE_PREP_ICON,
    },
    {
        "id": "validation",
        "title": "Validation & uncertainty",
        "subtitle": "Check quality & caveats",
        "status": "Complete",
        "icon": PIPELINE_STAGE_VALIDATE_ICON,
    },
    {
        "id": "representation",
        "title": "Representation",
        "subtitle": "Display in dashboard",
        "status": "Complete",
        "icon": PIPELINE_STAGE_REPRESENT_ICON,
    },
]


def get_pipeline_stage(stage_id: str | None) -> dict:
    for stage in PIPELINE_STAGES:
        if stage["id"] == stage_id:
            return stage
    return next(stage for stage in PIPELINE_STAGES if stage["id"] == DEFAULT_PIPELINE_STAGE)


def get_pipeline_topic_label(topic: str | None) -> str:
    label_map = {
        "population": "Population & density",
        "housing": "Housing",
        "green": "Green",
        "economy": "Economy",
        "employment": "Employment",
        "vulnerability": "Vulnerability",
        "mobility": "Mobility",
        "land_use": "Land use / green context",
        "height": "Building height",
    }
    return label_map.get(topic or "", "Topic not selected")


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    color = hex_color.lstrip("#")
    return tuple(int(color[index:index + 2], 16) for index in (0, 2, 4))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def interpolate_hex_color(start_color: str, end_color: str, fraction: float) -> str:
    start_rgb = hex_to_rgb(start_color)
    end_rgb = hex_to_rgb(end_color)
    bounded_fraction = max(0.0, min(1.0, fraction))
    interpolated = tuple(
        round(start + (end - start) * bounded_fraction)
        for start, end in zip(start_rgb, end_rgb)
    )
    return rgb_to_hex(interpolated)


def build_preview_metric_fill(topic: str | None, metric: str | None, district_name: str) -> str:
    district_match = DISTRICT_FRAME[DISTRICT_FRAME["district_name"] == district_name]
    if district_match.empty:
        return "#eef2f7"

    district_row = district_match.iloc[0]
    metric_by_topic = {
        "population": metric or "population_total",
        "housing": metric or "housing_total",
        "green": metric or "green_area_per_10000",
        "economy": metric or "income_per_person",
        "employment": metric or "unemployment_rate",
        "vulnerability": metric or "vulnerability_index",
    }
    default_metric = metric_by_topic.get(topic or "")
    if not default_metric or default_metric not in DISTRICT_FRAME.columns:
        return "#eef2f7"

    value = district_row.get(default_metric)
    if pd.isna(value):
        return "#e5e7eb"

    max_value = DISTRICT_FRAME[default_metric].max()
    if pd.isna(max_value) or max_value == 0:
        return "#eef2f7"

    fraction = float(value) / float(max_value)
    color_ranges = {
        "population": ("#dbeafe", "#1d4ed8"),
        "housing": ("#efe7ff", "#7c3aed"),
        "green": ("#dcfce7", "#16a34a"),
        "economy": ("#fef3c7", "#d97706"),
        "employment": ("#fee2e2", "#dc2626"),
        "vulnerability": ("#fee2e2", "#b91c1c"),
    }
    start_color, end_color = color_ranges.get(topic or "", ("#eef2f7", "#94a3b8"))
    return interpolate_hex_color(start_color, end_color, fraction)


def build_district_preview_svg(
    topic: str | None,
    district_name: str,
    metric: str | None = None,
    mobility_threshold: int = DEFAULT_MOBILITY_THRESHOLD,
    land_use_filter_values: list[str] | None = None,
) -> str:
    feature = next((feature for feature in DISTRICT_GEOJSON["features"] if feature["id"] == district_name), None)
    if not feature:
        fallback = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">'
            '<rect x="16" y="16" width="88" height="88" rx="22" fill="#ffffff" stroke="#d9e1ea" />'
            "</svg>"
        )
        return f"data:image/svg+xml;utf8,{quote(fallback)}"

    ring = feature["geometry"]["coordinates"][0]
    xs = [point[0] for point in ring]
    ys = [point[1] for point in ring]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max(max_x - min_x, 1e-6)
    height = max(max_y - min_y, 1e-6)
    preview_size = 84
    preview_origin = 18
    scale = min(preview_size / width, preview_size / height)
    offset_x = preview_origin + (preview_size - width * scale) / 2
    offset_y = preview_origin - 8 + (preview_size - height * scale) / 2

    def transform_ring_points(source_ring: list[list[float]]) -> str:
        transformed_points = []
        for lon, lat in source_ring:
            x = offset_x + (lon - min_x) * scale
            y = 98 - (offset_y + (lat - min_y) * scale)
            transformed_points.append(f"{x:.2f},{y:.2f}")
        return " ".join(transformed_points)

    polygon = transform_ring_points(ring)
    svg_parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">',
        '<rect x="10" y="10" width="100" height="100" rx="20" fill="#ffffff"/>',
    ]

    if topic in {"mobility", "land_use", "height"}:
        if topic == "mobility":
            district_frame = MOBILITY_DISTRICT_FRAME_CACHE.get(district_name, pd.DataFrame())
            district_geojson = MOBILITY_DISTRICT_GEOJSON_CACHE.get(district_name, {"features": []})
        else:
            district_frame = LAND_USE_DISTRICT_FRAME_CACHE.get(district_name, pd.DataFrame())
            district_geojson = LAND_USE_DISTRICT_GEOJSON_CACHE.get(district_name, {"features": []})

        feature_map = {feature["properties"]["cell_id"]: feature for feature in district_geojson.get("features", [])}

        if topic == "mobility":
            filtered_frame = district_frame[district_frame["pt_stop_count"] >= mobility_threshold]
        elif topic == "land_use":
            selected_classes = normalise_land_use_filter_values(land_use_filter_values, district_name)
            filtered_frame = district_frame[
                district_frame["lu_2018_class_simplified"].isin(selected_classes)
            ] if selected_classes else district_frame.head(0)
        else:
            preview_metric = metric if metric in {"height_mean", "height_max"} else "height_mean"
            filtered_frame = district_frame[district_frame[preview_metric].notna()]

        svg_parts.append(
            f'<polygon points="{polygon}" fill="#f8fafc" stroke="#d9e1ea" stroke-width="1.6" />'
        )

        for _, row in filtered_frame.iterrows():
            cell_feature = feature_map.get(row["cell_id"])
            if not cell_feature:
                continue
            cell_ring = cell_feature["geometry"]["coordinates"][0]
            cell_points = transform_ring_points(cell_ring)
            if topic == "mobility":
                fraction = min(float(row["pt_stop_count"]), float(MOBILITY_SLIDER_MAX)) / float(MOBILITY_SLIDER_MAX)
                fill = interpolate_hex_color("#dbeafe", "#2563eb", fraction)
            elif topic == "land_use":
                fill = LAND_USE_COLOR_MAP.get(row["lu_2018_class_simplified"], "#e5e7eb")
            else:
                preview_metric = metric if metric in {"height_mean", "height_max"} else "height_mean"
                fraction = min(float(row[preview_metric]), 60.0) / 60.0
                fill = interpolate_hex_color("#dbeafe", "#4f46e5", fraction)
            svg_parts.append(
                f'<polygon points="{cell_points}" fill="{fill}" fill-opacity="0.9" stroke="none" />'
            )
    else:
        fill = build_preview_metric_fill(topic, metric, district_name)
        svg_parts.append(
            f'<polygon points="{polygon}" fill="{fill}" stroke="#d9e1ea" stroke-width="1.8" />'
        )

    svg_parts.append(
        f'<polygon points="{polygon}" fill="none" stroke="#cbd5e1" stroke-width="1.8" />'
    )
    svg_parts.append("</svg>")
    svg = "".join(svg_parts)
    return f"data:image/svg+xml;utf8,{quote(svg)}"


def build_pipeline_stage_button(stage: dict, active_stage_id: str) -> html.Button:
    is_active = stage["id"] == active_stage_id
    class_name = "pipeline-stage-card pipeline-stage-card-active" if is_active else "pipeline-stage-card"
    return html.Button(
        [
            html.Div(
                html.Img(src=stage["icon"], className="pipeline-stage-icon", alt=""),
                className="pipeline-stage-icon-wrap",
            ),
            html.Div(
                [
                    html.Div(stage["title"], className="pipeline-stage-title"),
                    html.Div(stage["subtitle"], className="pipeline-stage-subtitle"),
                ],
                className="pipeline-stage-copy",
            ),
        ],
        id={"type": "pipeline-stage-button", "stage": stage["id"]},
        n_clicks=0,
        className=class_name,
    )


def build_pipeline_center(
    topic: str | None,
    district_name: str,
    active_stage_id: str,
    metric: str | None = None,
    mobility_threshold: int = DEFAULT_MOBILITY_THRESHOLD,
    land_use_filter_values: list[str] | None = None,
) -> html.Div:
    topic_label = get_pipeline_topic_label(topic)
    stage_buttons: list = []
    for index, stage in enumerate(PIPELINE_STAGES):
        stage_buttons.append(build_pipeline_stage_button(stage, active_stage_id))
        if index < len(PIPELINE_STAGES) - 1:
            stage_buttons.append(html.Div("→", className="pipeline-stage-arrow"))

    return html.Div(
        [
            html.Div(
                [
                    html.Img(
                        src=build_district_preview_svg(
                            topic,
                            district_name,
                            metric=metric,
                            mobility_threshold=mobility_threshold,
                            land_use_filter_values=land_use_filter_values,
                        ),
                        className="pipeline-district-preview",
                        alt="",
                    ),
                    html.Div(district_name, className="pipeline-district-label"),
                ],
                className="pipeline-district-card",
            ),
            html.Div(stage_buttons, className="pipeline-stage-row"),
        ],
        className="pipeline-mode-content",
    )


def build_pipeline_prompt_panel(district_name: str) -> html.Div:
    return html.Div(
        [
            html.H2("Pipeline mode", className="panel-title"),
            html.P("Workflow overview", className="panel-subtitle"),
            html.Div(
                [
                    html.H3("Select a topic", className="metric-value"),
                    html.P("Pipeline details unlock once a topic is selected", className="metric-label"),
                ],
                className="metric-card",
            ),
            html.Div(
                [
                    html.H4("District in focus"),
                    html.P(f"{district_name} is ready for pipeline inspection."),
                    html.H4("Next step"),
                    html.P("Choose a topic to see how its data moves from source intake to final representation."),
                ],
                className="panel-body",
            ),
        ],
        className="right-panel-content",
    )


def build_pipeline_empty_state() -> html.Div:
    return html.Div(
        [
            html.Div("Pipeline mode", className="pipeline-empty-title"),
            html.Div(
                "Select 1 district to inspect how a topic moves from source intake to final dashboard representation.",
                className="pipeline-empty-text",
            ),
        ],
        className="pipeline-empty-state",
    )


def build_pipeline_stage_panel(stage_id: str, topic: str | None, district_name: str) -> html.Div:
    stage = get_pipeline_stage(stage_id)
    topic_label = get_pipeline_topic_label(topic)
    topic_source = (
        "Official district dataset"
        if topic in {"population", "housing", "green", "economy", "employment", "vulnerability"}
        else "Processed 250m spatial layer"
        if topic in {"mobility", "land_use", "height"}
        else "Topic not selected yet"
    )
    stage_text_map = {
        "source_intake": {
            "provenance": f"{topic_source}. District focus: {district_name}.",
            "action": f"Collect the source inputs required for the {topic_label.lower()} view and attach them to the selected district context.",
            "notes": [
                "Keep the selected district explicit from the beginning.",
                "Record whether the topic comes from official district data or a processed spatial layer.",
                "Surface missing source coverage before later stages hide it.",
            ],
            "why": "This stage makes the input origin visible before any transformation happens.",
        },
        "cleaning": {
            "provenance": f"Standardisation rules for the {topic_label.lower()} topic before display.",
            "action": "Normalise names, formats, units, and district keys so the topic can be joined and compared consistently.",
            "notes": [
                "District names are canonicalised across files.",
                "Missing or non-matching values are flagged instead of dropped silently.",
                "Only the fields needed for this dashboard topic are carried forward.",
            ],
            "why": "This stage keeps the dashboard readable by preventing mismatched labels and hidden data loss.",
        },
        "topic_preparation": {
            "provenance": f"Topic-specific preparation for {topic_label.lower()} in {district_name}.",
            "action": "Translate cleaned inputs into the exact metric or spatial evidence used by the selected topic view.",
            "notes": [
                "District-native topics prepare one comparable district metric.",
                "Grid topics prepare 250m cells filtered to the selected district.",
                "Topic-specific controls, such as thresholds or class filters, are applied here.",
            ],
            "why": "This is where raw inputs become the view-ready representation users actually inspect.",
        },
        "validation": {
            "provenance": f"Quality and uncertainty review for {topic_label.lower()}.",
            "action": "Check missing-data cases, outlier handling, and the limits of what the topic can claim.",
            "notes": [
                "Districts without matching values remain visible and marked as unavailable.",
                "Research-derived layers are labelled as processed spatial evidence.",
                "Caveats are kept visible in the right panel rather than hidden in metadata.",
            ],
            "why": "This stage supports explainability by making limits and uncertainty explicit before interpretation.",
        },
        "representation": {
            "provenance": f"Final dashboard translation for {topic_label.lower()} in {district_name}.",
            "action": "Render the prepared topic as a readable district-first view with controls, hover logic, and explanatory panel content.",
            "notes": [
                "Display mode remains district-first even when the topic uses grid cells.",
                "Hover and panel content separate quick reading from deeper explanation.",
                "UI controls stay topic-specific instead of exposing the full raw pipeline.",
            ],
            "why": "This is the stage where transparency becomes usable interface logic instead of hidden process detail.",
        },
    }
    stage_text = stage_text_map[stage["id"]]

    return html.Div(
        [
            html.H2(stage["title"], className="panel-title"),
            html.P("Pipeline stage details", className="panel-subtitle"),
            html.Div(
                [
                    html.H4("Provenance"),
                    html.P(stage_text["provenance"]),
                    html.H4("What happens in this stage?"),
                    html.P(stage_text["action"]),
                    html.H4("Processing notes"),
                    html.Ul([html.Li(note) for note in stage_text["notes"]]),
                    html.H4("Why this stage matters"),
                    html.P(stage_text["why"]),
                ],
                className="panel-body",
            ),
        ],
        className="right-panel-content",
    )


app = Dash(__name__)
app.title = "Madrid District Explorer"

app.layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [
                        html.H1("Madrid", className="sidebar-title"),
                        html.Button(
                            ICON_CLOSE,
                            id="sidebar-toggle-button",
                            n_clicks=0,
                            className="sidebar-toggle-button sidebar-toggle-button-hidden",
                            title="Collapse district sidebar",
                        ),
                    ],
                    className="sidebar-header",
                ),
                html.Div(
                    [
                        html.Label("District", className="field-label"),
                        html.P("Select 1 district to inspect", id="district-field-hint", className="field-hint"),
                        html.Div(
                            [
                                dcc.Input(
                                    id="district-search",
                                    type="text",
                                    placeholder="Search districts",
                                    className="district-search-input",
                                ),
                                html.Button(
                                    "A-Z",
                                    id="district-sort-button",
                                    n_clicks=0,
                                    className="district-sort-button",
                                    title="Toggle alphabetical sorting",
                                ),
                            ],
                            className="district-toolbar",
                        ),
                        html.Div(
                            [
                                dcc.Checklist(
                                    id="district-checklist",
                                    options=build_district_options(),
                                    value=[],
                                    className="district-checklist",
                                    inputClassName="district-checklist-input",
                                    labelClassName="district-checklist-label",
                                )
                            ],
                            className="district-selector",
                        ),
                    ],
                    className="app-sidebar-inner",
                ),
            ],
            id="app-sidebar",
            className="app-sidebar",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.H2(id="map-selection-title", children="Madrid", className="map-title"),
                                                html.Div(id="map-selection-info", className="map-selection-info"),
                                            ],
                                            className="map-title-row",
                                        ),
                                    ],
                                    className="map-title-wrap",
                                ),
                                html.Div(
                                    [
                                        html.Button(
                                            "Display mode",
                                            id="view-mode-display-button",
                                            className="mode-toggle-button mode-toggle-button-active",
                                        ),
                                        html.Button(
                                            "Pipeline mode",
                                            id="view-mode-pipeline-button",
                                            className="mode-toggle-button",
                                        ),
                                    ],
                                    className="mode-toggle",
                                ),
                            ],
                            className="map-toolbar-top",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Button(
                                                    ICON_HOUSING,
                                                    id="topic-housing",
                                                    n_clicks=0,
                                                    className="topic-icon-button topic-icon-button-disabled",
                                                    disabled=True,
                                                    title="Housing",
                                                ),
                                                html.Button(
                                                    ICON_POPULATION,
                                                    id="topic-population",
                                                    n_clicks=0,
                                                    className="topic-icon-button topic-icon-button-disabled",
                                                    disabled=True,
                                                    title="Population & density",
                                                ),
                                                html.Button(
                                                    ICON_GREEN,
                                                    id="topic-green",
                                                    n_clicks=0,
                                                    className="topic-icon-button topic-icon-button-disabled",
                                                    disabled=True,
                                                    title="Green",
                                                ),
                                                html.Button(
                                                    ICON_LAND_USE,
                                                    id="topic-land-use",
                                                    n_clicks=0,
                                                    className="topic-icon-button topic-icon-button-disabled",
                                                    disabled=True,
                                                    title="Land use",
                                                ),
                                                html.Button(
                                                    ICON_HEIGHT,
                                                    id="topic-height",
                                                    n_clicks=0,
                                                    className="topic-icon-button topic-icon-button-disabled",
                                                    disabled=True,
                                                    title="Building height",
                                                ),
                                                html.Button(
                                                    ICON_MOBILITY,
                                                    id="topic-mobility",
                                                    n_clicks=0,
                                                    className="topic-icon-button topic-icon-button-disabled",
                                                    disabled=True,
                                                    title="Mobility",
                                                ),
                                                html.Button(
                                                    ICON_ECONOMY,
                                                    id="topic-economy",
                                                    n_clicks=0,
                                                    className="topic-icon-button topic-icon-button-disabled",
                                                    disabled=True,
                                                    title="Economy",
                                                ),
                                                html.Button(
                                                    ICON_EMPLOYMENT,
                                                    id="topic-employment",
                                                    n_clicks=0,
                                                    className="topic-icon-button topic-icon-button-disabled",
                                                    disabled=True,
                                                    title="Employment",
                                                ),
                                                html.Button(
                                                    ICON_VULNERABILITY,
                                                    id="topic-vulnerability",
                                                    n_clicks=0,
                                                    className="topic-icon-button topic-icon-button-disabled",
                                                    disabled=True,
                                                    title="Vulnerability",
                                                ),
                                            ],
                                            className="map-toolbar-icons",
                                        ),
                                        html.Div(
                                            [
                                                html.Div(id="map-topic-info", className="map-topic-info"),
                                                html.Div(
                                                    [
                                                        html.Button(
                                                            "Inspect",
                                                            id="display-submode-inspect-button",
                                                            className="mode-toggle-button mode-toggle-button-active mode-toggle-button-secondary",
                                                        ),
                                                        html.Button(
                                                            "Compare",
                                                            id="display-submode-compare-button",
                                                            className="mode-toggle-button mode-toggle-button-secondary",
                                                        ),
                                                    ],
                                                    id="display-submode-toggle",
                                                    className="mode-toggle mode-toggle-secondary",
                                                ),
                                            ],
                                            className="map-toolbar-secondary",
                                        ),
                                    ],
                                    className="map-toolbar-bottom",
                                ),
                            ],
                            className="map-toolbar-bottom-wrap",
                        ),
                    ],
                    className="map-toolbar",
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                dcc.Graph(
                                    id="district-map",
                                    config={"displayModeBar": False},
                                    clear_on_unhover=True,
                                    className="district-map-graph",
                                ),
                                html.Div(
                                    id="map-hover-layer",
                                    className="map-hover-layer",
                                    style={"display": "none"},
                                ),
                            ],
                            id="display-mode-map-layer",
                            className="display-mode-map-layer",
                        ),
                        html.Div(
                            id="pipeline-mode-layer",
                            className="pipeline-mode-layer",
                            style={"display": "none"},
                        ),
                    ],
                    className="app-center-body",
                )
            ],
            className="app-center",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Metric", className="field-label"),
                        html.Div(
                            [
                                html.Button(
                                    [
                                        html.Span("Population total", id="metric-filter-label"),
                                        html.Span("⌄", className="filter-select-chevron"),
                                    ],
                                    id="metric-filter-toggle",
                                    n_clicks=0,
                                    className="filter-select-toggle",
                                ),
                                html.Div(
                                    build_metric_menu(DEFAULT_TOPIC, "population_total"),
                                    id="metric-filter-menu",
                                    className="filter-select-menu",
                                    style={"display": "none"},
                                ),
                            ],
                            className="filter-select",
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Label("Stop threshold", className="field-label field-label-spaced"),
                                        html.Div(
                                            [
                                                html.Button(
                                                    "i",
                                                    id="mobility-threshold-info-button",
                                                    n_clicks=0,
                                                    className="inline-info-chip",
                                                ),
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            "Why is the slider limited to 10?",
                                                            className="inline-info-bubble-title",
                                                        ),
                                                        html.Div(
                                                            "The underlying mobility layer contains cells with up to 70 stops, but values above 10 are rare outliers. The slider is limited to 1-10 to keep exploration readable while higher-count cells still appear whenever they pass the chosen threshold."
                                                        ),
                                                    ],
                                                    id="mobility-threshold-info-bubble",
                                                    className="inline-info-bubble",
                                                ),
                                            ],
                                            className="inline-info-wrap",
                                        ),
                                    ],
                                    className="inline-label-row",
                                ),
                                dcc.Slider(
                                    id="mobility-threshold-slider",
                                    min=1,
                                    max=MOBILITY_SLIDER_MAX,
                                    step=1,
                                    value=DEFAULT_MOBILITY_THRESHOLD,
                                    marks={
                                        1: "1",
                                        2: "2",
                                        3: "3",
                                        5: "5",
                                        7: "7",
                                        10: "10",
                                    },
                                    tooltip={"placement": "bottom", "always_visible": False},
                                ),
                            ],
                            id="mobility-threshold-wrap",
                            className="mobility-threshold-wrap",
                            style={"display": "none"},
                        ),
                        html.Div(
                            [
                                html.Label("Land-use class", className="field-label field-label-spaced"),
                                html.Div(
                                    [
                                        html.Button(
                                            [
                                                html.Span("All classes", id="land-use-filter-label"),
                                                html.Span("⌄", className="filter-select-chevron"),
                                            ],
                                            id="land-use-filter-toggle",
                                            n_clicks=0,
                                            className="filter-select-toggle",
                                        ),
                                        html.Div(
                                            build_land_use_filter_menu(DEFAULT_DISTRICT, get_land_use_class_values(DEFAULT_DISTRICT)),
                                            id="land-use-filter-menu",
                                            className="filter-select-menu",
                                            style={"display": "none"},
                                        ),
                                    ],
                                    className="filter-select",
                                ),
                            ],
                            id="land-use-filter-wrap",
                            className="land-use-filter-wrap",
                            style={"display": "none"},
                        ),
                    ],
                    id="right-panel-controls",
                    className="right-panel-controls",
                ),
                html.Div(id="district-panel", className="right-panel-body"),
            ],
            id="right-panel-region",
            className="app-right-panel",
        ),
        dcc.Store(id="selected-district-store", data=[]),
        dcc.Store(id="selected-topic-store", data=None),
        dcc.Store(id="metric-value-store", data=None),
        dcc.Store(id="metric-open-store", data=False),
        dcc.Store(id="land-use-filter-value-store", data=[]),
        dcc.Store(id="land-use-filter-open-store", data=False),
        dcc.Store(id="sidebar-collapsed-store", data=False),
        dcc.Store(id="sidebar-manual-state-store", data=None),
        dcc.Store(id="view-mode-store", data=DEFAULT_VIEW_MODE),
        dcc.Store(id="display-selection-mode-store", data=DEFAULT_DISPLAY_SELECTION_MODE),
        dcc.Store(id="pipeline-stage-store", data=DEFAULT_PIPELINE_STAGE),
    ],
    id="app-shell",
    className="app-shell",
)


@app.callback(
    Output("view-mode-store", "data"),
    Output("display-selection-mode-store", "data"),
    Output("view-mode-display-button", "className"),
    Output("view-mode-pipeline-button", "className"),
    Output("display-submode-toggle", "style"),
    Output("display-submode-inspect-button", "className"),
    Output("display-submode-compare-button", "className"),
    Output("district-field-hint", "children"),
    Input("view-mode-display-button", "n_clicks"),
    Input("view-mode-pipeline-button", "n_clicks"),
    Input("display-submode-inspect-button", "n_clicks"),
    Input("display-submode-compare-button", "n_clicks"),
    State("view-mode-store", "data"),
    State("display-selection-mode-store", "data"),
)
def sync_mode_controls(
    display_clicks: int,
    pipeline_clicks: int,
    inspect_clicks: int,
    compare_clicks: int,
    current_view_mode: str | None,
    current_display_mode: str | None,
):
    view_mode = current_view_mode or DEFAULT_VIEW_MODE
    display_mode = current_display_mode or DEFAULT_DISPLAY_SELECTION_MODE
    triggered = callback_context.triggered_id

    if triggered == "view-mode-display-button":
        view_mode = "display"
    elif triggered == "view-mode-pipeline-button":
        view_mode = "pipeline"
    elif triggered == "display-submode-inspect-button":
        display_mode = "inspect"
    elif triggered == "display-submode-compare-button":
        display_mode = "compare"

    display_button_class = "mode-toggle-button mode-toggle-button-active" if view_mode == "display" else "mode-toggle-button"
    pipeline_button_class = "mode-toggle-button mode-toggle-button-active" if view_mode == "pipeline" else "mode-toggle-button"
    submode_style = {"display": "inline-flex"} if view_mode == "display" else {"display": "none"}
    inspect_button_class = (
        "mode-toggle-button mode-toggle-button-secondary mode-toggle-button-active"
        if display_mode == "inspect"
        else "mode-toggle-button mode-toggle-button-secondary"
    )
    compare_button_class = (
        "mode-toggle-button mode-toggle-button-secondary mode-toggle-button-active"
        if display_mode == "compare"
        else "mode-toggle-button mode-toggle-button-secondary"
    )

    if view_mode == "pipeline":
        field_hint = "Select 1 district to inspect its pipeline"
    elif display_mode == "compare":
        field_hint = "Select up to 2 districts to compare"
    else:
        field_hint = "Select 1 district to inspect"

    return (
        view_mode,
        display_mode,
        display_button_class,
        pipeline_button_class,
        submode_style,
        inspect_button_class,
        compare_button_class,
        field_hint,
    )


@app.callback(
    Output("pipeline-stage-store", "data"),
    Input({"type": "pipeline-stage-button", "stage": ALL}, "n_clicks"),
    Input("selected-topic-store", "data"),
    State("pipeline-stage-store", "data"),
    prevent_initial_call=True,
)
def sync_pipeline_stage(stage_clicks: list[int], topic: str | None, current_stage: str | None):
    triggered = callback_context.triggered_id
    if triggered == "selected-topic-store":
        return DEFAULT_PIPELINE_STAGE
    if isinstance(triggered, dict) and triggered.get("type") == "pipeline-stage-button":
        return triggered.get("stage", current_stage or DEFAULT_PIPELINE_STAGE)
    return current_stage or DEFAULT_PIPELINE_STAGE


@app.callback(
    Output("selected-topic-store", "data"),
    Output("metric-value-store", "data"),
    Output("metric-open-store", "data"),
    Output("topic-population", "className"),
    Output("topic-population", "disabled"),
    Output("topic-housing", "className"),
    Output("topic-housing", "disabled"),
    Output("topic-green", "className"),
    Output("topic-green", "disabled"),
    Output("topic-land-use", "className"),
    Output("topic-land-use", "disabled"),
    Output("topic-height", "className"),
    Output("topic-height", "disabled"),
    Output("topic-mobility", "className"),
    Output("topic-mobility", "disabled"),
    Output("topic-economy", "className"),
    Output("topic-economy", "disabled"),
    Output("topic-employment", "className"),
    Output("topic-employment", "disabled"),
    Output("topic-vulnerability", "className"),
    Output("topic-vulnerability", "disabled"),
    Input("topic-population", "n_clicks"),
    Input("topic-housing", "n_clicks"),
    Input("topic-green", "n_clicks"),
    Input("topic-land-use", "n_clicks"),
    Input("topic-height", "n_clicks"),
    Input("topic-mobility", "n_clicks"),
    Input("topic-economy", "n_clicks"),
    Input("topic-employment", "n_clicks"),
    Input("topic-vulnerability", "n_clicks"),
    Input("selected-district-store", "data"),
    State("selected-topic-store", "data"),
)
def sync_topic(
    population_clicks: int,
    housing_clicks: int,
    green_clicks: int,
    land_use_clicks: int,
    height_clicks: int,
    mobility_clicks: int,
    economy_clicks: int,
    employment_clicks: int,
    vulnerability_clicks: int,
    selected_districts: list[str] | None,
    current_topic: str | None,
):
    triggered = callback_context.triggered_id
    has_selected_district = bool(canonicalise_selected_districts(selected_districts))
    topic = current_topic if has_selected_district else None

    if has_selected_district and triggered == "topic-population":
        topic = "population"
    elif has_selected_district and triggered == "topic-housing":
        topic = "housing"
    elif has_selected_district and triggered == "topic-green":
        topic = "green"
    elif has_selected_district and triggered == "topic-land-use":
        topic = "land_use"
    elif has_selected_district and triggered == "topic-height":
        topic = "height"
    elif has_selected_district and triggered == "topic-mobility":
        topic = "mobility"
    elif has_selected_district and triggered == "topic-economy":
        topic = "economy"
    elif has_selected_district and triggered == "topic-employment":
        topic = "employment"
    elif has_selected_district and triggered == "topic-vulnerability":
        topic = "vulnerability"

    default_metric = build_metric_options(topic)[0]["value"] if topic else None
    is_disabled = not has_selected_district
    return (
        topic,
        default_metric,
        False,
        topic_button_class(topic, "population", has_selected_district),
        is_disabled,
        topic_button_class(topic, "housing", has_selected_district),
        is_disabled,
        topic_button_class(topic, "green", has_selected_district),
        is_disabled,
        topic_button_class(topic, "land_use", has_selected_district),
        is_disabled,
        topic_button_class(topic, "height", has_selected_district),
        is_disabled,
        topic_button_class(topic, "mobility", has_selected_district),
        is_disabled,
        topic_button_class(topic, "economy", has_selected_district),
        is_disabled,
        topic_button_class(topic, "employment", has_selected_district),
        is_disabled,
        topic_button_class(topic, "vulnerability", has_selected_district),
        is_disabled,
    )


@app.callback(
    Output("selected-district-store", "data"),
    Output("district-checklist", "value"),
    Input("district-checklist", "value"),
    Input("district-map", "clickData"),
    Input("view-mode-store", "data"),
    Input("display-selection-mode-store", "data"),
    State("selected-district-store", "data"),
)
def sync_selected_district(
    checklist_values: list[str] | None,
    click_data: dict | None,
    view_mode: str | None,
    display_selection_mode: str | None,
    current_districts: list[str] | None,
):
    current_selection = canonicalise_selected_districts(current_districts)
    triggered = callback_context.triggered_id
    compare_enabled = is_compare_selection_mode(view_mode, display_selection_mode)

    if triggered in ("view-mode-store", "display-selection-mode-store"):
        if compare_enabled:
            limited_selection = canonicalise_selected_districts(current_selection)
            return limited_selection, limited_selection
        if current_selection:
            reduced_selection = [get_active_map_district(current_selection)]
            return reduced_selection, reduced_selection
        return [], []

    if triggered == "district-map" and click_data and click_data.get("points"):
        point = click_data["points"][0]
        clicked_district = resolve_click_district_name(point, current_selection[0] if current_selection else DEFAULT_DISTRICT)
        if compare_enabled:
            if clicked_district in current_selection:
                updated_selection = [name for name in current_selection if name != clicked_district]
                return updated_selection, updated_selection
            if len(current_selection) >= 2:
                updated_selection = [current_selection[1], clicked_district]
                return updated_selection, updated_selection
            updated_selection = [*current_selection, clicked_district]
            return updated_selection, updated_selection

        if clicked_district in current_selection and current_selection:
            return current_selection[:1], current_selection[:1]
        return [clicked_district], [clicked_district]

    if triggered == "district-checklist":
        if compare_enabled:
            if not checklist_values:
                return [], []

            normalized_checklist = normalise_district_sequence(checklist_values)
            added_districts = [name for name in normalized_checklist if name not in current_selection]
            removed_districts = [name for name in current_selection if name not in normalized_checklist]

            if removed_districts and not added_districts:
                updated_selection = [name for name in current_selection if name in normalized_checklist]
                return updated_selection, updated_selection

            if added_districts:
                if len(current_selection) >= 2:
                    updated_selection = [current_selection[1], added_districts[-1]]
                    return updated_selection, updated_selection
                updated_selection = [*current_selection, added_districts[-1]]
                return updated_selection, updated_selection

            stable_selection = [name for name in current_selection if name in normalized_checklist]
            if stable_selection:
                return stable_selection, stable_selection
            limited_selection = canonicalise_selected_districts(normalized_checklist)
            return limited_selection, limited_selection

        if not checklist_values:
            if current_selection:
                return current_selection[:1], current_selection[:1]
            return [], []

        normalized_checklist = normalise_district_sequence(checklist_values)
        added_districts = [name for name in normalized_checklist if name not in current_selection]
        if added_districts:
            updated_selection = [added_districts[-1]]
            return updated_selection, updated_selection

        if normalized_checklist:
            stable_selection = [normalized_checklist[-1]]
            return stable_selection, stable_selection
        if current_selection:
            return current_selection[:1], current_selection[:1]
        return [], []

    return current_selection, current_selection


@app.callback(
    Output("district-checklist", "options"),
    Output("district-sort-button", "children"),
    Input("district-search", "value"),
    Input("district-sort-button", "n_clicks"),
    Input("selected-district-store", "data"),
)
def update_district_options(search_query: str | None, sort_clicks: int, selected_districts: list[str] | None):
    search_text = (search_query or "").strip().casefold()
    district_names = DISTRICT_FRAME["district_name"].drop_duplicates().tolist()
    district_names.sort(reverse=bool(sort_clicks % 2))

    if search_text:
        district_names = [
            district_name
            for district_name in district_names
            if search_text in district_name.casefold()
        ]

    sort_label = "Z-A" if sort_clicks % 2 else "A-Z"
    return build_district_options(district_names, selected_districts), sort_label


@app.callback(
    Output("sidebar-collapsed-store", "data"),
    Output("sidebar-manual-state-store", "data"),
    Input("selected-district-store", "data"),
    Input("sidebar-toggle-button", "n_clicks"),
    State("sidebar-collapsed-store", "data"),
    State("sidebar-manual-state-store", "data"),
)
def sync_sidebar_state(
    selected_districts: list[str] | None,
    toggle_clicks: int,
    is_collapsed: bool,
    manual_state: str | None,
):
    selected_count = len(canonicalise_selected_districts(selected_districts))
    triggered = callback_context.triggered_id

    if triggered == "sidebar-toggle-button" and selected_count >= 2:
        next_collapsed = not bool(is_collapsed)
        return next_collapsed, "collapsed" if next_collapsed else "expanded"

    if selected_count < 2:
        return False, None

    if manual_state is None:
        return True, None

    return bool(is_collapsed), manual_state


@app.callback(
    Output("app-shell", "className"),
    Output("app-sidebar", "className"),
    Output("sidebar-toggle-button", "className"),
    Output("sidebar-toggle-button", "children"),
    Input("selected-district-store", "data"),
    Input("sidebar-collapsed-store", "data"),
)
def update_layout_state(selected_districts: list[str] | None, is_collapsed: bool):
    selected_count = len(canonicalise_selected_districts(selected_districts))
    shell_class_parts = ["app-shell"]
    if selected_count == 0:
        shell_class_parts.append("app-shell-no-panel")
    elif selected_count == 1:
        shell_class_parts.append("app-shell-one-panel")
    else:
        shell_class_parts.append("app-shell-two-panels")

    sidebar_class_parts = ["app-sidebar"]
    toggle_class_parts = ["sidebar-toggle-button"]
    toggle_icon = ICON_CLOSE

    if is_collapsed:
        shell_class_parts.append("app-shell-sidebar-collapsed")
        sidebar_class_parts.append("app-sidebar-collapsed")
        toggle_icon = ICON_SEARCH

    if selected_count < 2 and not is_collapsed:
        toggle_class_parts.append("sidebar-toggle-button-hidden")
    elif selected_count < 2:
        toggle_class_parts.append("sidebar-toggle-button-hidden")

    return (
        " ".join(shell_class_parts),
        " ".join(sidebar_class_parts),
        " ".join(toggle_class_parts),
        toggle_icon,
    )


@app.callback(
    Output("district-map", "figure"),
    Input("metric-value-store", "data"),
    Input("selected-topic-store", "data"),
    Input("selected-district-store", "data"),
    Input("mobility-threshold-slider", "value"),
    Input("land-use-filter-value-store", "data"),
    Input("district-map", "hoverData"),
)
def update_map(
    metric: str | None,
    topic: str | None,
    selected_districts: list[str] | None,
    mobility_threshold: int,
    land_use_filter: list[str] | None,
    hover_data: dict | None,
):
    normalized_selection = canonicalise_selected_districts(selected_districts)
    if not normalized_selection:
        return build_grid_base_figure()

    active_district = get_active_map_district(selected_districts)
    hovered_district_name = None
    if hover_data and hover_data.get("points"):
        hovered_district_name = resolve_click_district_name(hover_data["points"][0], active_district)

    if topic == "land_use" and metric:
        figure = build_land_use_map(selected_districts, land_use_filter)
    elif topic == "height" and metric:
        figure = build_height_map(selected_districts, metric)
    elif topic == "mobility":
        figure = build_mobility_map(mobility_threshold or DEFAULT_MOBILITY_THRESHOLD, selected_districts)
    elif topic and metric:
        figure = build_choropleth(metric, topic)
        figure.update_traces(
            selectedpoints=[
                index
                for index, name in enumerate(DISTRICT_FRAME["district_name"])
                if name in normalized_selection
            ],
            selector={"type": "choropleth"},
        )
    else:
        figure = build_grid_base_figure()
    figure = add_hovered_district_outline(figure, hovered_district_name, selected_districts)
    figure = add_selected_district_outlines(figure, selected_districts)
    return figure


@app.callback(
    Output("display-mode-map-layer", "style"),
    Output("pipeline-mode-layer", "children"),
    Output("pipeline-mode-layer", "style"),
    Input("view-mode-store", "data"),
    Input("selected-district-store", "data"),
    Input("selected-topic-store", "data"),
    Input("metric-value-store", "data"),
    Input("mobility-threshold-slider", "value"),
    Input("land-use-filter-value-store", "data"),
    Input("pipeline-stage-store", "data"),
)
def update_center_mode(
    view_mode: str | None,
    selected_districts: list[str] | None,
    topic: str | None,
    metric: str | None,
    mobility_threshold: int,
    land_use_filter_values: list[str] | None,
    pipeline_stage: str | None,
):
    if view_mode == "pipeline":
        normalized_selection = canonicalise_selected_districts(selected_districts)
        if not normalized_selection:
            return {"display": "none"}, build_pipeline_empty_state(), {"display": "block"}
        active_district = get_active_map_district(selected_districts)
        return (
            {"display": "none"},
            build_pipeline_center(
                topic,
                active_district,
                pipeline_stage or DEFAULT_PIPELINE_STAGE,
                metric=metric,
                mobility_threshold=mobility_threshold,
                land_use_filter_values=land_use_filter_values,
            ),
            {"display": "block"},
        )
    return {"display": "block"}, html.Div(), {"display": "none"}


@app.callback(
    Output("district-panel", "children"),
    Output("map-selection-title", "children"),
    Output("map-selection-info", "children"),
    Output("map-topic-info", "children"),
    Output("right-panel-region", "className"),
    Output("right-panel-controls", "style"),
    Input("selected-district-store", "data"),
    Input("metric-value-store", "data"),
    Input("selected-topic-store", "data"),
    Input("mobility-threshold-slider", "value"),
    Input("land-use-filter-value-store", "data"),
    Input("view-mode-store", "data"),
    Input("pipeline-stage-store", "data"),
)
def update_panel(
    selected_districts: list[str] | None,
    metric: str | None,
    topic: str | None,
    mobility_threshold: int,
    land_use_filter: list[str] | None,
    view_mode: str | None,
    pipeline_stage: str | None,
):
    normalized_selection = canonicalise_selected_districts(selected_districts)
    selected_count = len(normalized_selection)
    controls_style = {"display": "block"} if topic and view_mode == "display" else {"display": "none"}

    if selected_count == 0:
        return (
            [],
            "Madrid",
            html.Div(),
            html.Div(),
            "app-right-panel app-right-panel-hidden",
            {"display": "none"},
        )

    if selected_count == 1:
        district_name = normalized_selection[0]
        if view_mode == "pipeline":
            panel_children = (
                build_pipeline_stage_panel(pipeline_stage or DEFAULT_PIPELINE_STAGE, topic, district_name)
                if topic
                else build_pipeline_prompt_panel(district_name)
            )
            subtitle = (
                "Select a pipeline stage to inspect how this topic is produced."
                if topic
                else "Choose a topic to unlock the pipeline walkthrough."
            )
            return (
                build_district_sidebar(panel_children, 1),
                district_name,
                build_toolbar_info_bubble(subtitle, "Pipeline help"),
                html.Div(),
                "app-right-panel app-right-panel-single",
                {"display": "none"},
            )
        panel_children = (
            build_info_panel(
                district_name,
                metric,
                topic,
                mobility_threshold or DEFAULT_MOBILITY_THRESHOLD,
                land_use_filter,
            )
            if topic and metric
            else build_topic_prompt_panel(district_name)
        )
        subtitle = (
            "Shared topic controls are now unlocked for this district."
            if topic
            else "Choose a topic to open the district explanation and metric summary."
        )
        return (
            build_district_sidebar(panel_children, 1),
            district_name,
            build_toolbar_info_bubble(subtitle, "Topic help"),
            html.Div(),
            "app-right-panel app-right-panel-single",
            controls_style,
        )

    first_district = normalized_selection[0]
    second_district = normalized_selection[1]
    first_panel = (
        build_info_panel(
            first_district,
            metric,
            topic,
            mobility_threshold or DEFAULT_MOBILITY_THRESHOLD,
            land_use_filter,
        )
        if topic and metric
        else build_topic_prompt_panel(first_district, is_comparison=True)
    )
    second_panel = (
        build_info_panel(
            second_district,
            metric,
            topic,
            mobility_threshold or DEFAULT_MOBILITY_THRESHOLD,
            land_use_filter,
        )
        if topic and metric
        else build_topic_prompt_panel(second_district, is_comparison=True)
    )
    subtitle = ""
    comparison_message = (
        "Both district sidebars use the same shared topic for direct comparison."
        if topic
        else "Choose one shared topic to populate both district sidebars."
    )
    return (
        [
            build_district_sidebar(first_panel, 1),
            build_district_sidebar(second_panel, 2),
        ],
        f"{first_district} vs {second_district}",
        build_map_info_bubble(comparison_message),
        html.Div(),
        "app-right-panel app-right-panel-double",
        controls_style,
    )


@app.callback(
    Output("map-hover-layer", "children"),
    Output("map-hover-layer", "style"),
    Input("district-map", "hoverData"),
    Input("selected-topic-store", "data"),
    Input("metric-value-store", "data"),
    Input("mobility-threshold-slider", "value"),
    Input("land-use-filter-value-store", "data"),
)
def update_hover_layer(
    hover_data: dict | None,
    topic: str | None,
    metric: str | None,
    mobility_threshold: int,
    land_use_filter: list[str] | None,
):
    if not topic or not metric or not hover_data or not hover_data.get("points"):
        return html.Div(), {"display": "none"}

    return (
        build_hover_card(
            hover_data,
            topic,
            metric,
            mobility_threshold or DEFAULT_MOBILITY_THRESHOLD,
            land_use_filter,
        ),
        {"display": "block"},
    )


@app.callback(
    Output("mobility-threshold-wrap", "style"),
    Input("selected-topic-store", "data"),
)
def toggle_mobility_threshold(topic: str):
    if topic == "mobility":
        return {"display": "block"}
    return {"display": "none"}


@app.callback(
    Output("metric-filter-label", "children"),
    Output("metric-filter-menu", "children"),
    Output("metric-filter-menu", "style"),
    Input("selected-topic-store", "data"),
    Input("metric-value-store", "data"),
    Input("metric-open-store", "data"),
)
def render_metric_filter(topic: str, selected_value: str, is_open: bool):
    if not topic:
        return "Select a topic", [], {"display": "none"}

    metric_value = selected_value or build_metric_options(topic)[0]["value"]
    return (
        get_metric_label(topic, metric_value),
        build_metric_menu(topic, metric_value),
        {"display": "block"} if is_open else {"display": "none"},
    )


@app.callback(
    Output("metric-value-store", "data", allow_duplicate=True),
    Output("metric-open-store", "data", allow_duplicate=True),
    Input("metric-filter-toggle", "n_clicks"),
    Input({"type": "metric-option", "value": ALL}, "n_clicks"),
    State("selected-topic-store", "data"),
    State("metric-value-store", "data"),
    State("metric-open-store", "data"),
    prevent_initial_call=True,
)
def sync_metric_filter(
    toggle_clicks: int,
    option_clicks: list[int],
    topic: str | None,
    current_value: str | None,
    is_open: bool,
):
    if not topic:
        return None, False

    triggered = callback_context.triggered_id

    if triggered == "metric-filter-toggle":
        return current_value or build_metric_options(topic)[0]["value"], not bool(is_open)

    if isinstance(triggered, dict) and triggered.get("type") == "metric-option":
        return triggered.get("value", build_metric_options(topic)[0]["value"]), False

    return current_value or build_metric_options(topic)[0]["value"], bool(is_open)


@app.callback(
    Output("land-use-filter-wrap", "style"),
    Output("land-use-filter-label", "children"),
    Output("land-use-filter-menu", "children"),
    Output("land-use-filter-menu", "style"),
    Input("selected-topic-store", "data"),
    Input("selected-district-store", "data"),
    Input("land-use-filter-value-store", "data"),
    Input("land-use-filter-open-store", "data"),
)
def toggle_land_use_filter(topic: str | None, district_names: list[str] | None, selected_value: list[str] | None, is_open: bool):
    if not canonicalise_selected_districts(district_names):
        return {"display": "none"}, "Select a district", [], {"display": "none"}

    selected_values = normalise_land_use_filter_values(selected_value if isinstance(selected_value, list) else None, district_names)
    label = get_land_use_filter_label(selected_values, district_names)
    menu_children = build_land_use_filter_menu(district_names, selected_values)
    if topic == "land_use":
        return (
            {"display": "block"},
            label,
            menu_children,
            {"display": "block"} if is_open else {"display": "none"},
        )
    return {"display": "none"}, label, menu_children, {"display": "none"}


@app.callback(
    Output("land-use-filter-value-store", "data"),
    Output("land-use-filter-open-store", "data"),
    Input("land-use-filter-toggle", "n_clicks"),
    Input({"type": "land-use-filter-option", "value": ALL}, "n_clicks"),
    Input({"type": "land-use-filter-action", "value": ALL}, "n_clicks"),
    Input("selected-topic-store", "data"),
    Input("selected-district-store", "data"),
    State("land-use-filter-value-store", "data"),
    State("land-use-filter-open-store", "data"),
)
def sync_land_use_filter(
    toggle_clicks: int,
    option_clicks: list[int],
    action_clicks: list[int],
    topic: str | None,
    district_names: list[str] | None,
    current_value: list[str] | None,
    is_open: bool,
):
    if not canonicalise_selected_districts(district_names):
        return [], False

    available_values = get_land_use_class_values(district_names)
    normalized_values = normalise_land_use_filter_values(current_value, district_names)
    triggered = callback_context.triggered_id

    if triggered in ("selected-topic-store", "selected-district-store"):
        return available_values, False

    if triggered == "land-use-filter-toggle":
        return normalized_values, not bool(is_open)

    if isinstance(triggered, dict) and triggered.get("type") == "land-use-filter-option":
        selected_value = triggered.get("value")
        if selected_value in normalized_values:
            updated_values = [value for value in normalized_values if value != selected_value]
        else:
            updated_values = [*normalized_values, selected_value]
        updated_values = [value for value in available_values if value in updated_values]
        return updated_values, True

    if isinstance(triggered, dict) and triggered.get("type") == "land-use-filter-action":
        action = triggered.get("value")
        if action == "select_all":
            return available_values, False
        if action == "clear_all":
            return [], False

    return normalized_values, bool(is_open)


if __name__ == "__main__":
    app.run(debug=True)
