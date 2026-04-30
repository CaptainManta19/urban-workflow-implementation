import json
from itertools import combinations
from pathlib import Path

from src.schemas import CollectedSource


def extract_source_year(source: CollectedSource) -> int | None:
    """
    Prefer the year hint prepared during collection.
    """
    return source.source_metadata.compatibility_hints.inferred_reference_year


def normalise_column_set(columns: list[str]) -> set[str]:
    return {column.lower() for column in columns}


def shared_values(first: list[str], second: list[str]) -> list[str]:
    second_lookup = {value.lower(): value for value in second}
    shared = []

    for value in first:
        if value.lower() in second_lookup:
            shared.append(value)

    return sorted(set(shared))


def summarise_source(source: CollectedSource) -> dict:
    meta = source.source_metadata

    return {
        "source_id": source.source_id,
        "source_name": meta.source_name,
        "source_type": meta.source_type,
        "file_format": meta.file_format,
        "acquisition_mode": meta.access_metadata.acquisition_mode,
        "year": extract_source_year(source),
        "year_inference_basis": meta.compatibility_hints.year_inference_basis,
        "columns": meta.columns,
        "candidate_join_columns": meta.compatibility_hints.candidate_join_columns,
        "candidate_spatial_unit_columns": meta.compatibility_hints.candidate_spatial_unit_columns,
        "geometry_present": meta.compatibility_hints.geometry_present,
        "crs": meta.crs,
        "warning_count": len(meta.transparency.warnings),
    }


def evaluate_temporal_rule(sources: list[CollectedSource]) -> tuple[dict, list[str], list[str]]:
    years_by_source = {
        source.source_id: extract_source_year(source)
        for source in sources
    }
    resolved_years = [year for year in years_by_source.values() if year is not None]

    if not resolved_years:
        return (
            {
                "rule_id": "temporal_reference_visibility",
                "rule_name": "Temporal Reference Visibility",
                "description": "Compatibility improves when each source has an explicit or inferable reference year.",
                "status": "warning",
                "evidence": years_by_source,
                "implication": "Temporal comparability remains uncertain and requires human interpretation.",
            },
            [
                "At least one source is missing a clear reference year, so temporal comparability is only partial."
            ],
            [
                "Record or confirm a reference year for each source before attempting time-sensitive integration."
            ],
        )

    if len(set(resolved_years)) == 1 and len(resolved_years) == len(sources):
        aligned_year = resolved_years[0]
        return (
            {
                "rule_id": "temporal_reference_visibility",
                "rule_name": "Temporal Reference Visibility",
                "description": "Compatibility improves when each source has an explicit or inferable reference year.",
                "status": "pass",
                "evidence": years_by_source,
                "implication": f"All sources currently appear to reference {aligned_year}, which supports time-aware comparison.",
            },
            [],
            [],
        )

    return (
        {
            "rule_id": "temporal_reference_visibility",
            "rule_name": "Temporal Reference Visibility",
            "description": "Compatibility improves when each source has an explicit or inferable reference year.",
            "status": "warning",
            "evidence": years_by_source,
            "implication": "Some sources have a year while others do not, or the years differ, so temporal alignment remains uncertain.",
        },
        [
            "The sources do not provide a fully shared and explicit temporal reference."
        ],
        [
            "Treat cross-source comparison as exploratory unless a shared time frame is confirmed."
        ],
    )


def evaluate_column_rule(sources: list[CollectedSource]) -> tuple[dict, list[str], list[str], list[str]]:
    shared_columns = normalise_column_set(sources[0].source_metadata.columns)
    original_lookup = {
        column.lower(): column
        for column in sources[0].source_metadata.columns
    }

    for source in sources[1:]:
        shared_columns &= normalise_column_set(source.source_metadata.columns)

    resolved_columns = sorted(original_lookup[column] for column in shared_columns if column in original_lookup)

    if resolved_columns:
        return (
            {
                "rule_id": "direct_shared_fields",
                "rule_name": "Direct Shared Fields",
                "description": "Direct joins become easier when sources share the same field names after harmonisation.",
                "status": "pass",
                "evidence": {"shared_columns": resolved_columns},
                "implication": "Some direct field-level alignment is available for further review.",
            },
            [],
            [],
            resolved_columns,
        )

    return (
        {
            "rule_id": "direct_shared_fields",
            "rule_name": "Direct Shared Fields",
            "description": "Direct joins become easier when sources share the same field names after harmonisation.",
            "status": "warning",
            "evidence": {"shared_columns": []},
            "implication": "No single shared field name is available across all sources for immediate direct merging.",
        },
        [
            "No shared columns were found across all sources that would support a simple direct merge."
        ],
        [
            "Use inferred spatial-unit or identifier fields instead of assuming a direct field-level join."
        ],
        [],
    )


