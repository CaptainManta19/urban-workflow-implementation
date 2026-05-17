import json
import re
from io import StringIO
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, callback_context, dcc, html, no_update
from shapely.geometry import GeometryCollection, LineString, MultiLineString, shape as geometry_shape
from shapely.validation import make_valid

from backend.dashboard_data.dataset_builder import build_dashboard_datasets
from backend.features.engineering import normalise_district_name


DEFAULT_DISTRICT = "Centro"
DEFAULT_TOPIC = "population"
DEFAULT_MOBILITY_THRESHOLD = 2
MOBILITY_SLIDER_MAX = 10
MAP_UIREVISION = "district-map-shared-view"
DEFAULT_VIEW_MODE = "display"
DEFAULT_DISPLAY_SELECTION_MODE = "inspect"
DEFAULT_PIPELINE_STAGE = "source_intake"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRID_TOPICS = {"land_use", "height", "mobility"}
ONBOARDING_STEP_COUNT = 3


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


def build_lucide_icon_with_color(svg_inner: str, stroke: str, class_name: str = "topic-icon-svg") -> html.Img:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" '
        f'stroke="{stroke}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{svg_inner}</svg>"
    )
    return html.Img(
        src=f"data:image/svg+xml;utf8,{quote(svg)}",
        className=class_name,
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


def build_file_icon_data_uri(stroke: str = "#111827") -> str:
    return build_lucide_icon_data_uri(
        (
            '<path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7z"/>'
            '<path d="M14 2v5h5"/>'
            '<path d="M9 13h6"/>'
            '<path d="M9 17h6"/>'
        ),
        stroke=stroke,
    )


NUMBER_EMPHASIS_PATTERN = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})*(?:\.\d+)?%?|\d+(?:\.\d+)?%?)(?![\d.,])")


def emphasize_numbers(text: str):
    parts: list[str | html.Strong] = []
    last_index = 0
    for match in NUMBER_EMPHASIS_PATTERN.finditer(text):
        start, end = match.span()
        if start > last_index:
            parts.append(text[last_index:start])
        parts.append(html.Strong(match.group(0)))
        last_index = end
    if last_index < len(text):
        parts.append(text[last_index:])
    return parts if parts else text
DASHBOARD_DATASETS = build_dashboard_datasets()
DISTRICT_GEOJSON = DASHBOARD_DATASETS["district_geojson"]
GRID_FRAME = DASHBOARD_DATASETS["grid_frame"]
DISTRICT_FRAME = DASHBOARD_DATASETS["district_frame"]
DISTRICT_NAME_BY_KEY = {
    normalise_district_name(name): name
    for name in DISTRICT_FRAME["district_name"].drop_duplicates()
}

COMPARE_DISTRICT_COLORS = ("#2563eb", "#7c3aed")


def get_compare_color(panel_position: int) -> str:
    return COMPARE_DISTRICT_COLORS[min(max(panel_position - 1, 0), len(COMPARE_DISTRICT_COLORS) - 1)]


def build_compare_district_name(name: str) -> html.Span:
    return html.Span(
        name,
        className="typology-district-name-inline",
    )


def sanitize_geometry(geometry):
    if geometry.is_valid:
        return geometry
    repaired = make_valid(geometry)
    if repaired.is_valid:
        return repaired
    return geometry.buffer(0)


DISTRICT_SHAPES = {
    feature["id"]: sanitize_geometry(geometry_shape(feature["geometry"]))
    for feature in DISTRICT_GEOJSON["features"]
}
GRID_GEOJSON = DASHBOARD_DATASETS["grid_geojson"]
MOBILITY_GRID_FRAME = DASHBOARD_DATASETS["mobility_grid_frame"]
MOBILITY_GRID_GEOJSON = DASHBOARD_DATASETS["mobility_grid_geojson"]
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
LAND_USE_DISTRICT_FRAME_CACHE = DASHBOARD_DATASETS["land_use_district_frame_cache"]
LAND_USE_DISTRICT_GEOJSON_CACHE = DASHBOARD_DATASETS["land_use_district_geojson_cache"]
MOBILITY_DISTRICT_FRAME_CACHE = DASHBOARD_DATASETS["mobility_district_frame_cache"]
MOBILITY_DISTRICT_GEOJSON_CACHE = DASHBOARD_DATASETS["mobility_district_geojson_cache"]
CLUSTER_PROFILE_LOOKUP = DASHBOARD_DATASETS["cluster_profile_lookup"]
DISTRICT_TYPOLOGY_LOOKUP = DASHBOARD_DATASETS["district_typology_lookup"]
DISTRICT_ANOMALY_LOOKUP = DASHBOARD_DATASETS["district_anomaly_lookup"]


