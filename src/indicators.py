import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from src.schemas import (
    CollectedSource,
    IndicatorSelectionEntry,
    IndicatorSelectionReport,
    IndicatorSourceReport,
)


AREA_FIELD_CANDIDATES = (
    "distrito",
    "desc_distrito",
    "cod_distrito",
    "barrio",
    "desc_barrio",
    "cod_barrio",
    "cod_dist_barrio",
    "fua_name",
    "fua_code",
)
TYPE_FIELD_CANDIDATES = (
    "tipo",
    "subtipo",
    "descripcion_entidad",
)
POPULATION_VALUE_COLUMNS = (
    "espanoleshombres",
    "espanolesmujeres",
    "extranjeroshombres",
    "extranjerosmujeres",
)

TradeoffSummary = dict[str, str]
ApplicabilityCheck = Callable[[CollectedSource], tuple[bool, str]]
IndicatorBuilder = Callable[[CollectedSource], dict[str, pd.DataFrame]]


@dataclass(frozen=True)
class IndicatorTemplate:
    indicator_id: str
    indicator_name: str
    description: str
    applicability_check: ApplicabilityCheck
    builder: IndicatorBuilder
    tradeoffs: TradeoffSummary


def first_available_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for column in candidates:
        if column in df.columns:
            return column

    return None


def check_transport_indicator(source: CollectedSource) -> tuple[bool, str]:
    if source.source_metadata.source_type != "tabular":
        return False, "Skipped because this indicator is only defined for tabular sources."

    if "mode_main" not in source.data.columns:
        return False, "Skipped because the source does not include a 'mode_main' field."

    return True, "Selected because the source includes the mobility category field 'mode_main'."


