from pathlib import Path

from backend.workflow.ml_pipeline import run_pipeline
from backend.workflow.source_collection import collect_sources, save_collection_report


def ask_to_continue_or_inspect(message: str) -> str:
    while True:
        response = input(f"\n{message} [y]es / [n]o / [i]nspect details: ").strip().lower()

        if response in {"y", "yes"}:
            return "yes"
        if response in {"n", "no"}:
            return "no"
        if response in {"i", "inspect"}:
            return "inspect"

        print("Please enter 'y', 'n', or 'i'.")


def ask_yes_no(message: str) -> bool:
    while True:
        response = input(f"\n{message} [y]es / [n]o: ").strip().lower()
        if response in {"y", "yes"}:
            return True
        if response in {"n", "no"}:
            return False
        print("Please enter 'y' or 'n'.")


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


def print_section_title(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def format_count(value: int) -> str:
    return f"{value:,}"


def print_collection_summary(report_path: Path, collection_report: dict) -> None:
    print_section_title("Source Collection Completed")
    print(f"Report saved to: {report_path}")

    manifest_path = collection_report.get("manifest_path")
    if manifest_path:
        print(f"Source catalog: {manifest_path}")

    print("")
    print(f"Collected sources: {format_count(collection_report.get('source_count', 0))}")
    print(f"Skipped items: {format_count(len(collection_report.get('skipped_items', [])))}")
    print(f"Warnings: {format_count(len(collection_report.get('warnings', [])))}")
    print("")


def print_collection_overview(sources: list) -> None:
    print_section_title("Collected Source Overview")
    for source in sources:
        meta = source.source_metadata
        print(
            f"- {source.source_id} | {meta.source_name} | "
            f"{format_source_type(meta.source_type)} | "
            f"{format_count(meta.row_count)} rows | {format_count(meta.column_count)} columns"
        )
    print("")


def print_collection_details(collection_report: dict, sources: list) -> None:
    print_section_title("Collected Source Details")

    manifest_path = collection_report.get("manifest_path")
    if manifest_path:
        print(f"Source catalog: {manifest_path}")
        print(f"Catalog entries: {collection_report.get('manifest_source_count', 0)}")
        print("-" * 40)

    for source in sources:
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

    skipped_items = collection_report.get("skipped_items", [])
    if skipped_items:
        print_section_title("Skipped Items")
        for skipped_item in skipped_items:
            print(
                f"{skipped_item['item_origin']} | {skipped_item['item_label']}: {skipped_item['reason']}"
            )

    collection_warnings = collection_report.get("warnings", [])
    if collection_warnings:
        print_section_title("Collection Warnings")
        for warning in collection_warnings:
            print(f"- {warning}")


def main() -> None:
    print("Starting source collection...", flush=True)
    sources, collection_report = collect_sources()
    report_path = save_collection_report(collection_report)
    collection_report_dict = collection_report.model_dump(mode="json")

    print_collection_summary(report_path=report_path, collection_report=collection_report_dict)
    print_collection_overview(sources)

    while True:
        user_choice = ask_to_continue_or_inspect(
            "Continue with feature engineering, clustering, anomaly detection, and evaluation?"
        )
        if user_choice == "inspect":
            print_collection_details(
                collection_report=collection_report_dict,
                sources=sources,
            )
            if ask_yes_no(
                "Continue with feature engineering, clustering, anomaly detection, and evaluation?"
            ):
                break
            print("Workflow stopped after source collection.")
            return
        if user_choice == "no":
            print("Workflow stopped after source collection.")
            return
        break

    run_pipeline()


if __name__ == "__main__":
    main()