def evaluate_geospatial_rule(sources: list[CollectedSource]) -> tuple[dict, list[str], list[str]]:
    geospatial_sources = [
        source for source in sources
        if source.source_metadata.compatibility_hints.geometry_present
    ]

    if not geospatial_sources:
        return (
            {
                "rule_id": "geospatial_reference_availability",
                "rule_name": "Geospatial Reference Availability",
                "description": "Spatial integration requires at least one explicit geographic reference.",
                "status": "warning",
                "evidence": {"geospatial_source_ids": []},
                "implication": "Spatial comparison is not available because no source currently carries geometry.",
            },
            [
                "No geospatial source is available to anchor spatial comparison or aggregation."
            ],
            [
                "Add a geospatial layer or explicit geographic reference before spatial integration."
            ],
        )

    crs_values = sorted(
        {
            source.source_metadata.crs
            for source in geospatial_sources
            if source.source_metadata.crs is not None
        }
    )

    if len(crs_values) <= 1:
        return (
            {
                "rule_id": "geospatial_reference_availability",
                "rule_name": "Geospatial Reference Availability",
                "description": "Spatial integration requires at least one explicit geographic reference.",
                "status": "pass",
                "evidence": {
                    "geospatial_source_ids": [source.source_id for source in geospatial_sources],
                    "crs_values": crs_values,
                },
                "implication": "At least one spatial reference is available and no CRS conflict is currently visible.",
            },
            [],
            [],
        )

    return (
        {
            "rule_id": "geospatial_reference_availability",
            "rule_name": "Geospatial Reference Availability",
            "description": "Spatial integration requires at least one explicit geographic reference.",
            "status": "warning",
            "evidence": {
                "geospatial_source_ids": [source.source_id for source in geospatial_sources],
                "crs_values": crs_values,
            },
            "implication": "Spatial references are available, but a CRS mismatch would need resolution before direct spatial operations.",
        },
        [
            "Multiple coordinate reference systems were detected across geospatial sources."
        ],
        [
            "Reproject geospatial layers to a shared CRS before direct spatial comparison or overlay."
        ],
    )


def evaluate_transparency_rule(sources: list[CollectedSource]) -> tuple[dict, list[str], list[str]]:
    warning_summary = {
        source.source_id: source.source_metadata.transparency.warnings
        for source in sources
        if source.source_metadata.transparency.warnings
    }

    if not warning_summary:
        return (
            {
                "rule_id": "collection_transparency_completeness",
                "rule_name": "Collection Transparency Completeness",
                "description": "Compatibility claims are stronger when collection assumptions and warnings are explicit.",
                "status": "pass",
                "evidence": {"sources_with_warnings": {}},
                "implication": "No major collection-time warnings are currently attached to these sources.",
            },
            [],
            [],
        )

    return (
        {
            "rule_id": "collection_transparency_completeness",
            "rule_name": "Collection Transparency Completeness",
            "description": "Compatibility claims are stronger when collection assumptions and warnings are explicit.",
            "status": "warning",
            "evidence": {"sources_with_warnings": warning_summary},
            "implication": "Collection-time warnings should be carried into compatibility interpretation rather than ignored.",
        },
        [
            "Collection-time warnings remain relevant for compatibility interpretation."
        ],
        [
            "Review source-specific warnings before treating any integration path as robust."
        ],
    )


