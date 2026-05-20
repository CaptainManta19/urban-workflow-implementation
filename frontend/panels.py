from frontend.dashboard_logic import *

def get_local_summary_chips(
    district_name: str,
    district_row: pd.Series,
    topic: str,
    metric: str,
    mobility_threshold: int = DEFAULT_MOBILITY_THRESHOLD,
    land_use_filter: list[str] | None = None,
    comparison_district: str | None = None,
) -> list[str]:
    if topic == "land_use":
        district_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(district_name, GRID_FRAME.head(0).copy()).copy()
        if district_cells.empty:
            return ["No data"]
        selected_classes = normalise_land_use_filter_values(land_use_filter, district_name)
        available_classes = get_land_use_class_values(district_name)
        if len(selected_classes) != len(available_classes):
            return []
        dominant_class = district_cells["lu_2018_class_simplified"].value_counts().idxmax()
        return [format_land_use_chip(dominant_class)]

    if topic == "height":
        district_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(district_name, GRID_FRAME.head(0).copy()).copy()
        height_cells = district_cells[district_cells["height_mean"].notna()].copy()
        if height_cells.empty:
            return ["No data"]
        height_band = describe_height_band(height_cells["height_mean"].mean())
        band_chip = {
            "lower-rise fabric": "Lower-rise",
            "mid-rise fabric": "Mid-rise",
            "taller urban fabric": "Taller fabric",
        }.get(height_band, "Height pattern")
        return [band_chip]

    if topic == "mobility":
        district_cells = MOBILITY_GRID_FRAME.loc[MOBILITY_GRID_FRAME["district_name"] == district_name].copy()
        if district_cells.empty:
            return ["No data"]
        if comparison_district:
            share_above_threshold = (district_cells["pt_stop_count"] >= mobility_threshold).mean()
            comparison_cells = MOBILITY_GRID_FRAME.loc[MOBILITY_GRID_FRAME["district_name"] == comparison_district].copy()
            if comparison_cells.empty:
                return ["Partial coverage"]
            comparison_share = (comparison_cells["pt_stop_count"] >= mobility_threshold).mean()
            if abs(share_above_threshold - comparison_share) < 0.1:
                return ["Similar access spread"]
            return ["Wider access spread" if share_above_threshold > comparison_share else "Narrower access spread"]
        return []

    if topic == "housing":
        if not bool(district_row["has_housing_data"]):
            return ["No data"]
        if metric == "housing_total":
            stock_chip = describe_relative_band(
                DISTRICT_FRAME.loc[DISTRICT_FRAME["has_housing_data"], "housing_total"],
                district_row["housing_total"],
                "Lower housing stock",
                "Mid housing stock",
                "Higher housing stock",
            )
            return [stock_chip]
        provision_chip = describe_relative_band(
            DISTRICT_FRAME.loc[DISTRICT_FRAME["has_housing_data"], "housing_per_1000_residents"],
            district_row["housing_per_1000_residents"],
            "Lower housing provision",
            "Mid housing provision",
            "Higher housing provision",
        )
        return [provision_chip]

    if topic == "green":
        if not bool(district_row["has_green_data"]):
            return ["No data"]
        if metric == "green_area_ha":
            green_chip = describe_relative_band(
                DISTRICT_FRAME.loc[DISTRICT_FRAME["has_green_data"], "green_area_ha"],
                district_row["green_area_ha"],
                "Lower green space",
                "Mid green space",
                "Higher green space",
            )
            return [green_chip]
        access_chip = describe_relative_band(
            DISTRICT_FRAME.loc[DISTRICT_FRAME["has_green_data"], "green_area_per_10000"],
            district_row["green_area_per_10000"],
            "Lower green access",
            "Mid green access",
            "Higher green access",
        )
        return [access_chip]

    if topic == "economy":
        if not bool(district_row["has_economy_data"]):
            return ["No data"]
        income_chip = describe_relative_band(
            DISTRICT_FRAME.loc[DISTRICT_FRAME["has_economy_data"], metric],
            district_row[metric],
            "Lower income",
            "Mid income",
            "Higher income",
        )
        return [income_chip]

    if topic == "employment":
        if not bool(district_row["has_employment_data"]):
            return ["No data"]
        if metric == "unemployment_total":
            unemployment_chip = describe_relative_band(
                DISTRICT_FRAME.loc[DISTRICT_FRAME["has_employment_data"], "unemployment_total"],
                district_row["unemployment_total"],
                "Lower unemployment total",
                "Mid unemployment total",
                "Higher unemployment total",
            )
            return [unemployment_chip]
        pressure_chip = describe_relative_band(
            DISTRICT_FRAME.loc[DISTRICT_FRAME["has_employment_data"], "unemployment_rate"],
            district_row["unemployment_rate"],
            "Lower pressure",
            "Mid pressure",
            "Higher pressure",
        )
        return [pressure_chip]

    if topic == "vulnerability":
        if not bool(district_row["has_vulnerability_data"]):
            return ["No data"]
        if metric == "vulnerability_index":
            vulnerability_chip = describe_relative_band(
                DISTRICT_FRAME.loc[DISTRICT_FRAME["has_vulnerability_data"], "vulnerability_index"],
                district_row["vulnerability_index"],
                "Lower vulnerability",
                "Mid vulnerability",
                "Higher vulnerability",
            )
            return [vulnerability_chip]
        vulnerability_chip = describe_relative_band(
            DISTRICT_FRAME.loc[DISTRICT_FRAME["has_vulnerability_data"], "vulnerability_employment"],
            district_row["vulnerability_employment"],
            "Lower employment vulnerability",
            "Mid employment vulnerability",
            "Higher employment vulnerability",
        )
        return [vulnerability_chip]

    if not bool(district_row["has_population_data"]):
        return ["No data"]
    if metric == "population_total":
        resident_chip = describe_relative_band(
            DISTRICT_FRAME.loc[DISTRICT_FRAME["has_population_data"], "population_total"],
            district_row["population_total"],
            "Smaller population",
            "Mid-sized population",
            "Larger population",
        )
        return [resident_chip]
    density_chip = describe_relative_band(
        DISTRICT_FRAME.loc[DISTRICT_FRAME["has_population_data"], "population_density_km2"],
        district_row["population_density_km2"],
        "Lower density",
        "Mid density",
        "Higher density",
    )
    return [density_chip]


