from pathlib import Path

from run_ml_pipeline import run_pipeline
from src.collection import collect_sources, save_collection_report


def ask_to_continue(message: str) -> bool:
    while True:
        response = input(f"{message} (y/n): ").strip().lower()

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


def review_collection_report(collection_report: dict, sources: list) -> None:
    print("\nCOLLECTED SOURCES")
    print("-" * 40)

    manifest_path = collection_report.get("manifest_path")
    if manifest_path:
        print(f"Manifest: {manifest_path}")
        print(f"Manifest entries: {collection_report.get('manifest_source_count', 0)}")
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
        print("\nSKIPPED ITEMS")
        print("-" * 40)
        for skipped_item in skipped_items:
            print(
                f"{skipped_item['item_origin']} | {skipped_item['item_label']}: {skipped_item['reason']}"
            )

    collection_warnings = collection_report.get("warnings", [])
    if collection_warnings:
        print("\nCOLLECTION WARNINGS")
        print("-" * 40)
        for warning in collection_warnings:
            print(f"- {warning}")


def main() -> None:
    sources, collection_report = collect_sources()
    report_path = save_collection_report(collection_report)
    print(f"\nSaved collection report to: {report_path}")

    review_collection_report(
        collection_report=collection_report.model_dump(mode="json"),
        sources=sources,
    )

    approved = ask_to_continue(
        "Continue with feature engineering, clustering, anomaly detection, and evaluation?"
    )
    if not approved:
        print("Workflow stopped after source collection.")
        return

    run_pipeline()


if __name__ == "__main__":
    main()
