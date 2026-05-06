import json
import re
from io import StringIO
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import ALL, Dash, Input, Output, State, callback_context, dcc, html, no_update
from shapely.geometry import GeometryCollection, LineString, MultiLineString, shape as geometry_shape
from shapely.validation import make_valid

from src.dashboard_context import build_dashboard_datasets
from src.feature_engineering import normalise_district_name


DEFAULT_DISTRICT = "Centro"
DEFAULT_TOPIC = "population"
DEFAULT_MOBILITY_THRESHOLD = 2
MOBILITY_SLIDER_MAX = 10
MAP_UIREVISION = "district-map-shared-view"
DEFAULT_VIEW_MODE = "display"
DEFAULT_DISPLAY_SELECTION_MODE = "inspect"
DEFAULT_PIPELINE_STAGE = "source_intake"
PROJECT_ROOT = Path(__file__).resolve().parent
GRID_TOPICS = {"land_use", "height", "mobility"}


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

COMPARE_DISTRICT_COLORS = ("#2563eb", "#f4a261")


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
LAND_USE_ALL_VALUE = "__all__"


LAND_USE_DISTRICT_FRAME_CACHE = DASHBOARD_DATASETS["land_use_district_frame_cache"]
LAND_USE_DISTRICT_GEOJSON_CACHE = DASHBOARD_DATASETS["land_use_district_geojson_cache"]
MOBILITY_DISTRICT_FRAME_CACHE = DASHBOARD_DATASETS["mobility_district_frame_cache"]
MOBILITY_DISTRICT_GEOJSON_CACHE = DASHBOARD_DATASETS["mobility_district_geojson_cache"]
CLUSTER_PROFILE_LOOKUP = DASHBOARD_DATASETS["cluster_profile_lookup"]
DISTRICT_TYPOLOGY_LOOKUP = DASHBOARD_DATASETS["district_typology_lookup"]
DISTRICT_ANOMALY_LOOKUP = DASHBOARD_DATASETS["district_anomaly_lookup"]


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
    if "lu_2018_class_simplified" not in district_frame.columns:
        return []
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
PIPELINE_STAGE_SOURCE_SVG = (
    '<ellipse cx="12" cy="5" rx="6" ry="3"/>'
    '<path d="M6 5v6c0 1.7 2.7 3 6 3s6-1.3 6-3V5"/>'
    '<path d="M6 11v6c0 1.7 2.7 3 6 3s6-1.3 6-3v-6"/>'
)
PIPELINE_STAGE_CLEANING_SVG = (
    '<path d="M4 5h16"/><path d="M7 5v14"/><path d="M17 5v14"/><path d="M10 10h4"/><path d="M9 14h6"/>'
)
PIPELINE_STAGE_PREP_SVG = (
    '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><rect x="4" y="17" width="16" height="4" rx="1"/>'
)
PIPELINE_STAGE_VALIDATE_SVG = (
    '<circle cx="12" cy="12" r="8"/><path d="m9 12 2 2 4-4"/>'
)
PIPELINE_STAGE_REPRESENT_SVG = (
    '<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M8 20h8"/><path d="M12 17v3"/>'
)


def build_pipeline_stage_icon(svg_inner: str, is_active: bool) -> str:
    return build_lucide_icon_data_uri(svg_inner, stroke="#111827" if is_active else "#7c3aed")
