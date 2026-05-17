from dash import dcc, html

from frontend.dashboard_logic import *


def build_app_layout() -> html.Div:
    return html.Div(
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
                        id="district-selection-region",
                        className="app-sidebar-inner onboarding-target-region",
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
                                        id="mode-selection-region",
                                        className="mode-selection-region onboarding-target-region",
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
                                                                title="Greenspaces",
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
                                                ],
                                                id="topic-selection-region",
                                                className="topic-selection-region onboarding-target-region",
                                            ),
                                            html.Div(
                                                [
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
                                                    html.Div(id="map-topic-info", className="map-topic-info"),
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
                        id="map-toolbar",
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
                        id="map-view-region",
                        className="app-center-body onboarding-target-region",
                    )
                ],
                className="app-center",
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
                                                    html.Label("Metric", id="metric-filter-title", className="field-label"),
                                                    build_toolbar_info_bubble(
                                                        "A metric is a quantified measure used to describe, analyze, and compare urban conditions.",
                                                        "What is a metric?",
                                                    ),
                                                ],
                                                className="inline-label-row metric-filter-title-row",
                                            ),
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
                                        ],
                                        id="metric-filter-wrap",
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
                                            html.Div(
                                                [
                                                    html.Label("Metric", id="land-use-filter-title", className="field-label"),
                                                    build_toolbar_info_bubble(
                                                        "A metric is a quantified measure used to describe, analyze, and compare urban conditions.",
                                                        "What is a metric?",
                                                    ),
                                                ],
                                                className="inline-label-row metric-filter-title-row",
                                            ),
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
                        id="right-panel-onboarding-region",
                        className="onboarding-target-region",
                    ),
                ],
                id="right-panel-region",
                className="app-right-panel",
            ),
            html.Div(
                id="onboarding-backdrop",
                className="onboarding-backdrop",
                style={"display": "none"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(id="onboarding-eyebrow", className="onboarding-eyebrow"),
                            html.H3(id="onboarding-title", className="onboarding-title"),
                            html.P(id="onboarding-body", className="onboarding-body"),
                            html.Div(id="onboarding-progress", className="onboarding-progress"),
                            html.Div(
                                [
                                    html.Button(
                                        "Skip",
                                        id="onboarding-skip-button",
                                        n_clicks=0,
                                        className="onboarding-button onboarding-button-ghost",
                                    ),
                                    html.Button(
                                        "Back",
                                        id="onboarding-back-button",
                                        n_clicks=0,
                                        className="onboarding-button onboarding-button-secondary",
                                    ),
                                    html.Button(
                                        "Next",
                                        id="onboarding-next-button",
                                        n_clicks=0,
                                        className="onboarding-button onboarding-button-primary",
                                    ),
                                ],
                                className="onboarding-actions",
                            ),
                        ],
                        id="onboarding-card",
                        className="onboarding-card onboarding-card-district",
                    )
                ],
                id="onboarding-card-layer",
                className="onboarding-card-layer",
                style={"display": "none"},
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
            dcc.Store(id="land-use-filter-value-store", data=None),
            dcc.Store(id="land-use-filter-open-store", data=False),
            dcc.Store(id="sidebar-collapsed-store", data=False),
            dcc.Store(id="sidebar-manual-state-store", data=None),
            dcc.Store(id="view-mode-store", data=DEFAULT_VIEW_MODE),
            dcc.Store(id="display-selection-mode-store", data=DEFAULT_DISPLAY_SELECTION_MODE),
            dcc.Store(id="pipeline-stage-store", data=DEFAULT_PIPELINE_STAGE),
            dcc.Store(id="pipeline-artifact-store", data=None),
            dcc.Store(id="onboarding-step-store", data=0),
            dcc.Store(id="onboarding-complete-store", data=False),
        ],
        id="app-shell",
        className="app-shell",
    )
    
