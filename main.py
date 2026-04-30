from pathlib import Path
from typing import Literal

from langgraph.graph import StateGraph, START, END

from src.collection import collect_sources, save_collection_report
from src.harmonise import harmonise_source
from src.profile import build_source_profiles, save_source_profiles
from src.compatibility import build_compatibility_report, save_compatibility_report
from src.indicators import build_indicators, save_indicator_report
from src.schemas import UrbanWorkflowState, HumanReviewState
from src.interpretation import (
    build_interpretation_context,
    generate_interpretation_draft,
    render_interpretation_draft,
    save_interpretation_context,
    save_interpretation_draft,
    save_interpretation_summary,
)


def ask_to_continue(message: str) -> bool:
    while True:
        response = input(f"{message} (y/n): ").strip().lower()

        if response in ["y", "yes"]:
            return True
        if response in ["n", "no"]:
            return False

        print("Please enter 'y' or 'n'.")


def collect_sources_node(state: UrbanWorkflowState) -> dict:
    sources, collection_report = collect_sources()
    report_path = save_collection_report(collection_report)
    print(f"\nSaved collection report to: {report_path}")
    return {
        "sources": sources,
        "collection_report": collection_report.model_dump(mode="json"),
    }


def format_acquisition_mode(acquisition_mode: str) -> str:
    if acquisition_mode == "api":
        return "API"
    return acquisition_mode.replace("_", " ").title()


def format_source_type(source_type: str) -> str:
    if source_type == "tabular":
        return "Tabular data"
    if source_type == "geospatial":
        return "Geospatial data"
    return source_type.replace("_", " ").title()


def format_local_path(path_value: str) -> str:
    project_root = Path(__file__).resolve().parent
    path = Path(path_value)

    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return path_value


def review_collection_node(state: UrbanWorkflowState) -> dict:
    print("\nCOLLECTED SOURCES")
    print("-" * 40)

    manifest_path = state.collection_report.get("manifest_path")
    if manifest_path:
        print(f"Manifest: {manifest_path}")
        print(f"Manifest entries: {state.collection_report.get('manifest_source_count', 0)}")
        print("-" * 40)

    for source in state.sources:
        meta = source.source_metadata
        print(f"ID: {source.source_id}")
        print(f"Name: {meta.source_name}")
        print(f"Collection mode: {format_acquisition_mode(meta.access_metadata.acquisition_mode)}")
        print(f"Data kind: {format_source_type(meta.source_type)}")
        print(f"File type: {meta.file_format}")
        print(f"Rows: {meta.row_count}")
        print(f"Columns: {meta.column_count}")

        year_hint = meta.compatibility_hints.inferred_reference_year
        if year_hint is not None:
            print(f"Likely reference year: {year_hint}")
        else:
            print("Likely reference year: not identified during collection")

        if meta.compatibility_hints.candidate_spatial_unit_columns:
            spatial_units = ", ".join(meta.compatibility_hints.candidate_spatial_unit_columns)
            print(f"Possible area or location fields: {spatial_units}")

        if meta.compatibility_hints.candidate_join_columns:
            join_candidates = ", ".join(meta.compatibility_hints.candidate_join_columns)
            print(f"Possible fields for later linking: {join_candidates}")

        if meta.geospatial_metadata is not None:
            print(f"Map layer used: {meta.geospatial_metadata.selected_layer}")
            print(f"Available map layers in file: {len(meta.geospatial_metadata.available_layers)}")
            if meta.crs is not None:
                print(f"Coordinate reference system: {meta.crs}")

        if meta.access_metadata.origin_url is not None:
            print(f"Source URL: {meta.access_metadata.origin_url}")

        if meta.access_metadata.cache_path is not None:
            print(f"Saved local copy: {format_local_path(meta.access_metadata.cache_path)}")

        if meta.access_metadata.used_cached_copy:
            print("Collection status: reused an existing local copy")

        if meta.transparency.warnings:
            print("Review notes:")
            for warning in meta.transparency.warnings:
                print(f"  - {warning}")

        print("-" * 40)

    skipped_items = state.collection_report.get("skipped_items", [])
    if skipped_items:
        print("\nSKIPPED ITEMS")
        print("-" * 40)
        for skipped_item in skipped_items:
            print(
                f"{skipped_item['item_origin']} | {skipped_item['item_label']}: {skipped_item['reason']}"
            )

    collection_warnings = state.collection_report.get("warnings", [])
    if collection_warnings:
        print("\nCOLLECTION WARNINGS")
        print("-" * 40)
        for warning in collection_warnings:
            print(f"- {warning}")

    approved = ask_to_continue(
        "Continue with harmonisation, profiling, compatibility check, and indicators?"
    )

    return {
        "human_review": HumanReviewState(
            after_collection=approved,
            before_interpretation=state.human_review.before_interpretation,
        )
    }


def route_after_collection(
    state: UrbanWorkflowState,
) -> Literal["process_data", "end"]:
    if state.human_review.after_collection:
        return "process_data"

    print("Workflow stopped after source collection.")
    return "end"