PANEL_META_DATA_ICON = build_lucide_icon_data_uri(
    '<path d="M14 3v4"/><path d="M18 3v4"/><path d="M6 7h12"/><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 11h8"/><path d="M8 15h5"/>',
    stroke="#486175",
)
PANEL_META_ALERT_ICON = build_lucide_icon_data_uri(
    '<path d="m10.29 3.86-8 14A1 1 0 0 0 3.16 19h17.68a1 1 0 0 0 .87-1.5l-8-14a1 1 0 0 0-1.74 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    stroke="#dc2626",
)
PANEL_ML_ICON = build_lucide_icon_data_uri(
    '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.75c.63.44 1 1.15 1 1.92V17h6v-.33c0-.77.37-1.48 1-1.92A7 7 0 0 0 12 2z"/>',
    stroke="#7c3aed",
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
        "vulnerability_employment": "Economy and employment vulnerability index",
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
    if topic == "housing" and not unavailable.empty:
        add_unavailable_hatch_overlay(figure, unavailable["district_name"].tolist())
    elif not unavailable.empty:
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


def iter_clipped_line_segments(geometry):
    if geometry.is_empty:
        return
    if isinstance(geometry, LineString):
        yield geometry
        return
    if isinstance(geometry, MultiLineString):
        for line in geometry.geoms:
            if not line.is_empty:
                yield line
        return
    if isinstance(geometry, GeometryCollection):
        for item in geometry.geoms:
            yield from iter_clipped_line_segments(item)


def build_hatch_segments_for_geometry(geometry, spacing: float = 0.0032):
    minx, miny, maxx, maxy = geometry.bounds
    pad = max(maxx - minx, maxy - miny) * 0.35
    start = (miny - maxx) - pad
    end = (maxy - minx) + pad
    hatch_lines = []
    offset = start
    while offset <= end:
        x0 = minx - pad
        x1 = maxx + pad
        candidate = LineString(
            [
                (x0, x0 + offset),
                (x1, x1 + offset),
            ]
        )
        clipped = candidate.intersection(geometry)
        hatch_lines.extend(iter_clipped_line_segments(clipped))
        offset += spacing
    return hatch_lines


def add_unavailable_hatch_overlay(figure, district_names: list[str]):
    for district_name in district_names:
        geometry = DISTRICT_SHAPES.get(district_name)
        if geometry is None:
            continue
        for segment in build_hatch_segments_for_geometry(geometry):
            coords = list(segment.coords)
            if len(coords) < 2:
                continue
            figure.add_trace(
                go.Scattergeo(
                    lon=[point[0] for point in coords],
                    lat=[point[1] for point in coords],
                    mode="lines",
                    line={"color": "rgba(71,85,105,0.68)", "width": 1.15},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )


def add_selected_district_outlines(figure, district_names: list[str] | None):
    selected_districts = canonicalise_selected_districts(district_names)
    outline_styles = [
        {"color": COMPARE_DISTRICT_COLORS[0], "width": 2.8},
        {"color": COMPARE_DISTRICT_COLORS[1], "width": 2.4},
    ]
    styled_districts = [
        (district_name, outline_styles[min(index, len(outline_styles) - 1)])
        for index, district_name in enumerate(selected_districts)
    ]

    for district_name, style in reversed(styled_districts):
        selected_features = [
            feature for feature in DISTRICT_GEOJSON["features"]
            if feature["id"] == district_name
        ]
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
    show_typology_section: bool = True,
    show_anomaly_section: bool = True,
    panel_position: int = 1,
) -> html.Div:
    canonical_district_name = DISTRICT_NAME_BY_KEY.get(normalise_district_name(district_name), district_name)
    district_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == canonical_district_name].iloc[0]
    district_name = canonical_district_name
    typology_section = None
    anomaly_section = None
    metric_label_node = None
    sources_text = "Madrid district boundaries"
    reference_date = "Not available yet"
    source_links: list[tuple[str, str | None]] = []
    if topic == "land_use":
        if show_typology_section:
            typology_section = build_typology_section(district_name, topic)
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
            "Use this as a broad spatial summary. It shows the main land-use character across the district's grid cells, "
            "not parcel-level land use on every site."
        )
        caveat_line = "This is a simplified land-use layer for spatial context, not parcel-level zoning."
        sources_text = "Urban Atlas-based 250m grid + Madrid district boundaries"
        reference_date = "Land-use layer: 2018"
        source_links = [
            ("Urban Atlas", "https://land.copernicus.eu/en/products/urban-atlas"),
            ("District boundaries", None),
        ]
    elif topic == "height":
        if show_typology_section:
            typology_section = build_typology_section(district_name, topic)
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
            "This helps show the district's built form. It is most useful for spotting broad differences in height across the district."
        )
        production_text = "Use this as a broad height pattern, not as an exact reading for each building."
        caveat_line = "Height values are generalized grid estimates, not exact building measurements."
        sources_text = "Urban Atlas building-height layer + Madrid district boundaries"
        reference_date = "Reference year not explicitly documented in current source notes"
        source_links = [
            ("Urban Atlas building height", "https://land.copernicus.eu/en/products/urban-atlas?tab=building_height"),
            ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
        ]
    elif topic == "mobility":
        if show_typology_section:
            typology_section = build_typology_section(district_name, topic)
        district_cells = MOBILITY_GRID_FRAME.loc[MOBILITY_GRID_FRAME["district_name"] == district_name].copy()
        cells_above_threshold = district_cells.loc[district_cells["pt_stop_count"] >= mobility_threshold]
        has_data = not district_cells.empty
        topic_label = "Mobility"
        metric_label = "Bus stops per 250m cell"
        if has_data:
            metric_value = f"{len(cells_above_threshold):,} cells at threshold"
            key_finding = (
                f"{district_name} has {len(cells_above_threshold):,} grid cells with at least "
                f"{mobility_threshold} bus stops in the current mobility layer."
            )
            meaning_text = (
                "This helps show where stop access is more concentrated within the district. It is useful for comparing broad spatial patterns, not service quality in full."
            )
            production_text = (
                "Use this as a stop concentration view. It shows where stops cluster across grid cells, not how frequent or reliable service is."
            )
            caveat_line = "This shows stop concentration by grid cell, not full public transport quality."
            reference_date = "2018"
        else:
            metric_value = "No data available yet"
            key_finding = f"{district_name} does not have mobility grid data available yet for this MVP slice."
            meaning_text = "The district is still shown, but this topic does not yet have matching mobility cells here."
            production_text = "Treat this as a data coverage gap rather than as evidence of low mobility access."
            caveat_line = "Research-derived grid topics may still have partial coverage."
        sources_text = "Public transportation usage dataset (2018), Kaggle + Madrid district boundaries"
        source_links = [
            ("Public transportation usage dataset (2018), Kaggle", "https://www.kaggle.com/datasets/dataguapa/madrid-public-transportation-data-2018"),
            ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
        ]
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
            f"Housing data is not available yet for {district_name} in this dashboard view."
            if not has_data
            else (
                f"{district_name} has {int(district_row['housing_total']):,} EMVS public housing allocations, "
                f"equal to {format_housing_rate(district_row['housing_per_1000_residents'])}."
            )
        )
        meaning_text = (
            "The district is still shown so the data gap stays visible."
            if not has_data
            else (
                "This gives a focused view of public housing provision in the district. It does not describe the full housing market."
            )
        )
        production_text = (
            "This topic does not yet have a matching district value in the current dashboard data."
            if not has_data
            else (
                "Read these values as public housing context at district level. They are most useful for comparing provision across districts."
            )
        )
        reference_date = "1 June 2015 to 30 April 2023" if has_data else "Not available yet"
        caveat_line = "EMVS values describe public housing allocation, not total housing supply or affordability."
        sources_text = "EMVS housing CSV + Madrid Population API + Madrid district boundaries"
        source_links = [
            ("EMVS housing CSV", None),
            ("Madrid Population API", "https://datos.madrid.es/dataset/300557-0-poblacion-distrito-barrio"),
            ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
        ]
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
            f"Green-space data is not available yet for {district_name} in this dashboard view."
            if not has_data
            else (
                f"{district_name} has {format_float(district_row['green_area_ha'], ' ha')} of district green space, "
                f"equal to {format_float(district_row['green_area_per_10000'], ' ha / 10,000 residents')}."
            )
        )
        meaning_text = (
            "The district is still shown so the data gap stays visible."
            if not has_data
            else "This shows how much green space is recorded for the district. It helps compare overall provision across districts."
        )
        production_text = (
            "This topic does not yet have a matching district value in the current dashboard data."
            if not has_data
            else "Read this as district-wide green provision, not as direct access from a specific street or address."
        )
        reference_date = f"Indicator year {int(district_row['green_area_per_10000_year'])}" if has_data and not pd.isna(district_row.get("green_area_per_10000_year")) else "Not available yet"
        caveat_line = "This is district-level green-space provision, not direct park accessibility from a specific address."
        sources_text = "Madrid district indicator panel + Madrid district boundaries"
        source_links = [
            ("Madrid district indicator panel", "https://datos.madrid.es/dataset/300087-0-indicadores-distritos"),
            ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
        ]
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
            f"Income data is not available yet for {district_name} in this dashboard view."
            if not has_data
            else (
                f"{district_name} records {format_float(district_row['income_per_person'], ' €', 0)} income per person "
                f"and {format_float(district_row['household_income'], ' €', 0)} household income."
            )
        )
        meaning_text = (
            "The district is still shown so the data gap stays visible."
            if not has_data
            else "This gives a broad picture of local economic conditions in the district. It does not show the full spread of incomes within the district."
        )
        production_text = (
            "This topic does not yet have a matching district value in the current dashboard data."
            if not has_data
            else "Use this as district context for comparison, not as a description of every household."
        )
        reference_date = f"Indicator year {int(district_row['income_per_person_year'])}" if has_data and not pd.isna(district_row.get("income_per_person_year")) else "Not available yet"
        caveat_line = "These are panel indicators and should be read as district context, not household-level distributions."
        sources_text = "Madrid district indicator panel + Madrid district boundaries"
        source_links = [
            ("Madrid district indicator panel", "https://datos.madrid.es/dataset/300087-0-indicadores-distritos"),
            ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
        ]
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
            f"Employment data is not available yet for {district_name} in this dashboard view."
            if not has_data
            else (
                f"{district_name} records {format_float(district_row['unemployment_total'], '', 0)} registered unemployed people "
                f"and an unemployment rate of {format_float(district_row['unemployment_rate'], '%', 2)}."
            )
        )
        meaning_text = (
            "The district is still shown so the data gap stays visible."
            if not has_data
            else "This gives a broad picture of labor-market pressure in the district and helps compare districts at a high level."
        )
        production_text = (
            "This topic does not yet have a matching district value in the current dashboard data."
            if not has_data
            else "Use this as district context rather than as a full picture of employment conditions."
        )
        reference_date = f"Indicator year {int(district_row['unemployment_rate_year'])}" if has_data and not pd.isna(district_row.get("unemployment_rate_year")) else "Not available yet"
        caveat_line = "These values reflect registered unemployment indicators, not the full labor market picture."
        sources_text = "Madrid district indicator panel + Madrid district boundaries"
        source_links = [
            ("Madrid district indicator panel", "https://datos.madrid.es/dataset/300087-0-indicadores-distritos"),
            ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
        ]
    elif topic == "vulnerability":
        has_data = bool(district_row["has_vulnerability_data"])
        topic_label = "Vulnerability"
        metric_label = (
            "Territorial vulnerability index"
            if metric == "vulnerability_index"
            else "Economy and employment vulnerability index"
        )
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
            f"Vulnerability data is not available yet for {district_name} in this dashboard view."
            if not has_data
            else (
                f"{district_name} shows a territorial vulnerability index of {format_float(district_row['vulnerability_index'])} "
                f"and an economy and employment vulnerability index of {format_float(district_row['vulnerability_employment'])}."
            )
        )
        meaning_text = (
            "The district is still shown so the data gap stays visible."
            if not has_data
            else "These indices help compare broader social and economic pressure across districts."
        )
        production_text = (
            "This topic does not yet have a matching district value in the current dashboard data."
            if not has_data
            else "Read these as broad comparative indices, not as direct explanations of cause."
        )
        reference_date = f"Indicator year {int(district_row['vulnerability_index_year'])}" if has_data and not pd.isna(district_row.get("vulnerability_index_year")) else "Not available yet"
        caveat_line = "These are composite municipal panel indices and should be read as comparative context rather than direct causal explanations."
        sources_text = "Madrid district indicator panel + Madrid district boundaries"
        source_links = [
            ("Madrid district indicator panel", "https://datos.madrid.es/dataset/300087-0-indicadores-distritos"),
            ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
        ]
        vulnerability_metric_help = (
            "This is a composite district index from Madrid's IGUALA system. It combines several dimensions of vulnerability, including social conditions, urban environment and mobility, education and culture, economy and employment, and health. Higher values indicate higher relative vulnerability and are best used for high-level district comparison."
            if metric == "vulnerability_index"
            else "This is the economy and employment part of Madrid's IGUALA vulnerability system. It reflects district-level pressure linked to employment and economic conditions. Higher values indicate higher relative vulnerability in this dimension, and the index should be read as comparative context rather than as a direct measure of unemployment alone."
        )
        metric_label_node = build_metric_label_with_info(metric_label, vulnerability_metric_help)
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
            f"Population data is not available yet for {district_name} in this dashboard view."
            if not has_data
            else (
                f"{district_name} has {district_row['population_total']:,} residents and a population density "
                f"of {density_text}."
            )
        )
        meaning_text = (
            "The district is still shown so the data gap stays visible."
            if not has_data
            else (
                "This gives a simple district-level view of how many people live here and how concentrated they are."
            )
        )
        production_text = (
            "This topic does not yet have a matching district value in the current dashboard data."
            if not has_data
            else (
                "These values work well for district-to-district comparison, but density reflects the whole district area rather than only built-up land."
            )
        )
        caveat_line = "Density is derived from administrative district area, not built-up area."
        sources_text = "Madrid Population API + Madrid district boundaries"
        source_links = [
            ("Madrid Population API", "https://datos.madrid.es/dataset/300557-0-poblacion-distrito-barrio"),
            ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
        ]

    content_children = [
        html.Div(
            [
                html.Span(
                    className="panel-title-dot",
                    style={"backgroundColor": get_compare_color(panel_position)},
                    **{"aria-hidden": "true"},
                ),
                html.H2(district_name, className="panel-title"),
            ],
            className="panel-title-row",
        ),
        html.P(topic_label, className="panel-subtitle"),
        html.Div(
            [
                html.H3(metric_value, className="metric-value"),
                metric_label_node or html.P(metric_label, className="metric-label"),
            ],
            className="metric-card",
        ),
    ]
    is_grid_topic = topic in {"land_use", "height", "mobility"}
    if is_grid_topic:
        panel_body_children = [
            html.H4("What we see"),
            html.P(emphasize_numbers(key_finding)),
            html.H4("Why it matters"),
            html.P(emphasize_numbers(meaning_text)),
            html.H4("How to read it"),
            html.P(emphasize_numbers(production_text)),
        ]
    else:
        panel_body_children = [
            html.H4("What we see"),
            html.P(emphasize_numbers(key_finding)),
            html.H4("Why it matters"),
            html.P(emphasize_numbers(meaning_text)),
            html.H4("How to read it"),
            html.P(emphasize_numbers(production_text)),
        ]
    content_children.append(
        html.Div(
            panel_body_children,
            className="panel-body",
        )
    )
    if typology_section is not None:
        content_children.append(typology_section)
    if show_anomaly_section and not is_grid_topic:
        anomaly_section = build_district_mismatch_section(district_name)
        if anomaly_section is not None:
            content_children.append(anomaly_section)
    if is_grid_topic:
        content_children.append(
            html.Div(
                [
                    build_panel_meta_item(
                        PANEL_META_DATA_ICON,
                        "Source",
                        html.Div(
                            [
                                html.P(sources_text, className="panel-meta-text"),
                                build_panel_meta_links(source_links),
                                html.P(f"Reference date: {reference_date}", className="panel-meta-subtext"),
                            ]
                        ),
                        tone="plain",
                    ),
                    build_panel_meta_item(
                        PANEL_META_ALERT_ICON,
                        "Keep in mind",
                        html.Ul(
                            [
                                html.Li(caveat_line),
                                html.Li("Districts without matching topic data appear in grey."),
                            ],
                            className="panel-meta-list",
                        ),
                        tone="warning",
                    ),
                ],
                className="panel-meta-grid",
            )
        )
    else:
        source_data_children = []
        if not has_data:
            source_data_children.append(
                html.P(
                    "No matching topic value is currently available for this district in the dashboard data.",
                    className="panel-meta-text",
                )
            )
        if has_data or not source_links:
            source_data_children.append(html.P(sources_text, className="panel-meta-text"))
        source_data_children.extend(
            [
                build_panel_meta_links(source_links),
                html.P(f"Reference date: {reference_date}", className="panel-meta-subtext"),
            ]
        )
        content_children.append(
            html.Div(
                [
                    build_panel_meta_item(
                        PANEL_META_DATA_ICON,
                        "Source",
                        html.Div(source_data_children),
                        tone="plain",
                    ),
                    build_panel_meta_item(
                        PANEL_META_ALERT_ICON,
                        "Keep in mind",
                        html.Ul(
                            [
                                html.Li(caveat_line),
                                html.Li("Districts without matching topic data appear in grey."),
                            ],
                            className="panel-meta-list",
                        ),
                        tone="warning",
                    ),
                ],
                className="panel-meta-grid",
            )
        )
    return html.Div(content_children, className="right-panel-content")