def format_land_use_signal(label: str | None) -> str:
    if not label:
        return "Not available"
    if label == "Other":
        return "Uncategorized land-use cells"
    return re.sub(r"\s*\(S\.L\.\s*:\s*[^)]*\)", "", label).strip()


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
            {"label": "Economy and employment vulnerability index", "value": "vulnerability_employment"},
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
    selected_districts = canonicalise_selected_districts(
        [district_name] if isinstance(district_name, str) else district_name
    )
    if not selected_districts:
        return []
    if len(selected_districts) == 1:
        district_frame = LAND_USE_DISTRICT_FRAME_CACHE.get(selected_districts[0], pd.DataFrame())
    else:
        district_frame, _ = build_combined_grid_context(
            LAND_USE_DISTRICT_FRAME_CACHE,
            LAND_USE_DISTRICT_GEOJSON_CACHE,
            selected_districts,
        )
    if "lu_2018_class_simplified" not in district_frame.columns:
        return []
    return sorted(district_frame["lu_2018_class_simplified"].dropna().unique().tolist())


def build_land_use_filter_options(district_name: str | list[str] | None) -> list[dict[str, str]]:
    classes = get_land_use_class_values(district_name)
    return [{"label": format_land_use_signal(class_name), "value": class_name} for class_name in classes]


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
        "green": "Greenspaces",
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
        district_cells = MOBILITY_GRID_FRAME.loc[MOBILITY_GRID_FRAME["district_name"] == canonical_district_name].copy()
        cells_above_threshold = district_cells.loc[district_cells["pt_stop_count"] >= mobility_threshold]
        focus_label = "Bus stops per 250m cell"
        focus_value = (
            f"{len(cells_above_threshold):,} cells at threshold"
            if not district_cells.empty
            else "No data available yet"
        )
        rows.extend(
            [
                html.Div([html.Span("Hovered cell", className="map-hover-row-label"), html.Span(f"{int(hovered_stops):,} stops" if hovered_stops is not None else "Not available", className="map-hover-row-value")], className="map-hover-row"),
                html.Div([html.Span("Threshold", className="map-hover-row-label"), html.Span(f"{mobility_threshold}+", className="map-hover-row-value")], className="map-hover-row"),
            ]
        )
    elif topic == "land_use":
        custom_data = point.get("customdata") or []
        hovered_class = custom_data[1] if isinstance(custom_data, (list, tuple)) and len(custom_data) > 1 else None
        district_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(canonical_district_name, GRID_FRAME.head(0).copy())
        selected_classes = normalise_land_use_filter_values(land_use_filter, canonical_district_name)
        available_classes = get_land_use_class_values(canonical_district_name)
        dominant_class = district_cells["lu_2018_class_simplified"].value_counts().idxmax() if not district_cells.empty else "Not available"
        filtered_view = len(selected_classes) != len(available_classes)
        focus_label = "Dominant land-use class"
        focus_value = format_land_use_signal(dominant_class)
        if filtered_view:
            chips.append(build_hover_chip(f"Visible: {len(selected_classes)} classes", "accent"))
        rows.extend(
            [
                html.Div([html.Span("Hovered class", className="map-hover-row-label"), html.Span(format_land_use_signal(hovered_class) if hovered_class else "Not available", className="map-hover-row-value")], className="map-hover-row"),
                html.Div([html.Span("Dominant class", className="map-hover-row-label"), html.Span(format_land_use_signal(dominant_class), className="map-hover-row-value")], className="map-hover-row"),
                html.Div([html.Span("Scope", className="map-hover-row-label"), html.Span("Selected district cells", className="map-hover-row-value")], className="map-hover-row"),
            ]
        )
    elif topic == "height":
        custom_data = point.get("customdata") or []
        mean_value = custom_data[1] if isinstance(custom_data, (list, tuple)) and len(custom_data) > 1 else None
        max_value = custom_data[2] if isinstance(custom_data, (list, tuple)) and len(custom_data) > 2 else None
        district_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(canonical_district_name, GRID_FRAME.head(0).copy()).copy()
        height_cells = district_cells[district_cells["height_mean"].notna()].copy()
        district_mean = height_cells["height_mean"].mean() if not height_cells.empty else None
        district_max = height_cells["height_max"].max() if not height_cells.empty else None
        if metric == "height_mean":
            focus_label = "Mean building height"
            focus_value = f"{district_mean:.1f} m" if isinstance(district_mean, (int, float)) else "No data available yet"
        else:
            focus_label = "Maximum building height"
            focus_value = f"{district_max:.1f} m" if isinstance(district_max, (int, float)) else "No data available yet"
        rows.extend(
            [
                html.Div([html.Span("Hovered cell mean", className="map-hover-row-label"), html.Span(f"{mean_value:.1f} m" if isinstance(mean_value, (int, float)) else "Not available", className="map-hover-row-value")], className="map-hover-row"),
                html.Div([html.Span("Hovered cell max", className="map-hover-row-label"), html.Span(f"{max_value:.1f} m" if isinstance(max_value, (int, float)) else "Not available", className="map-hover-row-value")], className="map-hover-row"),
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
        ],
        className="map-hover-card",
    )