def build_pairwise_assessments(sources: list[CollectedSource]) -> list[dict]:
    pairwise_assessments: list[dict] = []

    for first, second in combinations(sources, 2):
        first_meta = first.source_metadata
        second_meta = second.source_metadata

        first_year = extract_source_year(first)
        second_year = extract_source_year(second)

        if first_year is not None and second_year is not None:
            temporal_alignment = "aligned" if first_year == second_year else "different"
        else:
            temporal_alignment = "uncertain"

        shared_columns = shared_values(first_meta.columns, second_meta.columns)
        shared_join_candidates = shared_values(
            first_meta.compatibility_hints.candidate_join_columns,
            second_meta.compatibility_hints.candidate_join_columns,
        )
        shared_area_fields = shared_values(
            first_meta.compatibility_hints.candidate_spatial_unit_columns,
            second_meta.compatibility_hints.candidate_spatial_unit_columns,
        )

        if (
            first_meta.compatibility_hints.geometry_present
            and second_meta.compatibility_hints.geometry_present
        ):
            if first_meta.crs == second_meta.crs:
                spatial_relation = "both geospatial with matching CRS"
            else:
                spatial_relation = "both geospatial but CRS alignment is unclear"
        elif (
            first_meta.compatibility_hints.geometry_present
            or second_meta.compatibility_hints.geometry_present
        ):
            spatial_relation = "one geospatial source and one non-geospatial source"
        else:
            spatial_relation = "no explicit geometry in either source"

        pairwise_assessments.append(
            {
                "source_pair": [first.source_id, second.source_id],
                "temporal_alignment": temporal_alignment,
                "shared_columns": shared_columns,
                "shared_join_candidates": shared_join_candidates,
                "shared_area_fields": shared_area_fields,
                "spatial_relation": spatial_relation,
            }
        )

    return pairwise_assessments


def build_integration_paths(sources: list[CollectedSource]) -> list[dict]:
    geospatial_sources = [
        source.source_id
        for source in sources
        if source.source_metadata.compatibility_hints.geometry_present
    ]
    tabular_sources = [
        source.source_id
        for source in sources
        if source.source_metadata.source_type == "tabular"
    ]

    all_candidate_area_fields: set[str] = set()
    all_candidate_join_fields: set[str] = set()

    for source in sources:
        meta = source.source_metadata
        all_candidate_area_fields.update(meta.compatibility_hints.candidate_spatial_unit_columns)
        all_candidate_join_fields.update(meta.compatibility_hints.candidate_join_columns)

    paths = [
        {
            "path_id": "parallel_use",
            "path_name": "Use Sources In Parallel",
            "status": "viable",
            "description": "Keep sources separate and compare their findings side by side rather than forcing a merge.",
            "requirements": [
                "Explain differences in scope, time frame, and geography explicitly during interpretation."
            ],
            "tradeoffs": {
                "accuracy": "High, because fewer transformation assumptions are introduced.",
                "interpretability": "High, because each source remains inspectable in its original context.",
                "computational_cost": "Low, because no complex integration step is required.",
            },
        }
    ]

    if geospatial_sources and all_candidate_area_fields:
        paths.append(
            {
                "path_id": "area_based_alignment",
                "path_name": "Align Through Shared Area Labels",
                "status": "possible",
                "description": "Use area-like fields such as district, barrio, or similar units as a common comparison frame.",
                "requirements": [
                    "Confirm that the fields refer to the same geographic unit and naming convention.",
                    "Normalize spelling, casing, and coding differences before comparison.",
                ],
                "tradeoffs": {
                    "accuracy": "Medium, because aggregation can hide local variation or boundary differences.",
                    "interpretability": "High, because area-based units are often easier to explain to stakeholders.",
                    "computational_cost": "Low to medium, depending on cleaning and aggregation needs.",
                },
            }
        )

    if len(geospatial_sources) >= 1 and len(tabular_sources) >= 1:
        paths.append(
            {
                "path_id": "geographic_enrichment",
                "path_name": "Add Geographic Reference To Tabular Sources",
                "status": "possible",
                "description": "Introduce a shared spatial unit or geocode the tabular data before integrating it with geospatial layers.",
                "requirements": [
                    "Identify a defensible geographic reference for the tabular source.",
                    "Document whether geocoding, manual mapping, or aggregation was used.",
                ],
                "tradeoffs": {
                    "accuracy": "Medium to high, but depends on the quality of the geographic reference step.",
                    "interpretability": "Medium, because geocoding or aggregation adds another transformation layer.",
                    "computational_cost": "Medium, because geographic enrichment adds extra processing steps.",
                },
            }
        )

    if all_candidate_join_fields:
        paths.append(
            {
                "path_id": "field_based_linkage",
                "path_name": "Link Through Candidate Identifier Fields",
                "status": "conditional",
                "description": "Use likely identifier or label fields to create a relational linkage between sources.",
                "requirements": [
                    "Verify that the candidate fields refer to the same entity type.",
                    "Check for duplicates, naming inconsistencies, and partial matches.",
                ],
                "tradeoffs": {
                    "accuracy": "Variable, because identifier fields may look similar without actually being compatible.",
                    "interpretability": "Medium, because matching logic must be explained clearly.",
                    "computational_cost": "Low to medium, depending on matching complexity.",
                },
            }
        )

    return paths


