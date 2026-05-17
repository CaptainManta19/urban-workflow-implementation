from frontend.dashboard_logic import *

def get_pipeline_stage(stage_id: str | None) -> dict:
    for stage in PIPELINE_STAGES:
        if stage["id"] == stage_id:
            return stage
    return next(stage for stage in PIPELINE_STAGES if stage["id"] == DEFAULT_PIPELINE_STAGE)


def get_pipeline_topic_label(topic: str | None) -> str:
    label_map = {
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
            "title": "Source inventory report",
            "filename": "source_collection_report.json",
            "description": "This preview lists the sources currently used for the selected topic, together with basic provenance details.",
            "relative_path": "outputs/collection/source_collection_report.json",
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
        body = html.Div([build_pipeline_preview_table(preview_frame)])
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
            "clustering_summary": (
                f"This preview shows part of the clustering review for the selected {topic_label.lower()} topic. "
                "KMeans is a method that groups cases into clusters based on how similar their indicator values are. "
                "Here, it helps summarize recurring grid patterns so broader district structure becomes easier to compare. "
                "These clusters are exploratory pattern types, not official planning categories."
            ),
            "anomaly_summary": (
                f"This preview shows part of the standout review for the selected {topic_label.lower()} topic. "
                "Isolation Forest is a method that highlights cases whose indicator combinations look more unusual than the rest of the dataset. "
                "Here, it helps identify districts that stand out in comparative terms across the selected indicators. "
                "These results are exploratory signals, not diagnoses or explanations."
            ),
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
                    html.P("Pipeline details unlock once a topic is selected.", className="metric-label"),
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
            "stage_summary": f"This stage shows the source material used to build the selected {topic_label.lower()} view in {district_name} before any cleaning, aggregation, or modeling takes place.",
            "action": "The workflow brings together the raw inputs for the selected topic, along with basic source context such as origin, format, and coverage.",
            "input": topic_context["inputs"],
            "output": f"Raw topic inputs with visible source context. Source type: {topic_context['source_type']}.",
            "why": "What you can read later in the map or sidebar depends on what enters the workflow here. Different topics start from different kinds of source material, so they do not carry the same level of detail, consistency, or update cycle.",
            "caveat": "These inputs are the starting material, not yet comparable dashboard metrics. Differences in source year, update cycle, and coverage can still shape what appears in later stages.",
        },
        "cleaning": {
            "stage_summary": f"This stage prepares the selected {topic_label.lower()} inputs for comparison by aligning names, formats, units, and spatial references.",
            "action": "The workflow cleans and aligns the incoming source material so that the selected topic can be read on a more consistent basis across districts or grid cells.",
            "input": "Raw source tables, files, and spatial references.",
            "output": "Topic inputs that have been cleaned and aligned for later preparation steps.",
            "why": "District and grid comparisons depend on shared naming, units, and spatial framing. This stage reduces friction between sources so later indicators can be read together more reliably.",
            "caveat": "Alignment improves comparability, but it does not remove differences in source year, coverage, or original method.",
        },
        "topic_preparation": {
            "stage_summary": f"This stage turns the cleaned inputs into the district-level and grid-level indicators used in the selected {topic_label.lower()} topic.",
            "action": "The workflow translates the cleaned source material into structured indicators, using district summaries for some topics and 250m grid values for others.",
            "input": "Cleaned topic inputs.",
            "output": f"{topic_context['outputs']}.",
            "why": "This is the point where cleaned source material becomes the indicators the dashboard can compare, map, and describe.",
            "caveat": "These indicators are constructed representations of the topic. They make district or grid comparison possible, but they do not capture every aspect of urban conditions.",
        },
        "validation": {
            "stage_summary": "This stage uses the prepared indicators to generate exploratory pattern outputs and check how those outputs behave across districts or grid cells.",
            "action": "Where relevant, the workflow groups similar cases or flags unusual ones, then reviews the resulting outputs so they can be inspected with their limits still visible.",
            "input": "Prepared district and grid analysis tables.",
            "output": "Exploratory pattern outputs, standout signals, and model review summaries.",
            "why": "This stage adds comparative interpretation. It helps surface broad similarities, differences, and standout cases that would be harder to see from individual indicators alone.",
            "caveat": "These outputs are exploratory pattern readings, not diagnoses or predictions. They depend on the chosen indicators, preparation steps, and model settings.",
        },
        "representation": {
            "stage_summary": f"This stage turns the prepared {topic_label.lower()} outputs into the map, hover, and sidebar views used to read {district_name}.",
            "action": "The workflow maps prepared values and model results into interface elements such as topic controls, hover panels, cards, chips, and comparison views.",
            "input": "Prepared topic tables and any relevant model outputs.",
            "output": "Map and sidebar views that organize the selected topic into a readable district interface.",
            "why": "This stage shapes how the selected topic is actually read. Titles, metric cards, hover panels, chips, and comparison layouts all influence what stands out and how districts are interpreted.",
            "caveat": "The dashboard is a designed summary of the workflow, not a neutral mirror of the raw data. What is emphasized, grouped, or simplified here affects how the topic is understood.",
        },
    }
    stage_text = stage_text_map[stage["id"]]
    input_children: list = [html.P(stage_text["input"])]
    if stage["id"] == "source_intake":
        input_children = [
            html.P(source_details["sources_text"], className="panel-meta-subtext"),
            build_panel_meta_links(source_details["source_links"]),
        ]

    output_children: list = [html.P(stage_text["output"])]
    if stage["id"] in {"source_intake", "cleaning", "topic_preparation", "validation"} and artifact is not None:
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
                    html.P(stage_text["stage_summary"]),
                    html.Details(
                        [
                            html.Summary("What happens here?", className="pipeline-panel-summary"),
                            html.Div(html.P(stage_text["action"]), className="pipeline-panel-section-body"),
                        ],
                        className="pipeline-panel-section",
                    ),
                    html.Details(
                        [
                            html.Summary("Input", className="pipeline-panel-summary"),
                            html.Div(input_children, className="pipeline-panel-section-body"),
                        ],
                        className="pipeline-panel-section",
                    ),
                    html.Details(
                        [
                            html.Summary("Output", className="pipeline-panel-summary"),
                            html.Div(output_children, className="pipeline-panel-section-body"),
                        ],
                        className="pipeline-panel-section",
                    ),
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