TOPIC_ICON_SVGS = {
    "housing": (
        '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/>'
        '<path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
    ),
    "population": (
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>'
        '<circle cx="9" cy="7" r="4"/>'
        '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/>'
        '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
    ),
    "green": (
        '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/>'
        '<path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>'
    ),
    "land_use": (
        '<path d="m5 8 6-3 6 3 4-2v13l-4 2-6-3-6 3-4-2V6z"/>'
        '<path d="M11 5v13"/>'
        '<path d="M17 8v13"/>'
    ),
    "height": (
        '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/>'
        '<path d="M6 12H4a2 2 0 0 0-2 2v8h4"/>'
        '<path d="M18 9h2a2 2 0 0 1 2 2v11h-4"/>'
        '<path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/>'
    ),
    "mobility": (
        '<rect width="16" height="16" x="4" y="3" rx="2"/>'
        '<path d="M4 11h16"/>'
        '<path d="M12 3v8"/>'
        '<path d="m8 19-2 3"/>'
        '<path d="m18 22-2-3"/>'
        '<path d="M8 15h.01"/><path d="M16 15h.01"/>'
    ),
    "economy": (
        '<path d="M4 10h12"/>'
        '<path d="M4 14h9"/>'
        '<path d="M19 6a7.7 7.7 0 0 0-5.2-2A7.9 7.9 0 0 0 6 12c0 4.4 3.5 8 7.8 8 2 0 3.8-.8 5.2-2"/>'
    ),
    "employment": (
        '<rect width="20" height="14" x="2" y="7" rx="2"/>'
        '<path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        '<path d="M2 13h20"/>'
        '<path d="M12 12v2"/>'
    ),
    "vulnerability": (
        '<path d="M12 22s8-4 8-10V6l-8-4-8 4v6c0 6 8 10 8 10"/>'
        '<path d="m9 9 6 6"/>'
        '<path d="m15 9-6 6"/>'
    ),
}


def build_topic_icon(topic: str, stroke: str = "#111827", class_name: str = "topic-icon-svg") -> html.Img:
    svg_inner = TOPIC_ICON_SVGS.get(topic, TOPIC_ICON_SVGS["population"])
    return build_lucide_icon_with_color(svg_inner, stroke=stroke, class_name=class_name)


def build_title_topic_icon(topic: str, color: str) -> html.Span:
    return html.Span(
        build_topic_icon(topic, stroke="#ffffff", class_name="panel-title-icon-glyph"),
        className="panel-title-icon-badge",
        style={"backgroundColor": color},
    )