def get_shared_compare_summary_chips(
    first_district: str,
    second_district: str,
    topic: str,
    metric: str,
    mobility_threshold: int = DEFAULT_MOBILITY_THRESHOLD,
    land_use_filter: list[str] | None = None,
) -> list[str]:
    if topic == "land_use":
        selected_classes = normalise_land_use_filter_values(land_use_filter, [first_district, second_district])
        available_classes = get_land_use_class_values([first_district, second_district])
        if len(selected_classes) != len(available_classes):
            return []
        first_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(first_district, GRID_FRAME.head(0).copy()).copy()
        second_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(second_district, GRID_FRAME.head(0).copy()).copy()
        if first_cells.empty or second_cells.empty:
            return ["Partial coverage"]
        first_dominant = first_cells["lu_2018_class_simplified"].value_counts().idxmax()
        second_dominant = second_cells["lu_2018_class_simplified"].value_counts().idxmax()
        return ["Similar land use" if first_dominant == second_dominant else "Different land use"]
    if topic == "height":
        first_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(first_district, GRID_FRAME.head(0).copy()).copy()
        second_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(second_district, GRID_FRAME.head(0).copy()).copy()
        first_values = first_cells[first_cells[metric].notna()][metric]
        second_values = second_cells[second_cells[metric].notna()][metric] if metric in second_cells.columns else pd.Series(dtype=float)
        if first_values.empty or second_values.empty:
            return ["Partial coverage"]
        return ["Height contrast" if abs(first_values.mean() - second_values.mean()) >= 5 else "Similar height"]
    if topic == "mobility":
        first_cells = MOBILITY_GRID_FRAME.loc[MOBILITY_GRID_FRAME["district_name"] == first_district].copy()
        second_cells = MOBILITY_GRID_FRAME.loc[MOBILITY_GRID_FRAME["district_name"] == second_district].copy()
        if first_cells.empty or second_cells.empty:
            return ["Partial coverage"]
        gap = abs((first_cells["pt_stop_count"] >= mobility_threshold).mean() - (second_cells["pt_stop_count"] >= mobility_threshold).mean())
        return ["Access gap" if gap >= 0.15 else "Similar access"]
    if topic == "housing":
        has_flag = "has_housing_data"
        series_name = "housing_total" if metric == "housing_total" else "housing_per_1000_residents"
        first_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == first_district].iloc[0]
        second_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == second_district].iloc[0]
        if not bool(first_row[has_flag]) or not bool(second_row[has_flag]):
            return ["Partial coverage"]
        series = DISTRICT_FRAME.loc[DISTRICT_FRAME[has_flag], series_name]
        return ["Similar housing level" if values_share_relative_band(series, first_row[series_name], second_row[series_name]) else "Different housing level"]
    if topic == "green":
        has_flag = "has_green_data"
        series_name = "green_area_ha" if metric == "green_area_ha" else "green_area_per_10000"
        first_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == first_district].iloc[0]
        second_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == second_district].iloc[0]
        if not bool(first_row[has_flag]) or not bool(second_row[has_flag]):
            return ["Partial coverage"]
        series = DISTRICT_FRAME.loc[DISTRICT_FRAME[has_flag], series_name]
        return ["Similar green level" if values_share_relative_band(series, first_row[series_name], second_row[series_name]) else "Different green level"]
    if topic == "economy":
        first_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == first_district].iloc[0]
        second_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == second_district].iloc[0]
        if not bool(first_row["has_economy_data"]) or not bool(second_row["has_economy_data"]):
            return ["Partial coverage"]
        series = DISTRICT_FRAME.loc[DISTRICT_FRAME["has_economy_data"], metric]
        return ["Similar income" if values_share_relative_band(series, first_row[metric], second_row[metric]) else "Income gap"]
    if topic == "employment":
        first_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == first_district].iloc[0]
        second_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == second_district].iloc[0]
        if not bool(first_row["has_employment_data"]) or not bool(second_row["has_employment_data"]):
            return ["Partial coverage"]
        series_name = "unemployment_total" if metric == "unemployment_total" else "unemployment_rate"
        series = DISTRICT_FRAME.loc[DISTRICT_FRAME["has_employment_data"], series_name]
        if values_share_relative_band(series, first_row[series_name], second_row[series_name]):
            return ["Similar unemployment" if metric == "unemployment_total" else "Similar pressure"]
        return ["Different unemployment level" if metric == "unemployment_total" else "Different pressure"]
    if topic == "vulnerability":
        first_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == first_district].iloc[0]
        second_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == second_district].iloc[0]
        if not bool(first_row["has_vulnerability_data"]) or not bool(second_row["has_vulnerability_data"]):
            return ["Partial coverage"]
        series_name = "vulnerability_index" if metric == "vulnerability_index" else "vulnerability_employment"
        series = DISTRICT_FRAME.loc[DISTRICT_FRAME["has_vulnerability_data"], series_name]
        if values_share_relative_band(series, first_row[series_name], second_row[series_name]):
            return ["Similar vulnerability" if metric == "vulnerability_index" else "Similar employment vulnerability"]
        return ["Different vulnerability level" if metric == "vulnerability_index" else "Different employment vulnerability"]
    first_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == first_district].iloc[0]
    second_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == second_district].iloc[0]
    if not bool(first_row["has_population_data"]) or not bool(second_row["has_population_data"]):
        return ["Partial coverage"]
    series_name = "population_total" if metric == "population_total" else "population_density_km2"
    series = DISTRICT_FRAME.loc[DISTRICT_FRAME["has_population_data"], series_name]
    if values_share_relative_band(series, first_row[series_name], second_row[series_name]):
        return ["Similar population" if metric == "population_total" else "Similar density"]
    return ["Population gap" if metric == "population_total" else "Density gap"]