def choose_suggested_next_step(integration_paths: list[dict]) -> str:
    for preferred_path_id in (
        "area_based_alignment",
        "geographic_enrichment",
        "field_based_linkage",
        "parallel_use",
    ):
        for path in integration_paths:
            if path["path_id"] == preferred_path_id:
                return path["description"]

    return "Review the compatibility report manually before selecting an integration strategy."


def build_compatibility_report(sources: list[CollectedSource]) -> dict:
    """
    Build a more explicit compatibility assessment using collection-time metadata.
    """
    if len(sources) < 2:
        return {
            "status": "warning",
            "message": "Compatibility assessment requires at least two sources."
        }

    source_summaries = [summarise_source(source) for source in sources]
    pairwise_assessments = build_pairwise_assessments(sources)

    rule_evaluations = []
    reasons: list[str] = []
    requirements_for_integration: list[str] = []

    temporal_rule, temporal_reasons, temporal_requirements = evaluate_temporal_rule(sources)
    rule_evaluations.append(temporal_rule)
    reasons.extend(temporal_reasons)
    requirements_for_integration.extend(temporal_requirements)

    column_rule, column_reasons, column_requirements, shared_columns = evaluate_column_rule(sources)
    rule_evaluations.append(column_rule)
    reasons.extend(column_reasons)
    requirements_for_integration.extend(column_requirements)

    geospatial_rule, geospatial_reasons, geospatial_requirements = evaluate_geospatial_rule(sources)
    rule_evaluations.append(geospatial_rule)
    reasons.extend(geospatial_reasons)
    requirements_for_integration.extend(geospatial_requirements)

    transparency_rule, transparency_reasons, transparency_requirements = evaluate_transparency_rule(sources)
    rule_evaluations.append(transparency_rule)
    reasons.extend(transparency_reasons)
    requirements_for_integration.extend(transparency_requirements)

    all_years = [extract_source_year(source) for source in sources]
    resolved_years = [year for year in all_years if year is not None]
    same_year = len(set(resolved_years)) == 1 and len(resolved_years) == len(sources)

    if same_year:
        temporal_note = f"All sources currently appear to refer to {resolved_years[0]}."
    elif resolved_years:
        temporal_note = (
            "Some temporal information is available, but the sources do not fully align or remain only partially resolved."
        )
    else:
        temporal_note = "The sources do not currently provide a shared explicit temporal reference."

    integration_paths = build_integration_paths(sources)
    suggested_next_step = choose_suggested_next_step(integration_paths)

    direct_merge_possible = bool(shared_columns) and all(
        rule["status"] == "pass"
        for rule in (column_rule, transparency_rule)
    )

    report = {
        "status": "completed",
        "source_count": len(sources),
        "sources": source_summaries,
        "shared_columns": shared_columns,
        "same_year": same_year,
        "temporal_note": temporal_note,
        "direct_merge_possible": direct_merge_possible,
        "rule_evaluations": rule_evaluations,
        "pairwise_assessments": pairwise_assessments,
        "integration_paths": integration_paths,
        "reasons": sorted(set(reasons)),
        "requirements_for_integration": sorted(set(requirements_for_integration)),
        "suggested_next_step": suggested_next_step,
    }

    return report


def save_compatibility_report(report: dict) -> Path:
    """
    Save compatibility report to outputs/reports/compatibility_report.json
    """
    output_path = Path("outputs/reports/compatibility_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file_handle:
        json.dump(report, file_handle, indent=2, ensure_ascii=False)

    return output_path