ICON_HOUSING = build_topic_icon("housing")
ICON_POPULATION = build_topic_icon("population")
ICON_GREEN = build_topic_icon("green")
ICON_LAND_USE = build_topic_icon("land_use")
ICON_HEIGHT = build_topic_icon("height")
ICON_MOBILITY = build_topic_icon("mobility")
ICON_ECONOMY = build_topic_icon("economy")
ICON_EMPLOYMENT = build_topic_icon("employment")
ICON_VULNERABILITY = build_topic_icon("vulnerability")
ICON_CLOSE = build_lucide_icon(
    '<path d="M18 6 6 18"/>'
    '<path d="m6 6 12 12"/>'
)
ICON_SEARCH = build_lucide_icon(
    '<circle cx="11" cy="11" r="7"/>'
    '<path d="m21 21-4.3-4.3"/>'
)
PIPELINE_STAGE_SOURCE_SVG = (
    '<ellipse cx="12" cy="5" rx="6" ry="3"/>'
    '<path d="M6 5v6c0 1.7 2.7 3 6 3s6-1.3 6-3V5"/>'
    '<path d="M6 11v6c0 1.7 2.7 3 6 3s6-1.3 6-3v-6"/>'
)
PIPELINE_STAGE_CLEANING_SVG = (
    '<path d="M22 3H2l8 9.46V19l4 2v-8.54z"/>'
)
PIPELINE_STAGE_PREP_SVG = (
    '<path d="M12 3h2a2 2 0 0 1 2 2v2h2a2 2 0 0 1 2 2v2h-2a2 2 0 0 0-2 2 2 2 0 0 1-2 2h-2v2a2 2 0 0 1-2 2H8v-2a2 2 0 0 0-2-2 2 2 0 0 1-2-2v-2h2a2 2 0 0 0 2-2 2 2 0 0 1 2-2h2z"/>'
)
PIPELINE_STAGE_VALIDATE_SVG = (
    '<circle cx="6" cy="12" r="2"/>'
    '<circle cx="18" cy="6" r="2"/>'
    '<circle cx="18" cy="18" r="2"/>'
    '<circle cx="12" cy="12" r="2"/>'
    '<path d="M8 12h2"/>'
    '<path d="M13.5 10.5l3-3"/>'
    '<path d="M13.5 13.5l3 3"/>'
)
PIPELINE_STAGE_REPRESENT_SVG = (
    '<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M8 20h8"/><path d="M12 17v3"/>'
)


def build_pipeline_stage_icon(svg_inner: str, is_active: bool) -> str:
    return build_lucide_icon_data_uri(svg_inner, stroke="#111827")
PANEL_META_DATA_ICON = build_lucide_icon_data_uri(
    (
        '<circle cx="6" cy="6" r="3"/>'
        '<circle cx="18" cy="6" r="3"/>'
        '<circle cx="12" cy="18" r="3"/>'
        '<path d="M6 9v2a4 4 0 0 0 4 4h2"/>'
        '<path d="M18 9v2a4 4 0 0 1-4 4h-2"/>'
        '<path d="M12 15v0"/>'
    ),
    stroke="#486175",
)
PANEL_META_ALERT_ICON = build_lucide_icon_data_uri(
    '<path d="m10.29 3.86-8 14A1 1 0 0 0 3.16 19h17.68a1 1 0 0 0 .87-1.5l-8-14a1 1 0 0 0-1.74 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    stroke="#f59e0b",
)
PANEL_ML_ICON = build_lucide_icon_data_uri(
    '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.75c.63.44 1 1.15 1 1.92V17h6v-.33c0-.77.37-1.48 1-1.92A7 7 0 0 0 12 2z"/>',
    stroke="#111827",
)
PIPELINE_FILE_ICON = build_file_icon_data_uri(stroke="#486175")


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
        "Economy and employment vulnerability index": "Economy and employment<br>vulnerability index",
        "Mean building height": "Mean building<br>height",
        "Maximum building height": "Maximum building<br>height",
        "Building height (m)": "Building height<br>(m)",
    }
    return line_break_map.get(label, label)


def get_onboarding_step(step_index: int) -> dict[str, str]:
    steps = [
        {
            "target": "district",
            "eyebrow": "Step 1",
            "title": "Start with one district",
            "body": "Select one district from the list or map to unlock the topic layer.",
            "next_label": "Select a district first",
        },
        {
            "target": "topic",
            "eyebrow": "Step 2",
            "title": "Choose a topic",
            "body": "Pick one topic to load the district view and its supporting sidebar content.",
            "next_label": "Choose a topic first",
        },
        {
            "target": "mode",
            "eyebrow": "Step 3",
            "title": "Switch modes and compare later",
            "body": "Use Display mode to read results and Pipeline mode to understand how the view was produced. You can later add a second district to compare.",
            "next_label": "Finish",
        },
    ]
    bounded_index = max(0, min(step_index, len(steps) - 1))
    return steps[bounded_index]


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