def build_compare_local_interpretation(
    district_name: str,
    district_row: pd.Series,
    topic: str,
    metric: str,
    mobility_threshold: int = DEFAULT_MOBILITY_THRESHOLD,
    land_use_filter: list[str] | None = None,
) -> str:
    if topic == "land_use":
        district_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(district_name, GRID_FRAME.head(0).copy()).copy()
        if district_cells.empty:
            return "This district does not yet have matching land-use grid data in the current dashboard slice."
        selected_classes = normalise_land_use_filter_values(land_use_filter, district_name)
        available_classes = get_land_use_class_values(district_name)
        if len(selected_classes) != len(available_classes):
            return "The current filter shows only part of the district's land-use pattern."
        dominant_class = district_cells["lu_2018_class_simplified"].value_counts().idxmax()
        green_like_classes = {
            "Green urban areas",
            "Herbaceous vegetation associations (natural grassland, moors...)",
            "Pastures",
            "Arable land (annual crops)",
        }
        green_share = district_cells["lu_2018_class_simplified"].isin(green_like_classes).mean() * 100
        green_band = "a limited green/open-land share" if green_share < 25 else "a mixed green/open-land share" if green_share < 45 else "a stronger green/open-land share"
        return f"The visible grid is led by {format_land_use_signal(dominant_class).lower()}, with {green_band}."

    if topic == "height":
        district_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(district_name, GRID_FRAME.head(0).copy()).copy()
        height_cells = district_cells[district_cells["height_mean"].notna()].copy()
        if height_cells.empty:
            return "This district does not yet have matching building-height grid data in the current dashboard slice."
        mean_height = height_cells["height_mean"].mean()
        height_band = describe_height_band(mean_height)
        return f"Overall built form reads as {height_band} across the district."

    if topic == "mobility":
        district_cells = MOBILITY_GRID_FRAME.loc[MOBILITY_GRID_FRAME["district_name"] == district_name].copy()
        if district_cells.empty:
            return "This district does not yet have matching mobility grid data in the current dashboard slice."
        share_above_threshold = (district_cells["pt_stop_count"] >= mobility_threshold).mean()
        if share_above_threshold < 0.25:
            spread_text = "bus-stop access is limited to a smaller share of grid cells"
        elif share_above_threshold < 0.55:
            spread_text = "bus-stop access is present across a moderate share of grid cells"
        else:
            spread_text = "bus-stop access is spread across much of the district grid"
        return f"At the current threshold, {spread_text}."

    if topic == "housing":
        if not bool(district_row["has_housing_data"]):
            return "This district does not yet have matching housing data in the current dashboard slice."
        if metric == "housing_total":
            provision_band = describe_relative_band(
                DISTRICT_FRAME.loc[DISTRICT_FRAME["has_housing_data"], "housing_total"],
                district_row["housing_total"],
                "a relatively small public-housing footprint",
                "a moderate public-housing footprint",
                "a relatively strong public-housing footprint",
            )
            return f"Public housing has {provision_band} here."
        rate_band = describe_relative_band(
            DISTRICT_FRAME.loc[DISTRICT_FRAME["has_housing_data"], "housing_per_1000_residents"],
            district_row["housing_per_1000_residents"],
            "relatively low",
            "mid-level",
            "relatively high",
        )
        return f"Public-housing provision per resident is {rate_band} here."

    if topic == "green":
        if not bool(district_row["has_green_data"]):
            return "This district does not yet have matching green-space data in the current dashboard slice."
        if metric == "green_area_ha":
            green_band = describe_relative_band(
                DISTRICT_FRAME.loc[DISTRICT_FRAME["has_green_data"], "green_area_ha"],
                district_row["green_area_ha"],
                "a relatively small green-space footprint",
                "a moderate green-space footprint",
                "a relatively large green-space footprint",
            )
            return f"The district carries {green_band}."
        per_resident_band = describe_relative_band(
            DISTRICT_FRAME.loc[DISTRICT_FRAME["has_green_data"], "green_area_per_10000"],
            district_row["green_area_per_10000"],
            "relatively low",
            "mid-level",
            "relatively high",
        )
        return f"Green provision per resident is {per_resident_band} here."

    if topic == "economy":
        if not bool(district_row["has_economy_data"]):
            return "This district does not yet have matching income data in the current dashboard slice."
        if metric == "income_per_person":
            income_band = describe_relative_band(
                DISTRICT_FRAME.loc[DISTRICT_FRAME["has_economy_data"], "income_per_person"],
                district_row["income_per_person"],
                "the lower end",
                "the middle",
                "the higher end",
            )
            return f"This district sits toward {income_band} of Madrid's income distribution."
        household_band = describe_relative_band(
            DISTRICT_FRAME.loc[DISTRICT_FRAME["has_economy_data"], "household_income"],
            district_row["household_income"],
            "the lower end",
            "the middle",
            "the higher end",
        )
        return f"Household income here sits toward {household_band} of the citywide distribution."

    if topic == "employment":
        if not bool(district_row["has_employment_data"]):
            return "This district does not yet have matching employment data in the current dashboard slice."
        if metric == "unemployment_total":
            total_band = describe_relative_band(
                DISTRICT_FRAME.loc[DISTRICT_FRAME["has_employment_data"], "unemployment_total"],
                district_row["unemployment_total"],
                "a smaller absolute unemployment load",
                "a moderate absolute unemployment load",
                "a larger absolute unemployment load",
            )
            return f"In absolute terms, the district carries {total_band}."
        rate_band = describe_relative_band(
            DISTRICT_FRAME.loc[DISTRICT_FRAME["has_employment_data"], "unemployment_rate"],
            district_row["unemployment_rate"],
            "relatively low",
            "mid-level",
            "relatively high",
        )
        return f"Unemployment pressure is {rate_band} here."

    if topic == "vulnerability":
        if not bool(district_row["has_vulnerability_data"]):
            return "This district does not yet have matching vulnerability data in the current dashboard slice."
        if metric == "vulnerability_index":
            vulnerability_band = describe_relative_band(
                DISTRICT_FRAME.loc[DISTRICT_FRAME["has_vulnerability_data"], "vulnerability_index"],
                district_row["vulnerability_index"],
                "relatively low",
                "mid-level",
                "relatively high",
            )
            return f"Overall vulnerability is {vulnerability_band} here."
        employment_vulnerability_band = describe_relative_band(
            DISTRICT_FRAME.loc[DISTRICT_FRAME["has_vulnerability_data"], "vulnerability_employment"],
            district_row["vulnerability_employment"],
            "relatively low",
            "mid-level",
            "relatively high",
        )
        return f"Employment-related vulnerability is {employment_vulnerability_band} here."

    if not bool(district_row["has_population_data"]):
        return "This district does not yet have matching population data in the current dashboard slice."
    if metric == "population_total":
        resident_band = describe_relative_band(
            DISTRICT_FRAME.loc[DISTRICT_FRAME["has_population_data"], "population_total"],
            district_row["population_total"],
            "a smaller resident base",
            "a mid-sized resident base",
            "a larger resident base",
        )
        density_band = describe_relative_band(
            DISTRICT_FRAME.loc[DISTRICT_FRAME["has_population_data"], "population_density_km2"],
            district_row["population_density_km2"],
            "a more open district form",
            "a moderately compact district form",
            "a compact district form",
        )
        return f"This district combines {resident_band} with {density_band}."
    density_band = describe_relative_band(
        DISTRICT_FRAME.loc[DISTRICT_FRAME["has_population_data"], "population_density_km2"],
        district_row["population_density_km2"],
        "a more open district form",
        "a moderately compact district form",
        "a compact district form",
    )
    resident_band = describe_relative_band(
        DISTRICT_FRAME.loc[DISTRICT_FRAME["has_population_data"], "population_total"],
        district_row["population_total"],
        "a smaller resident base",
        "a mid-sized resident base",
        "a larger resident base",
    )
    return f"Density reads as {density_band}, alongside {resident_band}."