def process_data_node(state: UrbanWorkflowState) -> dict:
    harmonised_sources = [harmonise_source(source) for source in state.sources]
    profiles = build_source_profiles(harmonised_sources)
    profile_path = save_source_profiles(profiles)

    compatibility_report = build_compatibility_report(harmonised_sources)
    compatibility_path = save_compatibility_report(compatibility_report)

    indicator_results, indicator_report = build_indicators(harmonised_sources)
    indicator_report_path = save_indicator_report(indicator_report)

    print("\nWORKFLOW OUTPUTS")
    print("-" * 40)
    print(f"Saved source profiles to: {profile_path}")
    print(f"Saved compatibility report to: {compatibility_path}")
    print(f"Saved indicator selection report to: {indicator_report_path}")

    print("\nCOMPATIBILITY SUMMARY")
    print("-" * 40)
    print(f"Direct merge possible: {compatibility_report['direct_merge_possible']}")
    print(f"Same year: {compatibility_report['same_year']}")
    print(f"Suggested next step: {compatibility_report['suggested_next_step']}")

    print("\nINDICATOR SELECTION SUMMARY")
    print("-" * 40)
    for source_report in indicator_report.sources:
        print(f"\nSource: {source_report.source_id}")

        selected = [
            entry for entry in source_report.selected_indicators
            if entry.status == "selected"
        ]
        if selected:
            for entry in selected:
                output_names = ", ".join(entry.output_names)
                print(f"Selected: {entry.indicator_name}")
                print(f"Reason: {entry.applicability_reason}")
                print(f"Outputs: {output_names}")
        else:
            print("Selected: none")

        if source_report.skipped_indicators:
            skipped_names = ", ".join(
                entry.indicator_name for entry in source_report.skipped_indicators
            )
            print(f"Skipped templates: {skipped_names}")

    print("\nINDICATOR RESULTS")
    print("-" * 40)

    for source_id, indicators in indicator_results.items():
        print(f"\nSource: {source_id}")
        for indicator_name, table in indicators.items():
            print(f"\nIndicator: {indicator_name}")
            print(table.head().to_string(index=False))
            print("-" * 40)

    return {
        "harmonised_sources": harmonised_sources,
        "profiles": profiles,
        "compatibility_report": compatibility_report,
        "indicator_results": indicator_results,
        "indicator_report": indicator_report.model_dump(mode="json"),
    }


def review_interpretation_node(state: UrbanWorkflowState) -> dict:
    approved = ask_to_continue("Continue with interpretation summary?")

    return {
        "human_review": HumanReviewState(
            after_collection=state.human_review.after_collection,
            before_interpretation=approved,
        )
    }


def route_before_interpretation(
    state: UrbanWorkflowState,
) -> Literal["interpret", "end"]:
    if state.human_review.before_interpretation:
        return "interpret"

    print("Workflow stopped before interpretation.")
    return "end"


def interpret_node(state: UrbanWorkflowState) -> dict:
    interpretation_context = build_interpretation_context(
        profiles=state.profiles,
        compatibility_report=state.compatibility_report,
        indicator_results=state.indicator_results,
        indicator_report=state.indicator_report,
    )
    context_path = save_interpretation_context(interpretation_context)
    interpretation_draft = generate_interpretation_draft(interpretation_context)
    draft_path = save_interpretation_draft(interpretation_draft)
    interpretation_summary = render_interpretation_draft(interpretation_draft)

    interpretation_path = save_interpretation_summary(interpretation_summary)

    print(f"\nSaved interpretation context to: {context_path}")
    print(f"Saved interpretation draft to: {draft_path}")
    print(f"\nSaved interpretation summary to: {interpretation_path}")

    return {
        "interpretation_draft": interpretation_draft,
        "interpretation_summary": interpretation_summary,
    }


def build_workflow():
    builder = StateGraph(UrbanWorkflowState)

    builder.add_node("collect_sources", collect_sources_node)
    builder.add_node("review_collection", review_collection_node)
    builder.add_node("process_data", process_data_node)
    builder.add_node("review_interpretation", review_interpretation_node)
    builder.add_node("interpret", interpret_node)

    builder.add_edge(START, "collect_sources")
    builder.add_edge("collect_sources", "review_collection")

    builder.add_conditional_edges(
        "review_collection",
        route_after_collection,
        {
            "process_data": "process_data",
            "end": END,
        },
    )

    builder.add_edge("process_data", "review_interpretation")

    builder.add_conditional_edges(
        "review_interpretation",
        route_before_interpretation,
        {
            "interpret": "interpret",
            "end": END,
        },
    )

    builder.add_edge("interpret", END)

    return builder.compile()


def main():
    graph = build_workflow()

    result = graph.invoke(UrbanWorkflowState())

    # LangGraph returns a dict, so convert back to your Pydantic state model if needed.
    final_state = UrbanWorkflowState(**result)
    return final_state


if __name__ == "__main__":
    main()