def describe_relative_band(
    series: pd.Series,
    value: float | int | None,
    lower_label: str,
    middle_label: str,
    upper_label: str,
) -> str:
    if value is None or pd.isna(value):
        return middle_label
    clean = series.dropna()
    if clean.empty:
        return middle_label
    lower_cut = clean.quantile(1 / 3)
    upper_cut = clean.quantile(2 / 3)
    if value <= lower_cut:
        return lower_label
    if value >= upper_cut:
        return upper_label
    return middle_label


def build_summary_chip(label: str, tone: str = "neutral") -> html.Span:
    return html.Span(label, className=f"panel-summary-chip panel-summary-chip-{tone}")


def build_summary_chip_row(labels: list[str], tone: str = "neutral") -> html.Div | None:
    clean_labels = [label.strip() for label in labels if label and label.strip()]
    if not clean_labels:
        return None
    return html.Div(
        [build_summary_chip(label, tone) for label in clean_labels],
        className="panel-summary-chip-row",
    )


def values_share_relative_band(
    series: pd.Series,
    first_value: float | int | None,
    second_value: float | int | None,
) -> bool:
    if first_value is None or second_value is None or pd.isna(first_value) or pd.isna(second_value):
        return False
    clean = series.dropna()
    if clean.empty:
        return False
    lower_cut = clean.quantile(1 / 3)
    upper_cut = clean.quantile(2 / 3)

    def get_band(value: float | int) -> str:
        if value <= lower_cut:
            return "lower"
        if value >= upper_cut:
            return "upper"
        return "middle"

    return get_band(first_value) == get_band(second_value)


def get_mobility_spread_chip(district_name: str, mobility_threshold: int) -> str:
    district_cells = MOBILITY_GRID_FRAME.loc[MOBILITY_GRID_FRAME["district_name"] == district_name].copy()
    if district_cells.empty:
        return "No data"

    qualifying_cells = district_cells.loc[district_cells["pt_stop_count"] >= mobility_threshold, "cell_id"].astype(str)
    if qualifying_cells.empty:
        return "Stops concentrated in fewer areas"

    district_geojson = MOBILITY_DISTRICT_GEOJSON_CACHE.get(district_name, {"features": []})
    centroid_rows: list[tuple[str, float, float]] = []
    for feature in district_geojson.get("features", []):
        cell_id = str(feature.get("properties", {}).get("cell_id", feature.get("id", "")))
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        if not coordinates:
            continue
        ring = coordinates[0]
        if not ring:
            continue
        lon_values = [point[0] for point in ring]
        lat_values = [point[1] for point in ring]
        centroid_rows.append((cell_id, sum(lon_values) / len(lon_values), sum(lat_values) / len(lat_values)))

    centroid_frame = pd.DataFrame(centroid_rows, columns=["cell_id", "centroid_lon", "centroid_lat"])
    if centroid_frame.empty:
        share_above_threshold = (district_cells["pt_stop_count"] >= mobility_threshold).mean()
        return (
            "Stops concentrated in fewer areas"
            if share_above_threshold < 0.25
            else "Stops spread unevenly"
            if share_above_threshold < 0.55
            else "Stops spread widely"
        )

    centroid_frame["is_qualifying"] = centroid_frame["cell_id"].isin(set(qualifying_cells.tolist()))
    lon_min = centroid_frame["centroid_lon"].min()
    lon_max = centroid_frame["centroid_lon"].max()
    lat_min = centroid_frame["centroid_lat"].min()
    lat_max = centroid_frame["centroid_lat"].max()

    if lon_min == lon_max or lat_min == lat_max:
        qualifying_share = centroid_frame["is_qualifying"].mean()
        return (
            "Stops concentrated in fewer areas"
            if qualifying_share < 0.25
            else "Stops spread unevenly"
            if qualifying_share < 0.55
            else "Stops spread widely"
        )

    lon_edges = [lon_min, lon_min + (lon_max - lon_min) / 3, lon_min + 2 * (lon_max - lon_min) / 3, lon_max]
    lat_edges = [lat_min, lat_min + (lat_max - lat_min) / 3, lat_min + 2 * (lat_max - lat_min) / 3, lat_max]
    centroid_frame["lon_zone"] = pd.cut(
        centroid_frame["centroid_lon"],
        bins=lon_edges,
        labels=["west", "central", "east"],
        include_lowest=True,
        duplicates="drop",
    )
    centroid_frame["lat_zone"] = pd.cut(
        centroid_frame["centroid_lat"],
        bins=lat_edges,
        labels=["south", "middle", "north"],
        include_lowest=True,
        duplicates="drop",
    )
    centroid_frame["zone_key"] = centroid_frame["lon_zone"].astype(str) + "|" + centroid_frame["lat_zone"].astype(str)

    occupied_zone_share = (
        centroid_frame.loc[centroid_frame["is_qualifying"], "zone_key"].nunique()
        / max(centroid_frame["zone_key"].nunique(), 1)
    )
    if occupied_zone_share < 0.34:
        return "Stops concentrated in fewer areas"
    if occupied_zone_share < 0.67:
        return "Stops spread unevenly"
    return "Stops spread widely"


