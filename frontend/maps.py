from frontend.dashboard_logic import *

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
    filtered = district_frame
    normalized_selected_classes = normalise_land_use_filter_values(selected_classes, district_names)
    available_classes = get_land_use_class_values(district_names)
    if len(normalized_selected_classes) != len(available_classes):
        filtered = district_frame[
            district_frame["lu_2018_class_simplified"].isin(normalized_selected_classes)
        ]

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
        trace.name = format_land_use_signal(trace.name)
        if getattr(trace, "legendgroup", None):
            trace.legendgroup = format_land_use_signal(trace.legendgroup)
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