def check_landuse_indicator(source: CollectedSource) -> tuple[bool, str]:
    if source.source_metadata.source_type != "geospatial":
        return False, "Skipped because this indicator is only defined for geospatial sources."

    required_columns = {"class_2018", "area"}
    missing_columns = sorted(required_columns.difference(source.data.columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        return False, f"Skipped because the source is missing required land-use fields: {missing}."

    return True, "Selected because the source contains both land-use class and area fields."


def check_records_by_area_indicator(source: CollectedSource) -> tuple[bool, str]:
    if source.source_metadata.source_type != "tabular":
        return False, "Skipped because area-based record counts are currently bounded to tabular sources."

    area_field = first_available_column(source.data, AREA_FIELD_CANDIDATES)
    if area_field is None:
        return False, "Skipped because no district-, barrio-, or area-like field was detected."

    return True, f"Selected because the source includes the area-like field '{area_field}'."


def check_type_summary_indicator(source: CollectedSource) -> tuple[bool, str]:
    if source.source_metadata.source_type != "tabular":
        return False, "Skipped because category summaries are currently bounded to tabular sources."

    type_field = first_available_column(source.data, TYPE_FIELD_CANDIDATES)
    if type_field is None:
        return False, "Skipped because no suitable category field such as 'tipo' or 'descripcion_entidad' was found."

    return True, f"Selected because the source includes the category field '{type_field}'."


def check_historical_population_indicator(source: CollectedSource) -> tuple[bool, str]:
    if source.source_metadata.source_type != "tabular":
        return False, "Skipped because historical population summaries are currently bounded to tabular sources."

    missing_columns = [
        column for column in POPULATION_VALUE_COLUMNS
        if column not in source.data.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        return False, f"Skipped because required population columns are missing: {missing}."

    return True, "Selected because the source includes the population subtotal fields needed to compute totals."


def build_transport_indicators(source: CollectedSource) -> dict[str, pd.DataFrame]:
    """
    Build indicators for transport-style tabular data.
    """
    df = source.data.copy()

    mode_summary = (
        df["mode_main"]
        .dropna()
        .value_counts()
        .rename_axis("mode_main")
        .reset_index(name="trips")
    )

    if mode_summary.empty:
        return {}

    total_trips = mode_summary["trips"].sum()
    mode_summary["percent_of_trips"] = (
        mode_summary["trips"] / total_trips * 100
    ).round(2)

    return {
        "transport_mode_summary": mode_summary
    }


def build_landuse_indicators(source: CollectedSource) -> dict[str, pd.DataFrame]:
    """
    Build indicators for geospatial land-use data.
    """
    gdf = source.data.copy()

    landuse_summary = (
        gdf.dropna(subset=["class_2018", "area"])
        .groupby("class_2018", as_index=False)["area"]
        .sum()
    )

    if landuse_summary.empty:
        return {}

    landuse_summary = landuse_summary.sort_values(by="area", ascending=False)

    total_area = landuse_summary["area"].sum()
    landuse_summary["total_area_km2"] = (landuse_summary["area"] / 1_000_000).round(2)
    landuse_summary["percent_of_total_area"] = (
        landuse_summary["area"] / total_area * 100
    ).round(2)

    landuse_summary = landuse_summary.drop(columns=["area"])

    return {
        "landuse_area_summary": landuse_summary
    }


def build_records_by_area_indicator(source: CollectedSource) -> dict[str, pd.DataFrame]:
    """
    Build a generic count-by-area indicator when a source includes district,
    barrio, or comparable location fields.
    """
    df = source.data.copy()
    area_field = first_available_column(df, AREA_FIELD_CANDIDATES)

    if area_field is None:
        return {}

    area_summary = (
        df[area_field]
        .dropna()
        .astype(str)
        .value_counts()
        .rename_axis(area_field)
        .reset_index(name="records")
    )

    if area_summary.empty:
        return {}

    total_records = area_summary["records"].sum()
    area_summary["percent_of_records"] = (
        area_summary["records"] / total_records * 100
    ).round(2)

    return {
        f"records_by_{area_field}": area_summary
    }


def build_type_summary_indicator(source: CollectedSource) -> dict[str, pd.DataFrame]:
    """
    Build a generic category summary for facility/place-like datasets.
    """
    df = source.data.copy()
    type_field = first_available_column(df, TYPE_FIELD_CANDIDATES)

    if type_field is None:
        return {}

    type_summary = (
        df[type_field]
        .dropna()
        .astype(str)
        .value_counts()
        .rename_axis(type_field)
        .reset_index(name="records")
    )

    if type_summary.empty:
        return {}

    total_records = type_summary["records"].sum()
    type_summary["percent_of_records"] = (
        type_summary["records"] / total_records * 100
    ).round(2)

    return {
        f"records_by_{type_field}": type_summary
    }


def build_historical_population_indicator(source: CollectedSource) -> dict[str, pd.DataFrame]:
    """
    Build a population summary for historical padrón-style datasets.
    """
    df = source.data.copy()

    if not all(column in df.columns for column in POPULATION_VALUE_COLUMNS):
        return {}

    df["total_population"] = df[list(POPULATION_VALUE_COLUMNS)].fillna(0).sum(axis=1)
    area_field = first_available_column(
        df,
        ("desc_distrito", "distrito", "desc_barrio", "barrio", "cod_distrito"),
    )

    if area_field is None:
        total_population_summary = pd.DataFrame(
            {
                "metric": ["total_population"],
                "value": [int(df["total_population"].sum())],
            }
        )
        return {"historical_population_total": total_population_summary}

    population_summary = (
        df.groupby(area_field, as_index=False)["total_population"]
        .sum()
        .sort_values(by="total_population", ascending=False)
    )

    if population_summary.empty:
        return {}

    total_population = population_summary["total_population"].sum()
    population_summary["percent_of_total_population"] = (
        population_summary["total_population"] / total_population * 100
    ).round(2)

    return {
        f"population_by_{area_field}": population_summary
    }


INDICATOR_TEMPLATES = (
    IndicatorTemplate(
        indicator_id="transport_mode_summary",
        indicator_name="Transport Mode Summary",
        description="Summarise transport records by their main travel mode.",
        applicability_check=check_transport_indicator,
        builder=build_transport_indicators,
        tradeoffs={
            "accuracy": "Medium to high when 'mode_main' is consistently coded, but only for this specific schema.",
            "interpretability": "High, because modal shares are easy to explain in a walkthrough.",
            "computational_cost": "Low, because the calculation is a simple grouped count.",
        },
    ),
    IndicatorTemplate(
        indicator_id="landuse_area_summary",
        indicator_name="Land-Use Area Summary",
        description="Summarise mapped land-use classes by their total area.",
        applicability_check=check_landuse_indicator,
        builder=build_landuse_indicators,
        tradeoffs={
            "accuracy": "High for mapped polygons, but still depends on source classification quality and map scale.",
            "interpretability": "High, because dominant classes and shares are easy to communicate.",
            "computational_cost": "Low to medium, depending on the size of the geospatial layer.",
        },
    ),
    IndicatorTemplate(
        indicator_id="records_by_area",
        indicator_name="Records By Area",
        description="Count how many records fall under each detected area-like field.",
        applicability_check=check_records_by_area_indicator,
        builder=build_records_by_area_indicator,
        tradeoffs={
            "accuracy": "Medium, because record counts do not necessarily reflect intensity, capacity, or demand.",
            "interpretability": "High, because district or barrio counts are easy to inspect and compare.",
            "computational_cost": "Low, because the calculation is a basic aggregation.",
        },
    ),
    IndicatorTemplate(
        indicator_id="records_by_type",
        indicator_name="Records By Type",
        description="Count records by a detected category or facility-type field.",
        applicability_check=check_type_summary_indicator,
        builder=build_type_summary_indicator,
        tradeoffs={
            "accuracy": "Medium, because it depends on how consistently source categories are defined.",
            "interpretability": "High, because category counts are straightforward to explain.",
            "computational_cost": "Low, because the calculation is a basic aggregation.",
        },
    ),
    IndicatorTemplate(
        indicator_id="historical_population",
        indicator_name="Historical Population Summary",
        description="Compute total population from demographic subtotal columns and summarise by area when possible.",
        applicability_check=check_historical_population_indicator,
        builder=build_historical_population_indicator,
        tradeoffs={
            "accuracy": "Medium to high when subtotal fields are complete, but aggregation can hide internal differences.",
            "interpretability": "Medium to high, because totals are understandable but still depend on demographic field definitions.",
            "computational_cost": "Low, because the calculation is a simple row-wise sum and grouping step.",
        },
    ),
)


def build_indicators_for_source(
    source: CollectedSource,
) -> tuple[dict[str, pd.DataFrame], IndicatorSourceReport]:
    """
    Evaluate the indicator registry for one source and record both selected and
    skipped indicator paths for transparency.
    """
    indicators: dict[str, pd.DataFrame] = {}
    source_report = IndicatorSourceReport(
        source_id=source.source_id,
        source_name=source.source_metadata.source_name,
        source_type=source.source_metadata.source_type,
    )

    for template in INDICATOR_TEMPLATES:
        applicable, applicability_reason = template.applicability_check(source)

        if not applicable:
            source_report.skipped_indicators.append(
                IndicatorSelectionEntry(
                    indicator_id=template.indicator_id,
                    indicator_name=template.indicator_name,
                    status="skipped",
                    description=template.description,
                    applicability_reason=applicability_reason,
                    tradeoffs=template.tradeoffs,
                )
            )
            continue

        template_outputs = template.builder(source)
        if not template_outputs:
            source_report.selected_indicators.append(
                IndicatorSelectionEntry(
                    indicator_id=template.indicator_id,
                    indicator_name=template.indicator_name,
                    status="empty_result",
                    description=template.description,
                    applicability_reason=(
                        f"{applicability_reason} The calculation ran, but it produced no non-empty summary table."
                    ),
                    tradeoffs=template.tradeoffs,
                )
            )
            continue

        indicators.update(template_outputs)
        source_report.selected_indicators.append(
            IndicatorSelectionEntry(
                indicator_id=template.indicator_id,
                indicator_name=template.indicator_name,
                status="selected",
                description=template.description,
                applicability_reason=applicability_reason,
                output_names=sorted(template_outputs.keys()),
                tradeoffs=template.tradeoffs,
            )
        )

    return indicators, source_report


def build_indicators(
    sources: list[CollectedSource],
) -> tuple[dict[str, dict[str, pd.DataFrame]], IndicatorSelectionReport]:
    """
    Build indicators for all harmonised sources and capture how the indicator
    selection logic behaved for each source.
    """
    indicator_results: dict[str, dict[str, pd.DataFrame]] = {}
    source_reports: list[IndicatorSourceReport] = []

    for source in sources:
        source_indicators, source_report = build_indicators_for_source(source)
        indicator_results[source.source_id] = source_indicators
        source_reports.append(source_report)

    selected_count = sum(
        len(
            [
                entry for entry in source_report.selected_indicators
                if entry.status == "selected"
            ]
        )
        for source_report in source_reports
    )
    status = "completed" if selected_count > 0 else "warning"
    indicator_report = IndicatorSelectionReport(
        status=status,
        generated_at=datetime.now(),
        source_count=len(sources),
        sources=source_reports,
        workflow_notes=[
            "Indicator selection is template-based and deterministic rather than fully automated.",
            "Templates are evaluated against source type and available fields so new datasets can surface different indicator paths without changing the whole workflow.",
            "Skipped indicators remain visible to support transparency, review, and later extension.",
        ],
    )

    return indicator_results, indicator_report


def save_indicator_report(report: IndicatorSelectionReport) -> Path:
    """
    Save indicator selection details to outputs/reports/indicator_selection_report.json
    """
    output_path = Path("outputs/reports/indicator_selection_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file_handle:
        json.dump(report.model_dump(mode="json"), file_handle, indent=2, ensure_ascii=False)

    return output_path