def build_topic_prompt_panel(district_name: str, is_comparison: bool = False, panel_position: int = 1):
    guidance_text = (
        "Choose a shared topic to open both district sidebars and compare them with the same lens."
        if is_comparison
        else "Choose a topic to open this district's explanation and metric summary."
    )
    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        className="panel-title-dot",
                        style={"backgroundColor": get_compare_color(panel_position)},
                        **{"aria-hidden": "true"},
                    ),
                    html.H2(district_name, className="panel-title"),
                ],
                className="panel-title-row",
            ),
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


def format_typology_share(share: float | None) -> str:
    if share is None:
        return "Not available"
    return f"{share * 100:.0f}% of district grid cells"


def describe_height_band(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "height pattern not available"
    if value < 10:
        return "lower-rise fabric"
    if value < 20:
        return "mid-rise fabric"
    return "taller urban fabric"


def describe_pt_band(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "transport access pattern not available"
    if value < 1.5:
        return "lower stop intensity"
    if value < 4:
        return "moderate stop intensity"
    return "higher stop intensity"


def format_land_use_signal(label: str | None) -> str:
    if not label:
        return "Not available"
    if label == "Other":
        return "Uncategorized land-use cells"
    return label


def format_typology_label(label: str | None) -> str:
    label_map = {
        "Dense urban fabric": "Compact urban areas",
        "Mid-rise accessible mixed fabric": "Transit-connected urban areas",
        "Mixed urban fabric": "Lower-rise mixed areas",
    }
    if not label:
        return "Urban pattern summary"
    return label_map.get(label, label)


def format_anomaly_feature_label(feature_name: str) -> str:
    if feature_name.startswith("cluster_share_cluster_"):
        return "district pattern mix"
    label_map = {
        "population_density_km2": "population density",
        "housing_per_1000_residents": "public housing per 1,000 residents",
        "green_area_per_10000": "green-space provision",
        "income_per_person": "income per person",
        "household_income": "household income",
        "unemployment_rate": "unemployment rate",
        "vulnerability_index": "territorial vulnerability",
        "vulnerability_employment": "employment vulnerability",
        "grid_pt_access_good_share": "public transport access",
        "grid_height_mean_avg": "average building height",
        "grid_green_like_share": "green/open-land share",
        "grid_dense_urban_share": "dense urban structure",
    }
    return label_map.get(feature_name, feature_name.replace("_", " "))


def format_feature_list(items: list[str]) -> str:
    if not items:
        return "overall district profile"
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def build_typology_topic_bridge(topic: str) -> str:
    if topic == "land_use":
        return "It adds a district-wide pattern view behind the land-use map."
    if topic == "mobility":
        return "It adds a district-wide pattern view behind the mobility map."
    return "It adds a district-wide pattern view behind the height map."


def get_typology_compare_payload(district_name: str) -> dict | None:
    district_typology = DISTRICT_TYPOLOGY_LOOKUP.get(district_name)
    if not district_typology:
        return None

    dominant_cluster_label = district_typology.get("dominant_cluster_label")
    if not dominant_cluster_label:
        return None

    cluster_shares = district_typology.get("cluster_shares", {})
    if not cluster_shares:
        return None

    dominant_profile = CLUSTER_PROFILE_LOOKUP.get(dominant_cluster_label, {})
    sorted_shares = sorted(cluster_shares.items(), key=lambda item: item[1], reverse=True)
    second_share = sorted_shares[1][1] if len(sorted_shares) > 1 else 0.0

    return {
        "district_name": district_name,
        "dominant_cluster_label": dominant_cluster_label,
        "dominant_label": format_typology_label(dominant_profile.get("narrative_label", dominant_cluster_label)),
        "dominant_share": cluster_shares.get(dominant_cluster_label),
        "cluster_shares": cluster_shares,
        "sorted_shares": sorted_shares,
        "mixed_structure": bool(sorted_shares and (sorted_shares[0][1] - second_share) < 0.15),
    }


def build_typology_mix_compare_rows(first_payload: dict, second_payload: dict) -> list[html.Div]:
    cluster_labels = list(CLUSTER_PROFILE_LOOKUP.keys())
    sorted_labels = sorted(
        cluster_labels,
        key=lambda label: max(
            first_payload["cluster_shares"].get(label, 0.0),
            second_payload["cluster_shares"].get(label, 0.0),
        ),
        reverse=True,
    )
    rows = []
    for cluster_label in sorted_labels:
        profile = CLUSTER_PROFILE_LOOKUP.get(cluster_label, {})
        first_share = first_payload["cluster_shares"].get(cluster_label, 0.0)
        second_share = second_payload["cluster_shares"].get(cluster_label, 0.0)
        rows.append(
            html.Div(
                [
                    html.Div(
                        f"{first_share * 100:.0f}%",
                        className="typology-compare-side typology-compare-side-first",
                    ),
                    html.Div(
                        html.Div(
                            className="typology-compare-bar-fill typology-compare-bar-fill-first",
                            style={"width": f"{first_share * 100:.0f}%"},
                        ),
                        className="typology-compare-bar typology-compare-bar-first",
                    ),
                    html.Div(
                        format_typology_label(profile.get("narrative_label", cluster_label)),
                        className="typology-compare-pattern-label",
                    ),
                    html.Div(
                        html.Div(
                            className="typology-compare-bar-fill typology-compare-bar-fill-second",
                            style={"width": f"{second_share * 100:.0f}%"},
                        ),
                        className="typology-compare-bar typology-compare-bar-second",
                    ),
                    html.Div(
                        f"{second_share * 100:.0f}%",
                        className="typology-compare-side typology-compare-side-second",
                    ),
                ],
                className="typology-mix-row typology-compare-row",
            )
        )
    return rows


def build_typology_comparison_section(
    first_district: str,
    second_district: str,
    topic: str,
) -> html.Div:
    first_payload = get_typology_compare_payload(first_district)
    second_payload = get_typology_compare_payload(second_district)
    if not first_payload or not second_payload:
        return html.Div()

    same_dominant_pattern = (
        first_payload["dominant_cluster_label"] == second_payload["dominant_cluster_label"]
    )
    if same_dominant_pattern:
        main_summary = [
            "Both districts are mainly shaped by ",
            first_payload["dominant_label"],
            ", but their internal pattern mix still differs.",
        ]
    else:
        main_summary = [
            build_compare_district_name(first_district),
            f" is more strongly shaped by {first_payload['dominant_label']}, while ",
            build_compare_district_name(second_district),
            f" is more strongly shaped by {second_payload['dominant_label']}.",
        ]

    all_cluster_labels = set(first_payload["cluster_shares"]) | set(second_payload["cluster_shares"])
    largest_gap_label = None
    largest_gap_value = -1.0
    largest_gap_first = 0.0
    largest_gap_second = 0.0
    for cluster_label in all_cluster_labels:
        first_share = first_payload["cluster_shares"].get(cluster_label, 0.0)
        second_share = second_payload["cluster_shares"].get(cluster_label, 0.0)
        gap = abs(first_share - second_share)
        if gap > largest_gap_value:
            largest_gap_value = gap
            largest_gap_label = cluster_label
            largest_gap_first = first_share
            largest_gap_second = second_share

    largest_gap_name = format_typology_label(
        CLUSTER_PROFILE_LOOKUP.get(largest_gap_label, {}).get("narrative_label", largest_gap_label)
    )
    biggest_difference_text = [
        f"The largest gap appears in {largest_gap_name}: ",
        build_compare_district_name(first_district),
        f" has {largest_gap_first * 100:.0f}% of district grid cells in this pattern, while ",
        build_compare_district_name(second_district),
        f" has {largest_gap_second * 100:.0f}%.",
    ]

    mixed_notes = []
    if first_payload["mixed_structure"]:
        mixed_notes.append(
            [
                build_compare_district_name(first_district),
                " has a fairly mixed district structure, so its top pattern should be read as a broad summary.",
            ]
        )
    if second_payload["mixed_structure"]:
        mixed_notes.append(
            [
                build_compare_district_name(second_district),
                " has a fairly mixed district structure, so its top pattern should be read as a broad summary.",
            ]
        )
    if not mixed_notes:
        mixed_notes.append(
            "These pattern groups help compare broad spatial structure, but they do not explain why the districts differ."
        )

    return html.Div(
        [
            html.Details(
                [
                    html.Summary(
                        [
                            html.Div(
                                [
                                    html.Img(src=PANEL_ML_ICON, alt="", className="typology-summary-icon", draggable="false"),
                                    html.Div(
                                        [
                                            html.Div("District pattern comparison", className="typology-summary-title"),
                                            html.Div(
                                                "Open for a short comparison of broad district patterns.",
                                                className="typology-summary-subtitle",
                                            ),
                                        ],
                                        className="typology-summary-text",
                                    ),
                                ],
                                className="typology-summary-row",
                            ),
                            html.Div("Show", className="typology-summary-toggle"),
                        ],
                        className="typology-summary",
                    ),
                    html.Div(
                        [
                            html.Div("District pattern comparison", className="typology-card-eyebrow"),
                            html.H3("How the two districts differ structurally", className="typology-card-result-title"),
                            html.P(main_summary, className="typology-card-summary"),
                            html.P(biggest_difference_text, className="typology-card-bridge"),
                            html.Div(
                                [
                                    build_panel_heading_with_info(
                                        "District pattern mix",
                                        "This section compares how each district's grid cells are distributed across the 3 broad pattern groups.",
                                        "Pattern mix comparison",
                                    ),
                                    html.Div(
                                        [
                                            html.Div(first_district, className="typology-compare-district typology-compare-district-first"),
                                            html.Div("Pattern group", className="typology-compare-district typology-compare-district-center"),
                                            html.Div(second_district, className="typology-compare-district typology-compare-district-second"),
                                        ],
                                        className="typology-compare-header",
                                    ),
                                    html.Div(
                                        build_typology_mix_compare_rows(first_payload, second_payload),
                                        className="typology-mix-list",
                                    ),
                                    build_panel_heading_with_info(
                                        "How to read it",
                                        "This comparison highlights broad structural differences. It does not explain why those differences exist or how every street behaves.",
                                        "How to read it",
                                    ),
                                    html.P("This comparison works best as a broad spatial summary of the two districts rather than a final judgment about either one."),
                                    build_panel_heading_with_info(
                                        "Keep in mind",
                                        "These points explain the main limits behind the comparison.",
                                        "Keep in mind",
                                    ),
                                    html.Ul(
                                        [
                                            html.Li(
                                                "This comparison combines data layers from different reference years. Use it as a broad structural comparison, not as a single-time snapshot."
                                            ),
                                            html.Li(
                                                "The pattern groups are simplified summaries of similar grid cells, not official planning categories."
                                            ),
                                            *[html.Li(note) for note in mixed_notes],
                                        ],
                                        className="panel-meta-list",
                                    ),
                                ],
                                className="typology-card-body",
                            ),
                        ],
                        className="typology-card-content",
                    ),
                ],
                className="metric-card typology-card typology-card-collapsible typology-compare-card",
                open=False,
            )
        ],
        className="typology-compare-shell",
    )


def build_typology_section(district_name: str, topic: str) -> html.Div | None:
    district_typology = DISTRICT_TYPOLOGY_LOOKUP.get(district_name)
    if not district_typology:
        return None

    dominant_cluster_label = district_typology.get("dominant_cluster_label")
    if not dominant_cluster_label:
        return None

    dominant_profile = CLUSTER_PROFILE_LOOKUP.get(dominant_cluster_label)
    if not dominant_profile:
        return None

    cluster_shares = district_typology.get("cluster_shares", {})
    sorted_cluster_rows = sorted(
        cluster_shares.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    mix_rows = []
    for cluster_label, share in sorted_cluster_rows:
        profile = CLUSTER_PROFILE_LOOKUP.get(cluster_label, {})
        mix_rows.append(
            html.Div(
                [
                    html.Span(
                        format_typology_label(profile.get("narrative_label", cluster_label)),
                        className="typology-mix-label",
                    ),
                    html.Span(f"{share * 100:.0f}%", className="typology-mix-value"),
                ],
                className="typology-mix-row",
            )
        )

    dominant_share = cluster_shares.get(dominant_cluster_label)
    narrative_label = format_typology_label(dominant_profile.get("narrative_label", dominant_cluster_label))
    dominant_land_use = format_land_use_signal(dominant_profile.get("dominant_land_use_class"))
    evidence_points = [
        f"Main land-use context: {dominant_land_use}",
        f"Typical building form: {describe_height_band(dominant_profile.get('mean_height_mean'))} with an average height of {format_float(dominant_profile.get('mean_height_mean'), ' m', 1)}.",
        f"Typical public transport access: {describe_pt_band(dominant_profile.get('mean_pt_stop_count'))} with about {format_float(dominant_profile.get('mean_pt_stop_count'), '', 1)} stops per grid cell.",
    ]
    interpretation_text = (
        "This is the most common pattern across the district. It helps summarize the district as a whole, but it does not describe every street or block."
    )
    topic_bridge = build_typology_topic_bridge(topic)
    caveat_text = (
        "These pattern groups are not official planning categories. They are a simple summary of similar grid cells and work best as broad context."
    )

    return html.Details(
        [
            html.Summary(
                [
                    html.Div(
                        [
                            html.Img(src=PANEL_ML_ICON, alt="", className="typology-summary-icon", draggable="false"),
                            html.Div(
                                [
                                    html.Div("District pattern", className="typology-summary-title"),
                                    html.Div(
                                        "Open for a short district-wide pattern summary.",
                                        className="typology-summary-subtitle",
                                    ),
                                ],
                                className="typology-summary-text",
                            ),
                        ],
                        className="typology-summary-row",
                    ),
                    html.Div("Show", className="typology-summary-toggle"),
                ],
                className="typology-summary",
            ),
            html.Div(
                [
                    html.Div("District pattern summary", className="typology-card-eyebrow"),
                    html.H3(narrative_label, className="typology-card-result-title"),
                    html.P(format_typology_share(dominant_share), className="metric-label"),
                    html.P(
                        emphasize_numbers(
                            f"This is the most common pattern across the district's grid cells. {topic_bridge}"
                        ),
                        className="typology-card-summary",
                    ),
                    html.Div(
                        [
                            build_panel_heading_with_info(
                                "What shapes this pattern",
                                "This section shows the main land-use, building-height, and public-transport signals behind the district-wide pattern.",
                                "How this pattern was grouped",
                            ),
                            html.Ul([html.Li(point) for point in evidence_points], className="typology-list"),
                            build_panel_heading_with_info(
                                "District mix",
                                "Most districts contain more than one pattern. This shows how the district's grid cells are split across the pattern groups.",
                                "District mix",
                            ),
                            html.Div(mix_rows, className="typology-mix-list"),
                            build_panel_heading_with_info(
                                "How to read it",
                                "Use this as a broad district summary rather than a final judgment about every part of the district.",
                                "How to read it",
                            ),
                            html.P(emphasize_numbers(interpretation_text)),
                            build_panel_heading_with_info(
                                "What it uses",
                                "This summary is built from the grid layer and groups similar cells into broad pattern types.",
                                "What it uses",
                            ),
                            html.P(
                                emphasize_numbers(
                                    "This summary uses 250m grid cells with land use, building height, and stop-count information. Similar cells were grouped into 3 broad pattern types."
                                )
                            ),
                            build_panel_heading_with_info(
                                "Keep in mind",
                                "This shows broad district structure, but it cannot explain causes or the exact condition of every street or block.",
                                "Keep in mind",
                            ),
                            html.P(emphasize_numbers(caveat_text)),
                        ],
                        className="typology-card-body",
                    ),
                ],
                className="typology-card-content",
            ),
        ],
        className="metric-card typology-card typology-card-collapsible",
        open=False,
        key=f"typology-{district_name}-{topic}",
    )


def build_district_mismatch_section(district_name: str) -> html.Details | None:
    anomaly_record = DISTRICT_ANOMALY_LOOKUP.get(district_name)
    if not anomaly_record or not anomaly_record.get("anomaly_flag"):
        return None

    translated_features: list[str] = []
    for feature_name in anomaly_record.get("top_contributing_features", [])[:3]:
        translated = format_anomaly_feature_label(str(feature_name))
        if translated not in translated_features:
            translated_features.append(translated)

    standout_rows = []
    for index, feature_label in enumerate(translated_features, start=1):
        standout_rows.append(
            html.Div(
                [
                    html.Span(feature_label, className="typology-mix-label"),
                    html.Span(str(index), className="typology-mix-value"),
                ],
                className="typology-mix-row",
            )
        )

    return html.Details(
        [
            html.Summary(
                [
                    html.Div(
                        [
                            html.Img(src=PANEL_ML_ICON, alt="", className="typology-summary-icon", draggable="false"),
                            html.Div(
                                [
                                    html.Div("Why it stands out", className="typology-summary-title"),
                                    html.Div(
                                        "Open for a short district-wide comparison note.",
                                        className="typology-summary-subtitle",
                                    ),
                                ],
                                className="typology-summary-text",
                            ),
                        ],
                        className="typology-summary-row",
                    ),
                    html.Div("Show", className="typology-summary-toggle"),
                ],
                className="typology-summary",
            ),
            html.Div(
                [
                    html.Div("District comparison", className="typology-card-eyebrow"),
                    html.P(
                        emphasize_numbers(
                            "This district stands out more than most others in the current district-level comparison."
                        ),
                        className="typology-card-summary",
                    ),
                    html.Div(
                        [
                            build_panel_heading_with_info(
                                "Main factors",
                                "These are the main factors behind why this district stands out in the current comparison.",
                                "Main factors",
                            ),
                            html.Div(standout_rows, className="typology-mix-list"),
                            html.H4("How to read it"),
                            html.P(
                                emphasize_numbers(
                                    "This compares the district's overall profile with the other Madrid districts. It points to an unusual combination of characteristics, not just one extreme value."
                                )
                            ),
                            html.P(
                                emphasize_numbers(
                                    "The main factors may extend beyond the topic currently selected in the map."
                                )
                            ),
                            html.H4("Keep in mind"),
                            html.P(
                                emphasize_numbers(
                                    "This is an exploratory result based on indicators from different sources and years. It is not a diagnosis or a causal explanation."
                                )
                            ),
                        ],
                        className="typology-card-body",
                    ),
                ],
                className="typology-card-content",
            ),
        ],
        className="metric-card typology-card typology-card-collapsible",
        open=False,
        key=f"anomaly-{district_name}",
    )


PIPELINE_STAGES = [
    {
        "id": "source_intake",
        "title": "Source inputs",
        "subtitle": "Collect dataset",
        "status": "Complete",
        "icon_svg": PIPELINE_STAGE_SOURCE_SVG,
    },
    {
        "id": "cleaning",
        "title": "Cleaning & alignment",
        "subtitle": "Clean and standardise data",
        "status": "Complete",
        "icon_svg": PIPELINE_STAGE_CLEANING_SVG,
    },
    {
        "id": "topic_preparation",
        "title": "Feature preparation",
        "subtitle": "Build district and grid analysis tables",
        "status": "Active",
        "icon_svg": PIPELINE_STAGE_PREP_SVG,
    },
    {
        "id": "validation",
        "title": "Modeling & evaluation",
        "subtitle": "Generate typologies and validate outputs",
        "status": "Complete",
        "icon_svg": PIPELINE_STAGE_VALIDATE_SVG,
    },
    {
        "id": "representation",
        "title": "Dashboard translation",
        "subtitle": "Turn outputs into dashboard views",
        "status": "Complete",
        "icon_svg": PIPELINE_STAGE_REPRESENT_SVG,
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


def get_topic_source_details(topic: str | None) -> dict[str, str | list[tuple[str, str | None]]]:
    source_map = {
        "population": {
            "sources_text": "Madrid Population API + Madrid district boundaries",
            "reference_note": "Reference date is shown in the display view for the selected district.",
            "source_links": [
                ("Madrid Population API", "https://datos.madrid.es/dataset/300557-0-poblacion-distrito-barrio"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        },
        "housing": {
            "sources_text": "EMVS housing CSV + Madrid Population API + Madrid district boundaries",
            "reference_note": "Coverage reflects the 1 June 2015 to 30 April 2023 housing source window used in the dashboard.",
            "source_links": [
                ("EMVS housing CSV", None),
                ("Madrid Population API", "https://datos.madrid.es/dataset/300557-0-poblacion-distrito-barrio"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        },
        "green": {
            "sources_text": "Madrid district indicator panel + Madrid district boundaries",
            "reference_note": "Indicator year is shown in the display view for the selected district.",
            "source_links": [
                ("Madrid district indicator panel", "https://datos.madrid.es/dataset/300087-0-indicadores-distritos"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        },
        "economy": {
            "sources_text": "Madrid district indicator panel + Madrid district boundaries",
            "reference_note": "Indicator year is shown in the display view for the selected district.",
            "source_links": [
                ("Madrid district indicator panel", "https://datos.madrid.es/dataset/300087-0-indicadores-distritos"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        },
        "employment": {
            "sources_text": "Madrid district indicator panel + Madrid district boundaries",
            "reference_note": "Indicator year is shown in the display view for the selected district.",
            "source_links": [
                ("Madrid district indicator panel", "https://datos.madrid.es/dataset/300087-0-indicadores-distritos"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        },
        "vulnerability": {
            "sources_text": "Madrid district indicator panel + Madrid district boundaries",
            "reference_note": "Indicator year is shown in the display view for the selected district.",
            "source_links": [
                ("Madrid district indicator panel", "https://datos.madrid.es/dataset/300087-0-indicadores-distritos"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        },
        "mobility": {
            "sources_text": "Public transportation usage dataset (2018), Kaggle + Madrid district boundaries",
            "reference_note": "The mobility layer currently uses the 2018 source slice shown in display mode.",
            "source_links": [
                ("Public transportation usage dataset (2018), Kaggle", "https://www.kaggle.com/datasets/dataguapa/madrid-public-transportation-data-2018"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        },
        "land_use": {
            "sources_text": "Urban Atlas-based 250m grid + Madrid district boundaries",
            "reference_note": "Land-use layer reference year: 2018.",
            "source_links": [
                ("Urban Atlas", "https://land.copernicus.eu/en/products/urban-atlas"),
                ("District boundaries", None),
            ],
        },
        "height": {
            "sources_text": "Urban Atlas building-height layer + Madrid district boundaries",
            "reference_note": "The current source notes do not document a precise reference year for this layer.",
            "source_links": [
                ("Urban Atlas building height", "https://land.copernicus.eu/en/products/urban-atlas?tab=building_height"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        },
    }
    return source_map.get(
        topic or "",
        {
            "sources_text": "Select a topic to load its source context.",
            "reference_note": "Reference information appears once a topic is selected.",
            "source_links": [],
        },
    )


def get_pipeline_topic_context(topic: str | None) -> dict[str, str]:
    context_map = {
        "population": {
            "source_type": "Official district dataset",
            "inputs": "Madrid Population API and district boundaries",
            "outputs": "District population totals and density values",
        },
        "housing": {
            "source_type": "Official district dataset",
            "inputs": "EMVS housing data, population data, and district boundaries",
            "outputs": "District housing totals and housing per 1,000 residents",
        },
        "green": {
            "source_type": "Official district dataset",
            "inputs": "Madrid district indicator data and district boundaries",
            "outputs": "District green-space totals and green-space provision values",
        },
        "economy": {
            "source_type": "Official district dataset",
            "inputs": "Madrid district indicator data and district boundaries",
            "outputs": "District income indicators",
        },
        "employment": {
            "source_type": "Official district dataset",
            "inputs": "Madrid district indicator data and district boundaries",
            "outputs": "District unemployment indicators",
        },
        "vulnerability": {
            "source_type": "Official district dataset",
            "inputs": "Madrid district indicator data, IGUALA-linked vulnerability indicators, and district boundaries",
            "outputs": "District vulnerability indices",
        },
        "mobility": {
            "source_type": "Processed 250m spatial layer",
            "inputs": "Mobility source data, grid geometry, and district boundaries",
            "outputs": "Grid-level stop-count values and district-filtered mobility cells",
        },
        "land_use": {
            "source_type": "Processed 250m spatial layer",
            "inputs": "Urban Atlas land-use classes, grid geometry, and district boundaries",
            "outputs": "District-filtered land-use cells and land-use summaries",
        },
        "height": {
            "source_type": "Processed 250m spatial layer",
            "inputs": "Building-height layer, grid geometry, and district boundaries",
            "outputs": "Grid-level building-height values and district height summaries",
        },
    }
    return context_map.get(
        topic or "",
        {
            "source_type": "Topic not selected yet",
            "inputs": "Select a topic to load the relevant inputs",
            "outputs": "Select a topic to see the resulting dashboard values",
        },
    )


def get_pipeline_stage_artifact(stage_id: str, topic: str | None) -> dict[str, str] | None:
    is_grid_topic = topic in GRID_TOPICS
    if stage_id == "source_intake":
        return {
            "artifact_id": "collection_report",
            "title": "Collected source report",
            "filename": "collection_report.json",
            "description": "",
            "relative_path": "outputs/reports/collection_report.json",
            "preview_kind": "collection_report",
        }
    if stage_id == "topic_preparation":
        return {
            "artifact_id": "grid_features" if is_grid_topic else "district_features",
            "title": "Prepared grid feature table" if is_grid_topic else "Prepared district feature table",
            "filename": "grid_features.csv" if is_grid_topic else "district_features.csv",
            "description": "",
            "relative_path": "outputs/ml/grid_features.csv" if is_grid_topic else "outputs/ml/district_features.csv",
            "preview_kind": "grid_features" if is_grid_topic else "district_features",
        }
    if stage_id == "validation":
        if not topic:
            return None
        return {
            "artifact_id": "clustering_summary" if is_grid_topic else "anomaly_summary",
            "title": "Clustering model summary" if is_grid_topic else "District standout summary",
            "filename": "model_evaluation_summary.md",
            "description": "",
            "relative_path": "outputs/ml/model_evaluation_summary.md",
            "preview_kind": "clustering_summary" if is_grid_topic else "anomaly_summary",
        }
    return None


def build_pipeline_artifact_button(artifact: dict[str, str]) -> html.Button:
    copy_children = [
        html.Div(artifact["title"], className="pipeline-artifact-item-title"),
        html.Div(artifact["filename"], className="pipeline-artifact-item-file"),
    ]
    if artifact["description"]:
        copy_children.append(html.Div(artifact["description"], className="pipeline-artifact-item-text"))

    return html.Button(
        [
            html.Div(
                html.Img(src=PIPELINE_FILE_ICON, alt="", className="pipeline-artifact-item-icon", draggable="false"),
                className="pipeline-artifact-item-icon-wrap",
            ),
            html.Div(copy_children, className="pipeline-artifact-item-copy"),
            html.Div("Open", className="pipeline-artifact-item-toggle"),
        ],
        id={"type": "pipeline-artifact-button", "artifact": artifact["artifact_id"], "stage": artifact["preview_kind"]},
        n_clicks=0,
        className="pipeline-artifact-item",
    )


def get_pipeline_artifact_preview_columns(topic: str | None, preview_kind: str) -> list[str]:
    if preview_kind == "district_features":
        column_map = {
            "population": ["district_name", "reference_date", "population_total", "population_density_km2"],
            "housing": ["district_name", "housing_total", "housing_per_1000_residents", "has_housing_data"],
            "green": ["district_name", "green_area_ha", "green_area_per_10000", "has_green_data"],
            "economy": ["district_name", "income_per_person", "household_income", "has_economy_data"],
            "employment": ["district_name", "unemployment_total", "unemployment_rate", "has_employment_data"],
            "vulnerability": ["district_name", "vulnerability_index", "vulnerability_employment", "has_vulnerability_data"],
        }
        return column_map.get(topic or "", ["district_name", "reference_date"])
    if preview_kind == "grid_features":
        return [
            "district_name",
            "cell_id",
            "lu_2018_class_simplified",
            "height_mean",
            "pt_stop_count",
            "cluster_features_ready",
        ]
    return []


def extract_markdown_table(markdown_text: str, heading: str) -> pd.DataFrame:
    lines = markdown_text.splitlines()
    in_section = False
    table_lines: list[str] = []

    for line in lines:
        if line.strip() == heading:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.strip().startswith("|"):
            table_lines.append(line)
        elif in_section and table_lines:
            break

    if len(table_lines) < 2:
        return pd.DataFrame()

    cleaned_lines = [table_lines[0]]
    cleaned_lines.extend(table_lines[2:])
    csv_like = "\n".join(cleaned_lines)
    frame = pd.read_csv(StringIO(csv_like), sep="|", engine="python")
    frame = frame.drop(columns=[column for column in frame.columns if str(column).strip() == ""], errors="ignore")
    frame.columns = [str(column).strip() for column in frame.columns]
    frame = frame.loc[:, [column for column in frame.columns if not str(column).lower().startswith("unnamed:")]]
    for column in frame.columns:
        if frame[column].dtype == object:
            frame[column] = frame[column].astype(str).str.strip()
    return frame


def format_pipeline_preview_value(value) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return "—"
    if pd.isna(value):
        return "—"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def build_pipeline_preview_table(frame: pd.DataFrame) -> html.Div:
    if frame.empty:
        return html.Div("No preview rows available for this artifact.", className="pipeline-artifact-preview-empty")

    preview_frame = frame.copy()
    return html.Div(
        html.Table(
            [
                html.Thead(html.Tr([html.Th(column) for column in preview_frame.columns])),
                html.Tbody(
                    [
                        html.Tr([html.Td(format_pipeline_preview_value(row[column])) for column in preview_frame.columns])
                        for _, row in preview_frame.iterrows()
                    ]
                ),
            ],
            className="pipeline-artifact-table",
        ),
        className="pipeline-artifact-table-wrap",
    )


def build_pipeline_artifact_modal_content(
    artifact: dict[str, str],
    topic: str | None,
    district_name: str,
) -> tuple[str, str, str, html.Div]:
    artifact_path = PROJECT_ROOT / artifact["relative_path"]
    preview_kind = artifact["preview_kind"]
    modal_title = artifact["title"]
    modal_path = artifact["relative_path"]
    modal_description = artifact["description"]

    if preview_kind == "collection_report":
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        rows = pd.DataFrame(payload.get("sources", []))
        preview_columns = [
            column
            for column in ["source_name", "source_type", "file_format", "acquisition_mode", "row_count", "column_count"]
            if column in rows.columns
        ]
        preview_frame = rows.loc[:, preview_columns].head(8) if preview_columns else rows.head(8)
        summary = f"{payload.get('source_count', len(rows))} collected sources are recorded in the current report."
        body = html.Div(
            [
                html.P(summary, className="pipeline-artifact-modal-summary"),
                build_pipeline_preview_table(preview_frame),
            ]
        )
        return modal_title, modal_path, modal_description, body

    if preview_kind == "feature_specs":
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        spec_name = "grid_features" if topic in GRID_TOPICS else "district_features"
        selected_spec = next((item for item in payload if item.get("name") == spec_name), payload[0] if payload else {})
        columns = selected_spec.get("columns", [])
        preview_frame = pd.DataFrame(
            [
                {
                    "field": column.get("name"),
                    "description": column.get("description"),
                    "status": column.get("status"),
                    "used_for_modeling": bool(column.get("used_for_clustering") or column.get("used_for_anomaly_detection")),
                }
                for column in columns[:8]
            ]
        )
        body = html.Div(
            [
                html.P(selected_spec.get("purpose", "Prepared field specification."), className="pipeline-artifact-modal-summary"),
                html.P(selected_spec.get("grain", ""), className="pipeline-artifact-modal-subsummary"),
                build_pipeline_preview_table(preview_frame),
            ]
        )
        return modal_title, modal_path, modal_description, body

    if preview_kind in {"district_features", "grid_features"}:
        frame = pd.read_csv(artifact_path)
        if "district_name" in frame.columns:
            district_frame = frame.loc[frame["district_name"] == district_name].copy()
            if not district_frame.empty:
                frame = district_frame
        preview_columns = [column for column in get_pipeline_artifact_preview_columns(topic, preview_kind) if column in frame.columns]
        preview_frame = frame.loc[:, preview_columns].head(8) if preview_columns else frame.head(8)
        topic_label = get_pipeline_topic_label(topic)
        modal_description_map = {
            "district_features": f"This table shows a section of the prepared district-level {topic_label.lower()} dataset used in later pipeline steps.",
            "grid_features": f"This table shows a section of the prepared grid-level {topic_label.lower()} dataset used in later pipeline steps.",
            "cluster_mix": f"This table shows a section of the KMeans district pattern output for the {topic_label.lower()} topic.",
            "district_anomalies": f"This table shows a section of the district anomaly output used to compare {topic_label.lower()} signals across Madrid.",
        }
        body = html.Div(
            [build_pipeline_preview_table(preview_frame)]
        )
        return modal_title, modal_path, modal_description_map.get(preview_kind, modal_description), body

    if preview_kind in {"clustering_summary", "anomaly_summary"}:
        markdown_text = artifact_path.read_text(encoding="utf-8")
        heading = "## Clustering" if preview_kind == "clustering_summary" else "## Anomaly Detection"
        preview_frame = extract_markdown_table(markdown_text, heading).head(12)
        topic_label = get_pipeline_topic_label(topic)
        modal_description_map = {
            "clustering_summary": f"This table shows a section of the KMeans evaluation summary used for the {topic_label.lower()} topic.",
            "anomaly_summary": f"This table shows a section of the Isolation Forest summary used to compare {topic_label.lower()} signals across districts and identify which districts stand out.",
        }
        body = html.Div([build_pipeline_preview_table(preview_frame)])
        return modal_title, modal_path, modal_description_map.get(preview_kind, modal_description), body

    body = html.Div("Preview not available for this artifact.", className="pipeline-artifact-preview-empty")
    return modal_title, modal_path, modal_description, body


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
                html.Img(
                    src=build_pipeline_stage_icon(stage["icon_svg"], is_active),
                    className="pipeline-stage-icon",
                    alt="",
                ),
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
                    html.P("Choose a topic to see how source data becomes prepared tables, model outputs, and final dashboard views."),
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
                "Select 1 district to inspect how a topic moves from source inputs through preparation and evaluation into the dashboard.",
                className="pipeline-empty-text",
            ),
        ],
        className="pipeline-empty-state",
    )


def build_pipeline_stage_panel(stage_id: str, topic: str | None, district_name: str) -> html.Div:
    stage = get_pipeline_stage(stage_id)
    topic_label = get_pipeline_topic_label(topic)
    topic_context = get_pipeline_topic_context(topic)
    source_details = get_topic_source_details(topic)
    artifact = get_pipeline_stage_artifact(stage_id, topic)
    stage_icon_src = build_pipeline_stage_icon(stage["icon_svg"], is_active=True)
    stage_text_map = {
        "source_intake": {
            "stage_summary": f"This stage gathers the raw inputs needed for the {topic_label.lower()} view in {district_name}.",
            "action": "The workflow identifies the relevant source files or APIs and keeps their origin visible before later processing begins.",
            "input": topic_context["inputs"],
            "output": f"Raw topic inputs with visible source context. Source type: {topic_context['source_type']}.",
            "why": "This stage makes it clear where the selected topic starts and whether it comes from district indicators or processed spatial data.",
            "caveat": "A single topic can still combine sources from different years or source systems.",
        },
        "cleaning": {
            "stage_summary": f"This stage makes the {topic_label.lower()} inputs compatible with one another.",
            "action": "Names, formats, units, and spatial references are standardized so the topic can be prepared consistently.",
            "input": "Raw source tables, files, and spatial references",
            "output": "Cleaned topic inputs ready for table building",
            "why": "This stage reduces mismatches between districts, values, and geometries before the dashboard reads them.",
            "caveat": "Cleaning improves comparability, but it does not remove the limits of the original source data.",
        },
        "topic_preparation": {
            "stage_summary": f"This stage builds the analysis tables used for the {topic_label.lower()} topic in {district_name}.",
            "action": "Cleaned inputs are translated into district-level features or 250m grid features, depending on how the topic is represented in the dashboard.",
            "input": "Cleaned topic inputs",
            "output": topic_context["outputs"],
            "why": "This is where raw data becomes the structured evidence that the selected topic actually displays.",
            "caveat": "District topics and grid topics diverge here, so not every topic is prepared in the same way.",
        },
        "validation": {
            "stage_summary": f"This stage checks how the prepared {topic_label.lower()} data contributes to modeling outputs and quality checks.",
            "action": "Where relevant, the workflow generates typologies or anomaly signals and keeps evaluation results visible alongside those outputs.",
            "input": "Prepared district and grid analysis tables",
            "output": "Model outputs, warnings, and evaluation summaries",
            "why": "This stage adds analytical interpretation while keeping uncertainty and caveats visible.",
            "caveat": "These outputs are comparative and exploratory, not final diagnoses or planning decisions.",
        },
        "representation": {
            "stage_summary": f"This stage turns the prepared {topic_label.lower()} outputs into the dashboard view for {district_name}.",
            "action": "The workflow maps prepared values into topic controls, hover behavior, and sidebar content so the data can be read as a coherent interface.",
            "input": "Prepared topic tables and any relevant model outputs",
            "output": "Readable dashboard views for the selected district and topic",
            "why": "This is where technical outputs become usable planning evidence in the interface.",
            "caveat": "The dashboard summarizes the workflow; it does not expose every internal transformation in full detail.",
        },
    }
    stage_text = stage_text_map[stage["id"]]
    input_children: list = [html.P(stage_text["input"])]
    if stage["id"] == "source_intake":
        input_children = [
            html.P(source_details["sources_text"], className="panel-meta-subtext"),
            build_panel_meta_links(source_details["source_links"]),
        ]
        if artifact is not None:
            input_children.extend(
                [
                    html.Div("Example artifact", className="pipeline-artifact-label"),
                    build_pipeline_artifact_button(artifact),
                ]
            )

    output_children: list = [html.P(stage_text["output"])]
    if stage["id"] in {"cleaning", "topic_preparation", "validation"} and artifact is not None:
        output_children.extend(
            [
                html.Div("Example artifact", className="pipeline-artifact-label"),
                build_pipeline_artifact_button(artifact),
            ]
        )

    meta_items = [
        build_panel_meta_item(
            PANEL_META_ALERT_ICON,
            "Keep in mind",
            html.P(stage_text["caveat"], className="panel-meta-text"),
            tone="warning",
        )
    ]

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        html.Img(src=stage_icon_src, className="pipeline-panel-stage-icon", alt=""),
                        className="pipeline-panel-stage-icon-wrap",
                    ),
                    html.H2(stage["title"], className="panel-title"),
                ],
                className="pipeline-panel-stage-header",
            ),
            html.P("Pipeline stage details", className="panel-subtitle"),
            html.Div(
                [
                    html.H4("Stage"),
                    html.P(stage_text["stage_summary"]),
                    html.H4("What happens here?"),
                    html.P(stage_text["action"]),
                    html.H4("Input"),
                    html.Div(input_children),
                    html.H4("Output"),
                    html.Div(output_children),
                    html.H4("Why this stage matters"),
                    html.P(stage_text["why"]),
                ],
                className="panel-body",
            ),
            html.Div(
                meta_items,
                className="panel-meta-grid pipeline-panel-meta-grid",
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
                html.Div(id="shared-topic-compare", className="shared-topic-compare"),
                html.Div(id="district-panel", className="right-panel-body"),
            ],
            id="right-panel-region",
            className="app-right-panel",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div(id="pipeline-artifact-modal-title", className="pipeline-artifact-modal-title"),
                                        html.Div(id="pipeline-artifact-modal-path", className="pipeline-artifact-modal-path"),
                                    ]
                                ),
                                html.Button(
                                    "Close",
                                    id="pipeline-artifact-modal-close",
                                    n_clicks=0,
                                    className="pipeline-artifact-modal-close",
                                ),
                            ],
                            className="pipeline-artifact-modal-header",
                        ),
                        html.Div(id="pipeline-artifact-modal-description", className="pipeline-artifact-modal-description"),
                        html.Div(id="pipeline-artifact-modal-body", className="pipeline-artifact-modal-body"),
                    ],
                    className="pipeline-artifact-modal-card",
                )
            ],
            id="pipeline-artifact-modal",
            className="pipeline-artifact-modal",
            style={"display": "none"},
        ),
        dcc.Store(id="selected-district-store", data=[]),
        dcc.Store(id="selected-topic-store", data=None),
        dcc.Store(id="metric-value-store", data=None),
        dcc.Store(id="metric-memory-store", data={}),
        dcc.Store(id="metric-open-store", data=False),
        dcc.Store(id="land-use-filter-value-store", data=[]),
        dcc.Store(id="land-use-filter-open-store", data=False),
        dcc.Store(id="sidebar-collapsed-store", data=False),
        dcc.Store(id="sidebar-manual-state-store", data=None),
        dcc.Store(id="view-mode-store", data=DEFAULT_VIEW_MODE),
        dcc.Store(id="display-selection-mode-store", data=DEFAULT_DISPLAY_SELECTION_MODE),
        dcc.Store(id="pipeline-stage-store", data=DEFAULT_PIPELINE_STAGE),
        dcc.Store(id="pipeline-artifact-store", data=None),
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
    Input("view-mode-store", "data"),
    State("pipeline-stage-store", "data"),
    prevent_initial_call=True,
)
def sync_pipeline_stage(
    stage_clicks: list[int],
    view_mode: str | None,
    current_stage: str | None,
):
    triggered = callback_context.triggered_id
    if triggered == "view-mode-store" and view_mode == "pipeline":
        return DEFAULT_PIPELINE_STAGE
    if (
        isinstance(triggered, dict)
        and triggered.get("type") == "pipeline-stage-button"
        and any(stage_clicks or [])
    ):
        return triggered.get("stage", current_stage or DEFAULT_PIPELINE_STAGE)
    return current_stage or DEFAULT_PIPELINE_STAGE


@app.callback(
    Output("selected-topic-store", "data"),
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

    is_disabled = not has_selected_district
    return (
        topic,
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
)
def update_map(
    metric: str | None,
    topic: str | None,
    selected_districts: list[str] | None,
    mobility_threshold: int,
    land_use_filter: list[str] | None,
):
    normalized_selection = canonicalise_selected_districts(selected_districts)
    if not normalized_selection:
        return build_grid_base_figure()

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
    Output("shared-topic-compare", "children"),
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
    grid_typology_topics = {"land_use", "height", "mobility"}

    if selected_count == 0:
        return (
            [],
            "Madrid",
            html.Div(),
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
                panel_position=1,
            )
            if topic and metric
            else build_topic_prompt_panel(district_name, panel_position=1)
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
            html.Div(),
            "app-right-panel app-right-panel-single",
            controls_style,
        )

    first_district = normalized_selection[0]
    second_district = normalized_selection[1]
    show_shared_typology_compare = bool(topic and metric and topic in grid_typology_topics)
    first_panel = (
        build_info_panel(
            first_district,
            metric,
            topic,
            mobility_threshold or DEFAULT_MOBILITY_THRESHOLD,
            land_use_filter,
            show_typology_section=not show_shared_typology_compare,
            show_anomaly_section=False,
            panel_position=1,
        )
        if topic and metric
        else build_topic_prompt_panel(first_district, is_comparison=True, panel_position=1)
    )
    second_panel = (
        build_info_panel(
            second_district,
            metric,
            topic,
            mobility_threshold or DEFAULT_MOBILITY_THRESHOLD,
            land_use_filter,
            show_typology_section=not show_shared_typology_compare,
            show_anomaly_section=False,
            panel_position=2,
        )
        if topic and metric
        else build_topic_prompt_panel(second_district, is_comparison=True, panel_position=2)
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
        (
            build_typology_comparison_section(first_district, second_district, topic)
            if show_shared_typology_compare
            else html.Div()
        ),
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
    Output("metric-open-store", "data", allow_duplicate=True),
    Input("metric-filter-toggle", "n_clicks"),
    Input({"type": "metric-option", "value": ALL}, "n_clicks"),
    State("metric-open-store", "data"),
    prevent_initial_call=True,
)
def sync_metric_open_state(
    toggle_clicks: int,
    option_clicks: list[int],
    is_open: bool,
):
    triggered = callback_context.triggered_id

    if triggered == "metric-filter-toggle":
        return not bool(is_open)

    if (
        isinstance(triggered, dict)
        and triggered.get("type") == "metric-option"
        and any(option_clicks or [])
    ):
        return False

    return bool(is_open)


@app.callback(
    Output("metric-value-store", "data"),
    Output("metric-memory-store", "data"),
    Input("selected-topic-store", "data"),
    Input({"type": "metric-option", "value": ALL}, "n_clicks"),
    State("metric-memory-store", "data"),
    prevent_initial_call=True,
)
def sync_metric_state(
    topic: str | None,
    option_clicks: list[int],
    metric_memory: dict[str, str] | None,
):
    triggered = callback_context.triggered_id
    current_memory = dict(metric_memory or {})

    if triggered == "selected-topic-store":
        if not topic:
            return None, current_memory

        saved_metric = current_memory.get(topic)
        valid_metric_values = {option["value"] for option in build_metric_options(topic)}
        if saved_metric in valid_metric_values:
            return saved_metric, current_memory
        return build_metric_options(topic)[0]["value"], current_memory

    if (
        isinstance(triggered, dict)
        and triggered.get("type") == "metric-option"
        and topic
        and any(option_clicks or [])
    ):
        selected_metric = triggered.get("value", build_metric_options(topic)[0]["value"])
        current_memory[topic] = selected_metric
        return selected_metric, current_memory

    return no_update, current_memory


@app.callback(
    Output("pipeline-artifact-store", "data"),
    Input({"type": "pipeline-artifact-button", "artifact": ALL, "stage": ALL}, "n_clicks"),
    Input("pipeline-artifact-modal-close", "n_clicks"),
    Input("selected-topic-store", "data"),
    Input("selected-district-store", "data"),
    Input("pipeline-stage-store", "data"),
    Input("view-mode-store", "data"),
    State("pipeline-artifact-store", "data"),
    prevent_initial_call=True,
)
def sync_pipeline_artifact_modal(
    artifact_clicks: list[int],
    close_clicks: int,
    topic: str | None,
    selected_districts: list[str] | None,
    pipeline_stage: str | None,
    view_mode: str | None,
    current_artifact: dict[str, str] | None,
):
    triggered = callback_context.triggered_id

    if triggered in (
        "pipeline-artifact-modal-close",
        "selected-topic-store",
        "selected-district-store",
        "pipeline-stage-store",
    ):
        return None

    if triggered == "view-mode-store":
        return None

    if (
        isinstance(triggered, dict)
        and triggered.get("type") == "pipeline-artifact-button"
        and any(artifact_clicks or [])
    ):
        artifact = get_pipeline_stage_artifact(pipeline_stage, topic)
        if artifact is None:
            return None
        return {
            **artifact,
            "topic": topic,
            "district_name": (canonicalise_selected_districts(selected_districts) or [DEFAULT_DISTRICT])[0],
        }

    return current_artifact


@app.callback(
    Output("pipeline-artifact-modal", "className"),
    Output("pipeline-artifact-modal", "style"),
    Output("pipeline-artifact-modal-title", "children"),
    Output("pipeline-artifact-modal-path", "children"),
    Output("pipeline-artifact-modal-description", "children"),
    Output("pipeline-artifact-modal-body", "children"),
    Input("pipeline-artifact-store", "data"),
    State("selected-topic-store", "data"),
    State("selected-district-store", "data"),
)
def render_pipeline_artifact_modal(
    artifact_state: dict[str, str] | None,
    topic: str | None,
    selected_districts: list[str] | None,
):
    if not artifact_state:
        return "pipeline-artifact-modal", {"display": "none"}, "", "", "", []

    district_name = (canonicalise_selected_districts(selected_districts) or [artifact_state.get("district_name", DEFAULT_DISTRICT)])[0]
    artifact = {
        key: value
        for key, value in artifact_state.items()
        if key in {"artifact_id", "title", "filename", "description", "relative_path", "preview_kind"}
    }
    if not artifact:
        return "pipeline-artifact-modal", {"display": "none"}, "", "", "", []

    modal_title, modal_path, modal_description, modal_body = build_pipeline_artifact_modal_content(artifact, topic, district_name)
    return (
        "pipeline-artifact-modal pipeline-artifact-modal-open",
        {"display": "flex"},
        modal_title,
        modal_path,
        modal_description,
        modal_body,
    )


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
    Input("display-selection-mode-store", "data"),
    State("land-use-filter-value-store", "data"),
    State("land-use-filter-open-store", "data"),
)
def sync_land_use_filter(
    toggle_clicks: int,
    option_clicks: list[int],
    action_clicks: list[int],
    topic: str | None,
    district_names: list[str] | None,
    display_selection_mode: str | None,
    current_value: list[str] | None,
    is_open: bool,
):
    if not canonicalise_selected_districts(district_names):
        return [], False

    available_values = get_land_use_class_values(district_names)
    normalized_values = normalise_land_use_filter_values(current_value, district_names)
    triggered = callback_context.triggered_id

    if triggered in (
        "selected-topic-store",
        "selected-district-store",
        "display-selection-mode-store",
    ):
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