def format_land_use_chip(label: str | None) -> str:
    clean_label = format_land_use_signal(label)
    chip_map = {
        "Continuous urban fabric": "Continuous urban",
        "Discontinuous dense urban fabric": "Dense urban",
        "Industrial, commercial, public, military and private units": "Workplace land",
        "Road and rail networks and associated land": "Transport land",
        "Green urban areas": "Urban green",
        "Herbaceous vegetation associations": "Open green",
        "Arable land": "Arable land",
        "Pastures": "Pastures",
        "Forest": "Forest",
        "Water": "Water",
        "Uncategorized land-use cells": "Other land use",
    }
    for source, target in chip_map.items():
        if clean_label.startswith(source):
            return target
    return clean_label


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


def build_panel_info_bubble(message: str, title: str) -> html.Div:
    return html.Div(
        [
            html.Button(
                "i",
                className="inline-info-chip panel-inline-info-chip",
                tabIndex=-1,
            ),
            html.Div(
                [
                    html.Div(title, className="inline-info-bubble-title"),
                    html.Div(message),
                ],
                className="inline-info-bubble panel-inline-info-bubble",
            ),
        ],
        className="inline-info-wrap panel-inline-info-wrap",
    )


def build_metric_info_bubble(message: str, title: str = "About this metric") -> html.Div:
    return html.Div(
        [
            html.Button(
                "i",
                className="inline-info-chip metric-info-chip",
                tabIndex=-1,
            ),
            html.Div(
                [
                    html.Div(title, className="inline-info-bubble-title"),
                    html.Div(message),
                ],
                className="inline-info-bubble metric-info-bubble",
            ),
        ],
        className="inline-info-wrap metric-info-wrap",
    )


def build_metric_label_with_info(label: str, message: str, title: str = "About this metric") -> html.Div:
    return html.Div(
        [
            html.P(label, className="metric-label metric-label-inline"),
            build_metric_info_bubble(message, title),
        ],
        className="metric-label-row",
    )


def build_panel_heading_with_info(title: str, message: str, bubble_title: str) -> html.Div:
    return html.Div(
        [
            html.H4(title, className="panel-inline-heading-title"),
            build_panel_info_bubble(message, bubble_title),
        ],
        className="panel-inline-heading",
    )


def build_term_hint(term: str, message: str) -> html.Span:
    return html.Span(
        [
            html.Span(term, className="panel-term-text"),
            html.Span(message, className="panel-term-bubble"),
        ],
        className="panel-term-hint",
        tabIndex=0,
    )


def build_source_link(label: str, href: str | None) -> html.Span | html.A:
    if not href:
        return html.Span(label, className="panel-meta-plain-text")
    return html.A(label, href=href, target="_blank", rel="noreferrer", className="panel-meta-link")


def build_panel_meta_item(
    icon_src: str,
    title: str,
    content: html.Div | html.P | html.Ul,
    tone: str = "neutral",
) -> html.Div:
    return html.Div(
        [
            html.Img(src=icon_src, alt="", className="panel-meta-icon", draggable="false"),
            html.Div(
                [
                    html.Div(title, className="panel-meta-title"),
                    content,
                ],
                className="panel-meta-content",
            ),
        ],
        className=f"panel-meta-item panel-meta-item-{tone}",
    )


def build_panel_meta_links(items: list[tuple[str, str | None]]) -> html.Div:
    children = []
    for index, (label, href) in enumerate(items):
        if index:
            children.append(html.Span(" / ", className="panel-meta-separator"))
        children.append(build_source_link(label, href))
    return html.Div(children, className="panel-meta-links")