def build_info_panel(
    district_name: str,
    metric: str,
    topic: str,
    mobility_threshold: int = DEFAULT_MOBILITY_THRESHOLD,
    land_use_filter: list[str] | None = None,
    show_typology_section: bool = True,
    show_anomaly_section: bool = True,
    panel_position: int = 1,
    is_comparison: bool = False,
    comparison_district: str | None = None,
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
    title_icon = build_title_topic_icon(topic, get_compare_color(panel_position))
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
        metric_value = f"{len(selected_classes)} classes selected" if filtered_view else format_land_use_signal(dominant_class)
        key_finding = (
            (
                f"{district_name} currently shows {len(visible_cells):,} visible cells across "
                f"{len(selected_classes)} selected land-use classes."
            )
            if filtered_view
            else (
                f"{district_name} is dominated by {format_land_use_signal(dominant_class).lower()} in the research-derived land-use grid, "
                f"with {green_like_share:.0f}% of cells falling into green or open-land classes."
            )
        )
        meaning_text = (
            "Land use gives the district's physical backdrop: where the urban fabric is more built, more mixed, or more open."
        )
        production_text = (
            "Read the grid as a broad spatial profile. The value at the top summarizes the dominant class or active filter, while the map shows how that pattern is distributed."
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
            "Building height helps describe built form, street enclosure, and the overall intensity of the district's fabric."
        )
        production_text = "Read this as a district-wide height pattern built from grid estimates. Isolated tall buildings matter less than the overall profile."
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
                "This is a simple access signal: it shows where bus stops are more present across the district grid."
            )
            production_text = (
                "Read the threshold count as a spread measure. More qualifying cells means access is distributed more widely across the district."
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
                "Public housing helps show where municipal housing support has a stronger or weaker district footprint."
            )
        )
        production_text = (
            "This topic does not yet have a matching district value in the current dashboard data."
            if not has_data
            else (
                "Read the total and per-resident measure together. One shows stock, while the other shows how strongly that stock is represented against district population."
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
        topic_label = "Greenspaces"
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
            else "Green provision helps show the amount of shared open space the district carries and how much pressure that space may face."
        )
        production_text = (
            "This topic does not yet have a matching district value in the current dashboard data."
            if not has_data
            else "Read total green area together with the per-resident measure. A district can have a large green footprint overall but less green space per resident."
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
            else "Income helps place the district within Madrid's social geography and gives a first read on relative advantage and purchasing power."
        )
        production_text = (
            "This topic does not yet have a matching district value in the current dashboard data."
            if not has_data
            else "Read this as an overall district income profile. It shows the district's position, not the internal spread between households or neighborhoods."
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
            else "Employment indicators help show where economic pressure on residents is lighter or heavier across the district."
        )
        production_text = (
            "This topic does not yet have a matching district value in the current dashboard data."
            if not has_data
            else "Read the rate and the total together. The rate shows pressure, while the total shows how many residents are affected in absolute terms."
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
            else "These indices help flag where social and economic pressures may be stacking up at district scale."
        )
        production_text = (
            "This topic does not yet have a matching district value in the current dashboard data."
            if not has_data
            else "Read higher values as stronger relative pressure within the IGUALA system. The indicator is comparative, not causal."
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
                "Population and density together show district scale and urban concentration, which shape service demand and everyday intensity."
            )
        )
        production_text = (
            "This topic does not yet have a matching district value in the current dashboard data."
            if not has_data
            else (
                "Read total population with density at the same time. A large district is not always a dense one, and a dense district is not always the largest."
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
                title_icon,
                html.H2(topic_label, className="panel-title"),
            ],
            className="panel-title-row",
        ),
        html.P(district_name, className="panel-subtitle"),
        html.Div(
            [
                html.H3(metric_value, className="metric-value"),
                metric_label_node or html.P(metric_label, className="metric-label"),
            ],
            className="metric-card",
        ),
    ]
    summary_chip_labels = get_local_summary_chips(
        district_name,
        district_row,
        topic,
        metric,
        mobility_threshold,
        land_use_filter,
        comparison_district if is_comparison else None,
    )
    summary_chip_row = build_summary_chip_row(
        summary_chip_labels[:2] if is_comparison else summary_chip_labels
    )
    if summary_chip_row is not None:
        content_children.append(summary_chip_row)
    is_grid_topic = topic in {"land_use", "height", "mobility"}
    if is_comparison:
        panel_body_children = [
            html.H4("What stands out here"),
            html.P(
                emphasize_numbers(
                    build_compare_local_interpretation(
                        district_name,
                        district_row,
                        topic,
                        metric,
                        mobility_threshold,
                        land_use_filter,
                    )
                )
            ),
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
    if is_comparison:
        pass
    elif is_grid_topic:
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
                    html.H2("District selected", className="panel-title"),
                ],
                className="panel-title-row",
            ),
            html.P(district_name, className="panel-subtitle"),
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
def get_shared_compare_topic_context(
    topic: str,
    metric: str,
    mobility_threshold: int = DEFAULT_MOBILITY_THRESHOLD,
) -> dict[str, str | list[str] | list[tuple[str, str | None]]]:
    if topic == "land_use":
        return {
            "topic_label": "Land use / green context",
            "why_text": "Land use gives the broad physical setting of each district and helps explain why other differences appear on the map.",
            "how_text": "Compare the dominant land-use pattern, the share of open or green classes, and how evenly those classes spread across each district.",
            "caveats": [
                "This is a simplified land-use layer for spatial context, not parcel-level zoning.",
                "The current filter changes which land-use classes remain visible in both districts.",
            ],
            "sources_text": "Urban Atlas-based 250m grid + Madrid district boundaries",
            "reference_date": "Land-use layer: 2018",
            "source_links": [
                ("Urban Atlas", "https://land.copernicus.eu/en/products/urban-atlas"),
                ("District boundaries", None),
            ],
        }
    if topic == "height":
        return {
            "topic_label": "Building height",
            "why_text": "Building height helps describe density, enclosure, and the overall intensity of urban form.",
            "how_text": "Look first at the overall height profile, then at whether one district stays consistently low-rise or shifts into taller pockets.",
            "caveats": [
                "Height values are generalized grid estimates, not exact building measurements.",
                "Broad district averages can hide local height variation inside each district.",
            ],
            "sources_text": "Urban Atlas building-height layer + Madrid district boundaries",
            "reference_date": "Reference year not explicitly documented in current source notes",
            "source_links": [
                ("Urban Atlas building height", "https://land.copernicus.eu/en/products/urban-atlas?tab=building_height"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        }
    if topic == "mobility":
        return {
            "topic_label": "Mobility",
            "why_text": "This shows how evenly basic bus-stop access is distributed across each district.",
            "how_text": f"Each 250m cell is checked against the current threshold of {mobility_threshold} bus stops. Compare how many cells meet that threshold and whether they cluster or spread widely.",
            "caveats": [
                "This shows stop concentration by grid cell, not full public transport quality.",
                "Research-derived grid topics may still have partial coverage.",
            ],
            "sources_text": "Public transportation usage dataset (2018), Kaggle + Madrid district boundaries",
            "reference_date": "2018",
            "source_links": [
                ("Public transportation usage dataset (2018), Kaggle", "https://www.kaggle.com/datasets/dataguapa/madrid-public-transportation-data-2018"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        }
    if topic == "housing":
        return {
            "topic_label": "Housing",
            "why_text": "Public-housing provision shows where municipal housing support has a stronger footprint.",
            "how_text": "Read the total and per-resident measure together. One shows public-housing stock, the other shows how strongly that stock is represented against district population.",
            "caveats": [
                "EMVS values describe public housing allocation, not total housing supply or affordability.",
                "Districts without matching topic data appear in grey.",
            ],
            "sources_text": "EMVS housing CSV + Madrid Population API + Madrid district boundaries",
            "reference_date": "1 June 2015 to 30 April 2023",
            "source_links": [
                ("EMVS housing CSV", None),
                ("Madrid Population API", "https://datos.madrid.es/dataset/300557-0-poblacion-distrito-barrio"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        }
    if topic == "green":
        return {
            "topic_label": "Greenspaces",
            "why_text": "Green provision matters for amenity, cooling, and the amount of shared open space available at district scale.",
            "how_text": "Read total green area with the per-resident measure. Large districts can score high in one and weaker in the other.",
            "caveats": [
                "This is district-level green-space provision, not direct park accessibility from a specific address.",
                "Districts without matching topic data appear in grey.",
            ],
            "sources_text": "Madrid district indicator panel + Madrid district boundaries",
            "reference_date": "Indicator year varies by current dashboard data",
            "source_links": [
                ("Madrid district indicator panel", "https://datos.madrid.es/dataset/300087-0-indicadores-distritos"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        }
    if topic == "economy":
        metric_scope = "income per person" if metric == "income_per_person" else "household income"
        return {
            "topic_label": "Economy",
            "why_text": f"{metric_scope.capitalize()} helps place each district within Madrid's wider social and economic geography.",
            "how_text": "Compare which district sits higher in the income distribution and whether that gap appears in both income measures.",
            "caveats": [
                "These are panel indicators and should be read as district context, not household-level distributions.",
                "Districts without matching topic data appear in grey.",
            ],
            "sources_text": "Madrid district indicator panel + Madrid district boundaries",
            "reference_date": "Indicator year varies by current dashboard data",
            "source_links": [
                ("Madrid district indicator panel", "https://datos.madrid.es/dataset/300087-0-indicadores-distritos"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        }
    if topic == "employment":
        return {
            "topic_label": "Employment",
            "why_text": "Employment pressure helps frame household strain, economic stability, and where recovery may be more fragile.",
            "how_text": "Read the unemployment rate and the unemployment total together. One shows pressure, the other shows how many residents are affected in absolute terms.",
            "caveats": [
                "These values reflect registered unemployment indicators, not the full labor market picture.",
                "Districts without matching topic data appear in grey.",
            ],
            "sources_text": "Madrid district indicator panel + Madrid district boundaries",
            "reference_date": "Indicator year varies by current dashboard data",
            "source_links": [
                ("Madrid district indicator panel", "https://datos.madrid.es/dataset/300087-0-indicadores-distritos"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        }
    if topic == "vulnerability":
        return {
            "topic_label": "Vulnerability",
            "why_text": "These indices help identify where social and economic pressures may be layering together.",
            "how_text": "Read higher values as stronger relative pressure within the municipal index. Compare the overall index and the employment-specific dimension separately.",
            "caveats": [
                "These are composite municipal panel indices and should be read as comparative context rather than direct causal explanations.",
                "Districts without matching topic data appear in grey.",
            ],
            "sources_text": "Madrid district indicator panel + Madrid district boundaries",
            "reference_date": "Indicator year varies by current dashboard data",
            "source_links": [
                ("Madrid district indicator panel", "https://datos.madrid.es/dataset/300087-0-indicadores-distritos"),
                ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
            ],
        }
    return {
        "topic_label": "Population & density",
        "why_text": "Population and density help separate district scale from compactness, which matters for service demand and urban intensity.",
        "how_text": "Compare total population with density at the same time. A large district is not always a dense one, and a dense district is not always the largest.",
        "caveats": [
            "Density is derived from administrative district area, not built-up area.",
            "Districts without matching topic data appear in grey.",
        ],
        "sources_text": "Madrid Population API + Madrid district boundaries",
        "reference_date": "Reference dates follow the current dashboard population layer",
        "source_links": [
            ("Madrid Population API", "https://datos.madrid.es/dataset/300557-0-poblacion-distrito-barrio"),
            ("District boundaries", "https://datos.madrid.es/dataset/900012-0-limites-administrativos-mapas"),
        ],
    }


def get_compare_summary_text(
    first_district: str,
    second_district: str,
    metric: str,
    topic: str,
    mobility_threshold: int = DEFAULT_MOBILITY_THRESHOLD,
    land_use_filter: list[str] | None = None,
) -> str | list[str | html.Span]:
    first_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == first_district].iloc[0]
    second_row = DISTRICT_FRAME.loc[DISTRICT_FRAME["district_name"] == second_district].iloc[0]

    if topic == "land_use":
        selected_classes = normalise_land_use_filter_values(land_use_filter, [first_district, second_district])
        available_classes = get_land_use_class_values([first_district, second_district])
        filtered_view = len(selected_classes) != len(available_classes)
        first_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(first_district, GRID_FRAME.head(0).copy()).copy()
        second_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(second_district, GRID_FRAME.head(0).copy()).copy()
        if first_cells.empty or second_cells.empty:
            return "This comparison is partly limited because one or both districts do not yet have matching land-use grid data."
        if filtered_view:
            first_visible = first_cells[first_cells["lu_2018_class_simplified"].isin(selected_classes)]
            second_visible = second_cells[second_cells["lu_2018_class_simplified"].isin(selected_classes)]
            return [
                build_compare_district_name(first_district),
                f" currently shows {len(first_visible):,} visible 250m cells under the active land-use filter, while ",
                build_compare_district_name(second_district),
                f" shows {len(second_visible):,}.",
            ]
        first_dominant = first_cells["lu_2018_class_simplified"].value_counts().idxmax()
        second_dominant = second_cells["lu_2018_class_simplified"].value_counts().idxmax()
        if first_dominant == second_dominant:
            return f"Both districts are currently dominated by {format_land_use_signal(first_dominant).lower()} in the research-derived land-use grid."
        return [
            build_compare_district_name(first_district),
            f" is currently dominated by {format_land_use_signal(first_dominant).lower()}, while ",
            build_compare_district_name(second_district),
            f" is dominated by {format_land_use_signal(second_dominant).lower()}.",
        ]

    if topic == "height":
        first_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(first_district, GRID_FRAME.head(0).copy()).copy()
        second_cells = LAND_USE_DISTRICT_FRAME_CACHE.get(second_district, GRID_FRAME.head(0).copy()).copy()
        first_values = first_cells[first_cells[metric].notna()][metric]
        second_values = second_cells[second_cells[metric].notna()][metric]
        if first_values.empty or second_values.empty:
            return "This comparison is partly limited because one or both districts do not yet have matching building-height grid data."
        first_value = first_values.mean() if metric == "height_mean" else first_values.max()
        second_value = second_values.mean() if metric == "height_mean" else second_values.max()
        label = "average building height" if metric == "height_mean" else "maximum observed cell height"
        return [
            build_compare_district_name(first_district),
            f" records {label} of {first_value:.1f} m, while ",
            build_compare_district_name(second_district),
            f" records {second_value:.1f} m.",
        ]

    if topic == "mobility":
        first_cells = MOBILITY_GRID_FRAME.loc[MOBILITY_GRID_FRAME["district_name"] == first_district].copy()
        second_cells = MOBILITY_GRID_FRAME.loc[MOBILITY_GRID_FRAME["district_name"] == second_district].copy()
        if first_cells.empty or second_cells.empty:
            return "This comparison is partly limited because one or both districts do not yet have matching mobility grid data."
        first_count = int((first_cells["pt_stop_count"] >= mobility_threshold).sum())
        second_count = int((second_cells["pt_stop_count"] >= mobility_threshold).sum())
        return [
            build_compare_district_name(first_district),
            f" has {first_count:,} grid cells at or above the current threshold of {mobility_threshold} bus stops, while ",
            build_compare_district_name(second_district),
            f" has {second_count:,}.",
        ]

    compare_specs = {
        "population_total": ("has_population_data", "population total", lambda row: f"{int(row['population_total']):,} residents"),
        "population_density_km2": ("has_population_data", "population density", lambda row: format_density(row["population_density_km2"])),
        "housing_total": ("has_housing_data", "EMVS housing total", lambda row: f"{int(row['housing_total']):,}"),
        "housing_per_1000_residents": ("has_housing_data", "EMVS units per 1,000 residents", lambda row: format_housing_rate(row["housing_per_1000_residents"])),
        "green_area_ha": ("has_green_data", "green area total", lambda row: format_float(row["green_area_ha"], " ha")),
        "green_area_per_10000": ("has_green_data", "green area per 10,000 residents", lambda row: format_float(row["green_area_per_10000"], " ha / 10,000 residents")),
        "income_per_person": ("has_economy_data", "income per person", lambda row: format_float(row["income_per_person"], " €", 0)),
        "household_income": ("has_economy_data", "household income", lambda row: format_float(row["household_income"], " €", 0)),
        "unemployment_total": ("has_employment_data", "registered unemployment", lambda row: format_float(row["unemployment_total"], "", 0)),
        "unemployment_rate": ("has_employment_data", "unemployment rate", lambda row: format_float(row["unemployment_rate"], "%", 2)),
        "vulnerability_index": ("has_vulnerability_data", "territorial vulnerability index", lambda row: format_float(row["vulnerability_index"])),
        "vulnerability_employment": ("has_vulnerability_data", "economy and employment vulnerability index", lambda row: format_float(row["vulnerability_employment"])),
    }

    has_flag, metric_label, formatter = compare_specs.get(
        metric,
        ("has_population_data", "population total", lambda row: f"{int(row['population_total']):,} residents"),
    )
    first_has_data = bool(first_row[has_flag])
    second_has_data = bool(second_row[has_flag])
    if not first_has_data or not second_has_data:
        return "This comparison is partly limited because one or both districts do not yet have matching topic data."
    return [
        build_compare_district_name(first_district),
        f" records {formatter(first_row)} for {metric_label}, while ",
        build_compare_district_name(second_district),
        f" records {formatter(second_row)}.",
    ]


def build_shared_compare_section(
    first_district: str,
    second_district: str,
    metric: str,
    topic: str,
    mobility_threshold: int = DEFAULT_MOBILITY_THRESHOLD,
    land_use_filter: list[str] | None = None,
) -> html.Div:
    context = get_shared_compare_topic_context(topic, metric, mobility_threshold)
    summary_chip_row = build_summary_chip_row(
        get_shared_compare_summary_chips(
            first_district,
            second_district,
            topic,
            metric,
            mobility_threshold,
            land_use_filter,
        )
    )
    return html.Div(
        [
            html.Div(
                [
                    build_title_topic_icon(topic, "#486175"),
                    html.H2(
                        context["topic_label"],
                        className="panel-title",
                    ),
                ],
                className="panel-title-row",
            ),
            html.P(f"{first_district} / {second_district}", className="panel-subtitle"),
            summary_chip_row,
            html.Div(
                [
                    html.H4("How to read it"),
                    html.P(emphasize_numbers(context["how_text"])),
                    html.H4("Why it matters"),
                    html.P(emphasize_numbers(context["why_text"])),
                ],
                className="panel-body",
            ),
            html.Div(
                [
                    build_panel_meta_item(
                        PANEL_META_DATA_ICON,
                        "Source",
                        html.Div(
                            [
                                html.P(context["sources_text"], className="panel-meta-text"),
                                build_panel_meta_links(context["source_links"]),
                                html.P(f"Reference date: {context['reference_date']}", className="panel-meta-subtext"),
                            ]
                        ),
                        tone="plain",
                    ),
                    build_panel_meta_item(
                        PANEL_META_ALERT_ICON,
                        "Keep in mind",
                        html.Ul(
                            [html.Li(caveat) for caveat in context["caveats"]],
                            className="panel-meta-list",
                        ),
                        tone="warning",
                    ),
                ],
                className="panel-meta-grid",
            ),
        ],
        className="metric-card shared-compare-card",
    )


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
                                    html.Div(
                                        build_panel_meta_item(
                                            PANEL_META_ALERT_ICON,
                                            "Keep in mind",
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
                                            tone="warning",
                                        ),
                                        style={"marginTop": "12px"},
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
                            html.Div(
                                [
                                    html.Img(src=PANEL_META_ALERT_ICON, alt="", className="panel-meta-icon", draggable="false"),
                                    html.Div(
                                        html.P(emphasize_numbers(caveat_text), className="panel-meta-text"),
                                    ),
                                ],
                                className="panel-meta-item panel-meta-item-warning typology-keep-in-mind",
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
                            html.Div(
                                [
                                    html.Img(src=PANEL_META_ALERT_ICON, alt="", className="panel-meta-icon", draggable="false"),
                                    html.Div(
                                        html.P(
                                            emphasize_numbers(
                                                "This is an exploratory result based on indicators from different sources and years. It is not a diagnosis or a causal explanation."
                                            ),
                                            className="panel-meta-text",
                                        ),
                                    ),
                                ],
                                className="panel-meta-item panel-meta-item-warning typology-keep-in-mind",
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


