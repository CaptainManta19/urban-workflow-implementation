from dash import Dash

from frontend.dashboard_logic import *
from frontend.maps import (
    add_selected_district_outlines,
    build_choropleth,
    build_grid_base_figure,
    build_height_map,
    build_land_use_map,
    build_mobility_map,
)
from frontend.panels import (
    build_district_sidebar,
    build_info_panel,
    build_topic_prompt_panel,
)
from frontend.pipeline_view import (
    build_pipeline_center,
    build_pipeline_empty_state,
    build_pipeline_prompt_panel,
    build_pipeline_stage_panel,
)


def register_callbacks(app: Dash) -> None:
    @app.callback(
        Output("view-mode-store", "data"),
        Output("display-selection-mode-store", "data"),
        Output("view-mode-display-button", "className"),
        Output("view-mode-pipeline-button", "className"),
        Output("display-submode-toggle", "style"),
        Output("display-submode-inspect-button", "className"),
        Output("display-submode-compare-button", "className"),
        Output("district-field-hint", "children"),
        Output("map-toolbar", "className"),
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
    
        toolbar_class = "map-toolbar map-toolbar-pipeline" if view_mode == "pipeline" else "map-toolbar map-toolbar-display"
    
        return (
            view_mode,
            display_mode,
            display_button_class,
            pipeline_button_class,
            submode_style,
            inspect_button_class,
            compare_button_class,
            field_hint,
            toolbar_class,
        )
    
    
    @app.callback(
        Output("onboarding-step-store", "data"),
        Output("onboarding-complete-store", "data"),
        Input("onboarding-skip-button", "n_clicks"),
        Input("onboarding-back-button", "n_clicks"),
        Input("onboarding-next-button", "n_clicks"),
        Input("selected-district-store", "data"),
        Input("selected-topic-store", "data"),
        State("onboarding-step-store", "data"),
        State("onboarding-complete-store", "data"),
    )
    def sync_onboarding_state(
        skip_clicks: int,
        back_clicks: int,
        next_clicks: int,
        selected_districts: list[str] | None,
        selected_topic: str | None,
        current_step: int | None,
        is_complete: bool | None,
    ):
        step = current_step or 0
        complete = bool(is_complete)
        triggered = callback_context.triggered_id
        has_selected_district = bool(canonicalise_selected_districts(selected_districts))
        has_selected_topic = bool(selected_topic)
    
        if triggered == "onboarding-skip-button":
            return step, True
        if triggered == "onboarding-back-button":
            return max(step - 1, 0), False
        if triggered == "onboarding-next-button":
            if complete:
                return step, complete
            if step == 0 and not has_selected_district:
                return step, False
            if step == 1 and not has_selected_topic:
                return step, False
            if step >= ONBOARDING_STEP_COUNT - 1:
                return step, True
            return step + 1, False
        if complete:
            return step, complete
        if step == 0 and has_selected_district:
            return 1, False
        if step == 1 and has_selected_topic:
            return 2, False
        return step, False
    
    
    @app.callback(
        Output("onboarding-backdrop", "className"),
        Output("onboarding-backdrop", "style"),
        Output("onboarding-card-layer", "className"),
        Output("onboarding-card-layer", "style"),
        Output("onboarding-card", "className"),
        Output("onboarding-eyebrow", "children"),
        Output("onboarding-title", "children"),
        Output("onboarding-body", "children"),
        Output("onboarding-progress", "children"),
        Output("onboarding-back-button", "disabled"),
        Output("onboarding-next-button", "children"),
        Output("onboarding-next-button", "disabled"),
        Output("district-selection-region", "className"),
        Output("topic-selection-region", "className"),
        Output("mode-selection-region", "className"),
        Input("onboarding-step-store", "data"),
        Input("onboarding-complete-store", "data"),
        Input("selected-district-store", "data"),
        Input("selected-topic-store", "data"),
    )
    def render_onboarding(
        current_step: int | None,
        is_complete: bool | None,
        selected_districts: list[str] | None,
        selected_topic: str | None,
    ):
        default_region_classes = {
            "district": "app-sidebar-inner onboarding-target-region",
            "topic": "topic-selection-region onboarding-target-region",
            "mode": "mode-selection-region onboarding-target-region",
        }
        if is_complete:
            return (
                "onboarding-backdrop",
                {"display": "none"},
                "onboarding-card-layer",
                {"display": "none"},
                "onboarding-card onboarding-card-district",
                "",
                "",
                "",
                "",
                True,
                "Next",
                True,
                default_region_classes["district"],
                default_region_classes["topic"],
                default_region_classes["mode"],
            )
    
        step = current_step or 0
        step_config = get_onboarding_step(step)
        has_selected_district = bool(canonicalise_selected_districts(selected_districts))
        has_selected_topic = bool(selected_topic)
        next_disabled = (step == 0 and not has_selected_district) or (step == 1 and not has_selected_topic)
        active_target = step_config["target"]
    
        region_classes = default_region_classes.copy()
        region_classes[active_target] = f"{region_classes[active_target]} onboarding-target-active"
    
        return (
            "onboarding-backdrop onboarding-backdrop-open",
            {"display": "block"},
            "onboarding-card-layer onboarding-card-layer-open",
            {"display": "block"},
            f"onboarding-card onboarding-card-{active_target}",
            step_config["eyebrow"],
            step_config["title"],
            step_config["body"],
            f"{min(step + 1, ONBOARDING_STEP_COUNT)} / {ONBOARDING_STEP_COUNT}",
            step == 0,
            step_config["next_label"] if next_disabled else ("Finish" if step >= ONBOARDING_STEP_COUNT - 1 else "Next"),
            next_disabled,
            region_classes["district"],
            region_classes["topic"],
            region_classes["mode"],
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
                return (
                    build_district_sidebar(panel_children, 1),
                    district_name,
                    html.Div(),
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
            return (
                build_district_sidebar(panel_children, 1),
                district_name,
                html.Div(),
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
                is_comparison=True,
                comparison_district=second_district,
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
                is_comparison=True,
                comparison_district=first_district,
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
            f"{first_district} / {second_district}",
            build_map_info_bubble(comparison_message),
            html.Div(),
            (
                html.Div(
                    [
                        build_shared_compare_section(
                            first_district,
                            second_district,
                            metric,
                            topic,
                            mobility_threshold or DEFAULT_MOBILITY_THRESHOLD,
                            land_use_filter,
                        ),
                        (
                            build_typology_comparison_section(first_district, second_district, topic)
                            if show_shared_typology_compare
                            else html.Div()
                        ),
                    ]
                )
                if topic and metric
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
        Output("metric-filter-wrap", "style"),
        Output("land-use-filter-wrap", "style"),
        Output("land-use-filter-title", "children"),
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
            return {"display": "block"}, {"display": "none"}, "Metric", "Select a district", [], {"display": "none"}
    
        selected_values = normalise_land_use_filter_values(selected_value if isinstance(selected_value, list) else None, district_names)
        label = get_land_use_filter_label(selected_values, district_names)
        menu_children = build_land_use_filter_menu(district_names, selected_values)
        if topic == "land_use":
            return (
                {"display": "none"},
                {"display": "block"},
                "Metric",
                label,
                menu_children,
                {"display": "block"} if is_open else {"display": "none"},
            )
        return {"display": "block"}, {"display": "none"}, "Metric", label, menu_children, {"display": "none"}
    
    
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
