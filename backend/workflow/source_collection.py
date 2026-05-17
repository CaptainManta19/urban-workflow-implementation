import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
from pydantic import ValidationError

from backend.schemas.collection import (
    AccessMetadata,
    CollectedSource,
    CollectedSourceSummary,
    CollectionReport,
    CollectionTransparency,
    CompatibilityHints,
    GeospatialMetadata,
    SkippedCollectionItem,
    SourceFormat,
    SourceMetadata,
    SourceProvenance,
    SourceSpecification,
)


LOCAL_SUPPORTED_SUFFIXES = {".csv", ".gpkg"}
FORMAT_SUFFIXES: dict[SourceFormat, str] = {
    "csv": ".csv",
    "geopackage": ".gpkg",
    "json": ".json",
}
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
JOIN_KEYWORDS = (
    "id",
    "code",
    "name",
    "key",
    "district",
    "neigh",
    "barrio",
    "ward",
    "zone",
    "sector",
    "tract",
    "municip",
    "fua",
)
SPATIAL_UNIT_KEYWORDS = (
    "district",
    "neigh",
    "barrio",
    "ward",
    "zone",
    "sector",
    "tract",
    "municip",
    "fua",
    "grid",
    "cell",
)


@dataclass
class CollectionContext:
    source_id: str
    source_name: str
    file_format: SourceFormat
    source_type: str
    access_metadata: AccessMetadata
    transparency_decisions: list[str] = field(default_factory=list)
    transparency_assumptions: list[str] = field(default_factory=list)
    transparency_warnings: list[str] = field(default_factory=list)
    reference_texts: list[str] = field(default_factory=list)


def make_source_id(file_path: Path) -> str:
    source_id = file_path.stem.lower()
    source_id = re.sub(r"[^a-z0-9]+", "_", source_id)
    source_id = re.sub(r"_+", "_", source_id).strip("_")
    return source_id


def make_display_name(text: str) -> str:
    return text.replace("_", " ").replace("-", " ").strip().title()


def make_source_name(file_path: Path) -> str:
    return make_display_name(file_path.stem)


def to_project_relative(path: Path, project_root: Path) -> str:
    resolved_path = path.resolve()

    try:
        return str(resolved_path.relative_to(project_root.resolve()))
    except ValueError:
        return str(resolved_path)


def compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()

    with file_path.open("rb") as file_handle:
        while chunk := file_handle.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def build_provenance(file_path: Path, project_root: Path) -> SourceProvenance:
    stat_result = file_path.stat()

    return SourceProvenance(
        filename=file_path.name,
        relative_path=to_project_relative(file_path, project_root),
        absolute_path=str(file_path.resolve()),
        file_size_bytes=stat_result.st_size,
        modified_at=datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc),
        sha256=compute_sha256(file_path),
    )


def extract_year_candidates(values: list[str]) -> list[int]:
    candidates: list[int] = []

    for value in values:
        if not value:
            continue

        years = YEAR_PATTERN.findall(value)
        candidates.extend(int(year) for year in years)

    return sorted(set(candidates))


def infer_reference_year(reference_texts: list[str]) -> tuple[int | None, list[str], list[str]]:
    year_candidates = extract_year_candidates(reference_texts)

    if not year_candidates:
        return None, [], [
            "No reference year could be inferred during collection. Temporal alignment will need human review."
        ]

    if len(year_candidates) > 1:
        return None, [], [
            "Multiple year candidates were detected during collection. The source year remains unresolved."
        ]

    inferred_year = year_candidates[0]
    basis = [f"Inferred from collection metadata text: {inferred_year}"]
    return inferred_year, basis, []


def find_candidate_columns(columns: list[str], keywords: tuple[str, ...]) -> list[str]:
    return [
        column
        for column in columns
        if any(keyword in column.lower() for keyword in keywords)
    ]


def build_compatibility_hints(
    columns: list[str],
    source_type: str,
    reference_texts: list[str],
) -> tuple[CompatibilityHints, list[str]]:
    inferred_year, year_basis, warnings = infer_reference_year(reference_texts)

    candidate_join_columns = find_candidate_columns(columns, JOIN_KEYWORDS)
    candidate_spatial_unit_columns = find_candidate_columns(columns, SPATIAL_UNIT_KEYWORDS)

    hints = CompatibilityHints(
        inferred_reference_year=inferred_year,
        year_inference_basis=year_basis,
        candidate_join_columns=candidate_join_columns,
        candidate_spatial_unit_columns=candidate_spatial_unit_columns,
        geometry_present=source_type == "geospatial",
    )

    if source_type == "tabular" and not candidate_spatial_unit_columns:
        warnings.append(
            "No obvious spatial unit column was detected in the tabular source. Direct integration may require later aggregation or geographic referencing."
        )

    if not candidate_join_columns:
        warnings.append(
            "No obvious join key candidates were detected during collection. Compatibility assessment should treat linkage assumptions cautiously."
        )

    return hints, warnings


def build_source_summary(source: CollectedSource, project_root: Path) -> CollectedSourceSummary:
    meta = source.source_metadata

    return CollectedSourceSummary(
        source_id=source.source_id,
        source_name=meta.source_name,
        source_type=meta.source_type,
        file_format=meta.file_format,
        acquisition_mode=meta.access_metadata.acquisition_mode,
        row_count=meta.row_count,
        column_count=meta.column_count,
        inferred_reference_year=meta.compatibility_hints.inferred_reference_year,
        selected_layer=(
            meta.geospatial_metadata.selected_layer
            if meta.geospatial_metadata is not None
            else None
        ),
        origin_url=meta.access_metadata.origin_url,
        cache_path=(
            to_project_relative(Path(meta.access_metadata.cache_path), project_root)
            if meta.access_metadata.cache_path
            else None
        ),
        warning_count=len(meta.transparency.warnings),
    )


def build_cache_path(spec: SourceSpecification, project_root: Path) -> Path:
    fetched_dir = project_root / "data" / "fetched"
    fetched_dir.mkdir(parents=True, exist_ok=True)

    expected_name = spec.expected_file_name or f"{spec.source_id}{FORMAT_SUFFIXES[spec.file_format]}"
    filename = Path(expected_name).name
    suffix = FORMAT_SUFFIXES[spec.file_format]

    if not filename.endswith(suffix):
        filename = f"{filename}{suffix}"

    return fetched_dir / filename


def build_request_url(url: str, params: dict[str, str]) -> str:
    if not params:
        return url

    query_string = urlencode(params)
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{query_string}"


def fetch_remote_bytes(request_url: str) -> tuple[bytes, str | None]:
    request = Request(
        request_url,
        headers={"User-Agent": "UrbanWorkflowImplementation/0.1"},
    )

    with urlopen(request, timeout=60) as response:
        content_type = response.headers.get("Content-Type")
        payload = response.read()

    return payload, content_type


def fetch_remote_json(request_url: str) -> tuple[dict, str | None]:
    payload, content_type = fetch_remote_bytes(request_url)

    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Remote API response could not be decoded as JSON.") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Remote API response must decode to a JSON object.")

    return parsed, content_type


def is_ckan_records_payload(payload: dict) -> bool:
    result = payload.get("result")
    if not isinstance(result, dict):
        return False

    records = result.get("records")
    total = result.get("total")
    return isinstance(records, list) and isinstance(total, int)


def fetch_paginated_ckan_payload(
    url: str,
    params: dict[str, str],
) -> tuple[bytes, str | None, list[str]]:
    request_url = build_request_url(url, params)
    payload, content_type = fetch_remote_json(request_url)

    if not is_ckan_records_payload(payload):
        return json.dumps(payload, ensure_ascii=False).encode("utf-8"), content_type, []

    result = payload["result"]
    records = result["records"]
    total = result["total"]
    offset = int(result.get("offset", 0) or 0)
    first_page_count = len(records)
    page_limit = int(result.get("limit", 0) or 0)

    if total <= offset + first_page_count:
        return json.dumps(payload, ensure_ascii=False).encode("utf-8"), content_type, []

    if page_limit <= 0:
        page_limit = first_page_count if first_page_count > 0 else 100

    all_records = list(records)
    page_count = 1
    next_offset = offset + first_page_count

    while next_offset < total:
        page_params = dict(params)
        page_params["limit"] = str(page_limit)
        page_params["offset"] = str(next_offset)
        page_url = build_request_url(url, page_params)
        page_payload, _ = fetch_remote_json(page_url)

        if not is_ckan_records_payload(page_payload):
            raise ValueError(
                "Paginated API fetch expected CKAN-style 'result.records' and 'result.total' fields."
            )

        page_records = page_payload["result"]["records"]
        if not isinstance(page_records, list) or not page_records:
            break

        all_records.extend(page_records)
        next_offset += len(page_records)
        page_count += 1

    combined_payload = dict(payload)
    combined_result = dict(result)
    combined_result["records"] = all_records
    combined_result["offset"] = 0
    combined_result["limit"] = len(all_records)
    combined_payload["result"] = combined_result

    decisions = [
        f"Fetched {len(all_records)} records across {page_count} API pages from the CKAN datastore endpoint."
    ]
    return (
        json.dumps(combined_payload, ensure_ascii=False).encode("utf-8"),
        content_type,
        decisions,
    )


def resolve_manifest_local_path(spec: SourceSpecification, project_root: Path) -> Path:
    assert spec.path is not None

    candidate_path = Path(spec.path)
    if not candidate_path.is_absolute():
        candidate_path = project_root / candidate_path

    return candidate_path.resolve()


def load_source_catalog(
    project_root: Path,
) -> tuple[list[SourceSpecification], list[SkippedCollectionItem], Path | None, int]:
    manifest_path = project_root / "data" / "source_catalog.json"

    if not manifest_path.exists():
        return [], [], None, 0

    with manifest_path.open("r", encoding="utf-8") as file_handle:
        raw_manifest = json.load(file_handle)

    if not isinstance(raw_manifest, dict):
        raise ValueError("Source catalog must be a JSON object with a 'sources' list.")

    manifest_sources = raw_manifest.get("sources", [])
    if not isinstance(manifest_sources, list):
        raise ValueError("The source catalog 'sources' field must be a list.")

    skipped_items: list[SkippedCollectionItem] = []
    active_specs: list[SourceSpecification] = []

    for raw_spec in manifest_sources:
        try:
            spec = SourceSpecification.model_validate(raw_spec)
        except ValidationError as exc:
            item_label = (
                raw_spec.get("source_id", "<missing source_id>")
                if isinstance(raw_spec, dict)
                else "<invalid manifest entry>"
            )
            skipped_items.append(
                SkippedCollectionItem(
                    item_label=item_label,
                    item_origin="manifest",
                    reason=f"Manifest entry is invalid: {exc.errors()[0]['msg']}",
                )
            )
            continue

        if not spec.enabled:
            skipped_items.append(
                SkippedCollectionItem(
                    item_label=spec.source_id,
                    item_origin="manifest",
                    reason="Manifest entry is disabled.",
                )
            )
            continue

        active_specs.append(spec)

    return active_specs, skipped_items, manifest_path, len(manifest_sources)


def build_raw_scan_context(file_path: Path) -> CollectionContext:
    file_format: SourceFormat = "csv" if file_path.suffix.lower() == ".csv" else "geopackage"
    source_type = "tabular" if file_format == "csv" else "geospatial"

    return CollectionContext(
        source_id=make_source_id(file_path),
        source_name=make_source_name(file_path),
        file_format=file_format,
        source_type=source_type,
        access_metadata=AccessMetadata(
            acquisition_mode="local_file",
            manifest_declared=False,
        ),
        transparency_decisions=[
            "Automatically discovered this supported file by scanning data/raw."
        ],
        transparency_assumptions=[
            "Raw-folder scanning prioritises convenience for local prototype use and does not require a manifest declaration."
        ],
        reference_texts=[file_path.stem, make_source_name(file_path)],
    )


def build_manifest_context(
    spec: SourceSpecification,
    access_metadata: AccessMetadata,
    extra_decisions: list[str] | None = None,
    extra_assumptions: list[str] | None = None,
    extra_warnings: list[str] | None = None,
    extra_reference_texts: list[str] | None = None,
) -> CollectionContext:
    source_name = spec.source_name or make_display_name(spec.source_id)
    reference_texts = [source_name, spec.source_id]
    if spec.url:
        reference_texts.append(spec.url)
    reference_texts.extend(spec.params.values())
    reference_texts.extend(extra_reference_texts or [])

    return CollectionContext(
        source_id=spec.source_id,
        source_name=source_name,
        file_format=spec.file_format,
        source_type=spec.source_type,
        access_metadata=access_metadata,
        transparency_decisions=extra_decisions or [],
        transparency_assumptions=extra_assumptions or [],
        transparency_warnings=extra_warnings or [],
        reference_texts=reference_texts,
    )


def materialise_manifest_source(
    spec: SourceSpecification,
    project_root: Path,
    collected_at: datetime,
) -> tuple[Path, CollectionContext]:
    if spec.acquisition_mode == "local_file":
        file_path = resolve_manifest_local_path(spec, project_root)
        if not file_path.exists():
            raise FileNotFoundError(f"Manifest path does not exist: {file_path}")

        context = build_manifest_context(
            spec=spec,
            access_metadata=AccessMetadata(
                acquisition_mode="local_file",
                manifest_declared=True,
                discovery_notes=spec.discovery_notes,
            ),
            extra_decisions=["Loaded a manifest-declared local file source."],
            extra_assumptions=[
                "The manifest is treated as an explicit source-selection boundary for this workflow run."
            ],
            extra_reference_texts=[file_path.stem],
        )
        return file_path, context

    assert spec.url is not None
    cache_path = build_cache_path(spec, project_root)
    request_url = build_request_url(spec.url, spec.params)
    warnings: list[str] = []
    fetch_decisions: list[str] = []
    used_cached_copy = False
    content_type: str | None = None
    retrieved_at = collected_at

    try:
        if spec.acquisition_mode == "api" and spec.file_format == "json":
            payload, content_type, fetch_decisions = fetch_paginated_ckan_payload(
                spec.url,
                spec.params,
            )
        else:
            payload, content_type = fetch_remote_bytes(request_url)
        cache_path.write_bytes(payload)
        decision = (
            "Fetched the remote source during collection and stored a local cache copy for inspection and reproducibility."
        )
    except Exception as exc:
        if not cache_path.exists():
            raise RuntimeError(f"Remote fetch failed and no cached copy exists. {exc}") from exc

        used_cached_copy = True
        retrieved_at = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc)
        warnings.append(
            f"Remote fetch failed during this run ({exc}). Reused the existing cached copy instead."
        )
        decision = (
            "Used the existing cached copy because the remote source could not be fetched during this run."
        )

    access_metadata = AccessMetadata(
        acquisition_mode=spec.acquisition_mode,
        manifest_declared=True,
        origin_url=spec.url,
        request_url=request_url,
        request_params=spec.params,
        content_type=content_type,
        retrieved_at=retrieved_at,
        cache_path=str(cache_path.resolve()),
        used_cached_copy=used_cached_copy,
        discovery_notes=spec.discovery_notes,
    )

    assumptions = [
        "Remote collection is bounded to manifest-declared URLs and stores a local copy before downstream processing."
    ]
    if spec.acquisition_mode == "api":
        assumptions.append(
            "API collection is currently bounded to tabular CSV or JSON responses so that transformations remain inspectable."
        )

    context = build_manifest_context(
        spec=spec,
        access_metadata=access_metadata,
        extra_decisions=[decision] + fetch_decisions,
        extra_assumptions=assumptions,
        extra_warnings=warnings,
        extra_reference_texts=[cache_path.stem],
    )

    return cache_path, context


def normalise_json_payload(payload: object) -> tuple[pd.DataFrame, list[str]]:
    if isinstance(payload, list):
        if not all(isinstance(item, dict) for item in payload):
            raise ValueError("JSON list payloads must contain record-like objects.")

        return pd.json_normalize(payload), [
            "Parsed the JSON payload as a list of record objects."
        ]

    if isinstance(payload, dict):
        # CKAN Action API responses, including Madrid datastore_search, usually
        # wrap tabular rows inside result.records.
        result_value = payload.get("result")
        if isinstance(result_value, dict):
            records_value = result_value.get("records")
            if isinstance(records_value, list) and all(
                isinstance(item, dict) for item in records_value
            ):
                return pd.json_normalize(records_value), [
                    "Parsed the JSON payload from the CKAN Action API field 'result.records'."
                ]

            for candidate_key in ("results", "data", "items"):
                candidate_value = result_value.get(candidate_key)
                if isinstance(candidate_value, list) and all(
                    isinstance(item, dict) for item in candidate_value
                ):
                    return pd.json_normalize(candidate_value), [
                        f"Parsed the JSON payload from the nested field 'result.{candidate_key}'."
                    ]

        for candidate_key in ("results", "data", "items", "records"):
            candidate_value = payload.get(candidate_key)
            if isinstance(candidate_value, list) and all(
                isinstance(item, dict) for item in candidate_value
            ):
                return pd.json_normalize(candidate_value), [
                    f"Parsed the JSON payload from the '{candidate_key}' field."
                ]

        if isinstance(result_value, dict):
            return pd.json_normalize(result_value), [
                "Flattened the CKAN-style 'result' object into a single-row table because no tabular records field was found."
            ]

        return pd.json_normalize(payload), [
            "Flattened the top-level JSON object into a single-row table."
        ]

    raise ValueError("Unsupported JSON payload type for tabular collection.")


def read_csv_with_fallback(file_path: Path) -> tuple[pd.DataFrame, list[str], list[str]]:
    encodings_to_try = ["utf-8", "utf-8-sig", "iso-8859-1", "cp1252"]
    decode_errors: list[str] = []

    for encoding in encodings_to_try:
        try:
            dataframe = pd.read_csv(file_path, encoding=encoding, sep=None, engine="python")
            decisions = [f"Loaded the CSV using detected/fallback encoding '{encoding}'."]
            warnings: list[str] = []

            if encoding != "utf-8":
                warnings.append(
                    f"The CSV was not UTF-8 encoded. Collection used '{encoding}' as a fallback."
                )

            return dataframe, decisions, warnings
        except UnicodeDecodeError as exc:
            decode_errors.append(f"{encoding}: {exc}")

    raise UnicodeDecodeError(
        "csv",
        b"",
        0,
        1,
        "Unable to decode the CSV with the available fallback encodings. "
        + " | ".join(decode_errors),
    )


def collect_csv(
    file_path: Path,
    project_root: Path,
    collected_at: datetime,
    context: CollectionContext,
) -> CollectedSource:
    df, csv_decisions, csv_warnings = read_csv_with_fallback(file_path)
    columns = df.columns.tolist()  # pyright: ignore[reportAttributeAccessIssue]
    column_types = {column: str(dtype) for column, dtype in df.dtypes.items()}

    compatibility_hints, compatibility_warnings = build_compatibility_hints(
        columns=columns,
        source_type=context.source_type,
        reference_texts=context.reference_texts,
    )

    metadata = SourceMetadata(
        source_name=context.source_name,
        file_path=str(file_path.resolve()),
        file_format="csv",
        source_type="tabular",
        row_count=len(df),
        column_count=len(columns),
        columns=columns,
        column_types=column_types,
        crs=None,
        collected_at=collected_at,
        access_metadata=context.access_metadata,
        provenance=build_provenance(file_path, project_root),
        geospatial_metadata=None,
        compatibility_hints=compatibility_hints,
        transparency=CollectionTransparency(
            loader_name="pandas.read_csv",
            decisions=context.transparency_decisions
            + csv_decisions
            + ["Loaded the source as a CSV-backed tabular dataset."],
            assumptions=context.transparency_assumptions,
            warnings=context.transparency_warnings + csv_warnings + compatibility_warnings,
        ),
    )

    return CollectedSource(
        source_id=context.source_id,
        source_metadata=metadata,
        data=df,
    )


def collect_json_tabular(
    file_path: Path,
    project_root: Path,
    collected_at: datetime,
    context: CollectionContext,
) -> CollectedSource:
    with file_path.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)

    df, json_decisions = normalise_json_payload(payload)
    columns = df.columns.tolist()
    column_types = {column: str(dtype) for column, dtype in df.dtypes.items()}

    compatibility_hints, compatibility_warnings = build_compatibility_hints(
        columns=columns,
        source_type=context.source_type,
        reference_texts=context.reference_texts,
    )

    metadata = SourceMetadata(
        source_name=context.source_name,
        file_path=str(file_path.resolve()),
        file_format="json",
        source_type="tabular",
        row_count=len(df),
        column_count=len(columns),
        columns=columns,
        column_types=column_types,
        crs=None,
        collected_at=collected_at,
        access_metadata=context.access_metadata,
        provenance=build_provenance(file_path, project_root),
        geospatial_metadata=None,
        compatibility_hints=compatibility_hints,
        transparency=CollectionTransparency(
            loader_name="json.load + pandas.json_normalize",
            decisions=context.transparency_decisions
            + json_decisions
            + ["Loaded the source as a JSON-backed tabular dataset."],
            assumptions=context.transparency_assumptions,
            warnings=context.transparency_warnings + compatibility_warnings,
        ),
    )

    return CollectedSource(
        source_id=context.source_id,
        source_metadata=metadata,
        data=df,
    )


def collect_json_geospatial(
    file_path: Path,
    project_root: Path,
    collected_at: datetime,
    context: CollectionContext,
) -> CollectedSource:
    try:
        import geopandas as gpd
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Geospatial JSON collection requires 'geopandas' in the active environment."
        ) from exc

    gdf = gpd.read_file(file_path)
    columns = gdf.columns.tolist()
    column_types = {column: str(dtype) for column, dtype in gdf.dtypes.items()}
    geometry_types = sorted(
        {
            geometry_type
            for geometry_type in gdf.geometry.geom_type.dropna().unique().tolist()
        }
    )

    compatibility_hints, compatibility_warnings = build_compatibility_hints(
        columns=columns,
        source_type=context.source_type,
        reference_texts=context.reference_texts + [file_path.stem],
    )

    metadata = SourceMetadata(
        source_name=context.source_name,
        file_path=str(file_path.resolve()),
        file_format="json",
        source_type="geospatial",
        row_count=len(gdf),
        column_count=len(columns),
        columns=columns,
        column_types=column_types,
        crs=str(gdf.crs) if gdf.crs else None,
        collected_at=collected_at,
        access_metadata=context.access_metadata,
        provenance=build_provenance(file_path, project_root),
        geospatial_metadata=GeospatialMetadata(
            selected_layer=None,
            available_layers=[],
            geometry_column=str(gdf.geometry.name) if isinstance(gdf.geometry.name, str) else None,
            geometry_types=geometry_types,
        ),
        compatibility_hints=compatibility_hints,
        transparency=CollectionTransparency(
            loader_name="geopandas.read_file",
            decisions=context.transparency_decisions
            + [
                "Loaded the JSON source as a geospatial feature collection using geopandas.read_file."
            ],
            assumptions=context.transparency_assumptions
            + [
                "Geospatial JSON collection is currently bounded to feature-collection style files such as GeoJSON."
            ],
            warnings=context.transparency_warnings + compatibility_warnings,
        ),
    )

    return CollectedSource(
        source_id=context.source_id,
        source_metadata=metadata,
        data=gdf,
    )


def collect_gpkg(
    file_path: Path,
    project_root: Path,
    collected_at: datetime,
    context: CollectionContext,
) -> CollectedSource:
    try:
        import geopandas as gpd
        from pyogrio import list_layers
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "GeoPackage collection requires 'geopandas' and 'pyogrio' in the active environment."
        ) from exc

    layers = list_layers(file_path)
    available_layers = [layer[0] for layer in layers]

    if not available_layers:
        raise ValueError("GeoPackage does not contain any readable layers.")

    first_layer_name = available_layers[0]
    gdf = gpd.read_file(file_path, layer=first_layer_name)
    columns = gdf.columns.tolist()
    column_types = {column: str(dtype) for column, dtype in gdf.dtypes.items()}
    geometry_types = sorted(
        {
            geometry_type
            for geometry_type in gdf.geometry.geom_type.dropna().unique().tolist()
        }
    )

    compatibility_hints, compatibility_warnings = build_compatibility_hints(
        columns=columns,
        source_type=context.source_type,
        reference_texts=context.reference_texts + available_layers,
    )

    layer_decisions = [
        f"Loaded GeoPackage layer '{first_layer_name}' for this bounded prototype workflow."
    ]

    layer_warnings: list[str] = []
    if len(available_layers) > 1:
        layer_warnings.append(
            "Multiple GeoPackage layers were detected. Alternative layers remain available for later human-led inspection."
        )
        layer_decisions.append(
            "Selected the first listed layer to avoid silently mixing multiple spatial representations during collection."
        )
    else:
        layer_decisions.append("Loaded the only available GeoPackage layer.")

    metadata = SourceMetadata(
        source_name=context.source_name,
        file_path=str(file_path.resolve()),
        file_format="geopackage",
        source_type="geospatial",
        row_count=len(gdf),
        column_count=len(columns),
        columns=columns,
        column_types=column_types,
        crs=str(gdf.crs) if gdf.crs else None,
        collected_at=collected_at,
        access_metadata=context.access_metadata,
        provenance=build_provenance(file_path, project_root),
        geospatial_metadata=GeospatialMetadata(
            selected_layer=first_layer_name,
            available_layers=available_layers,
            geometry_column=str(gdf.geometry.name) if isinstance(gdf.geometry.name, str) else None,
            geometry_types=geometry_types,
        ),
        compatibility_hints=compatibility_hints,
        transparency=CollectionTransparency(
            loader_name="geopandas.read_file",
            decisions=context.transparency_decisions + layer_decisions,
            assumptions=context.transparency_assumptions
            + [
                "GeoPackage collection remains bounded to one selected layer per file to keep review and downstream processing inspectable."
            ],
            warnings=context.transparency_warnings
            + layer_warnings
            + compatibility_warnings,
        ),
    )

    return CollectedSource(
        source_id=context.source_id,
        source_metadata=metadata,
        data=gdf,
    )


def collect_source_from_path(
    file_path: Path,
    project_root: Path,
    collected_at: datetime,
    context: CollectionContext,
) -> CollectedSource:
    if context.file_format == "csv":
        return collect_csv(file_path, project_root, collected_at, context)

    if context.file_format == "json":
        if context.source_type == "geospatial":
            return collect_json_geospatial(file_path, project_root, collected_at, context)
        return collect_json_tabular(file_path, project_root, collected_at, context)

    if context.file_format == "geopackage":
        return collect_gpkg(file_path, project_root, collected_at, context)

    raise ValueError(f"Unsupported source format: {context.file_format}")


def build_collection_report(
    sources: list[CollectedSource],
    skipped_items: list[SkippedCollectionItem],
    collected_at: datetime,
    raw_data_path: Path,
    project_root: Path,
    manifest_path: Path | None,
    manifest_source_count: int,
) -> CollectionReport:
    warnings: list[str] = []

    if not sources:
        warnings.append("No supported sources were collected for this workflow run.")

    if skipped_items:
        warnings.append(
            "Some collection items were skipped or failed. Review the skipped item list before continuing."
        )

    status = "warning" if warnings else "completed"

    return CollectionReport(
        status=status,
        collected_at=collected_at,
        raw_data_path=str(raw_data_path),
        manifest_path=to_project_relative(manifest_path, project_root) if manifest_path else None,
        manifest_source_count=manifest_source_count,
        source_count=len(sources),
        sources=[build_source_summary(source, project_root) for source in sources],
        skipped_items=skipped_items,
        warnings=warnings,
    )


def save_collection_report(report: CollectionReport) -> Path:
    output_path = Path("outputs/collection/source_collection_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file_handle:
        json.dump(report.model_dump(mode="json"), file_handle, indent=2, ensure_ascii=False)

    return output_path


def collect_sources_from_project_root(project_root: Path) -> tuple[list[CollectedSource], CollectionReport]:
    raw_data_path = project_root / "data" / "raw"
    collected_at = datetime.now(timezone.utc)
    collected_sources: list[CollectedSource] = []
    skipped_items: list[SkippedCollectionItem] = []
    collected_source_ids: set[str] = set()
    collected_paths: set[str] = set()

    manifest_specs: list[SourceSpecification] = []
    manifest_path: Path | None = None
    manifest_source_count = 0

    if raw_data_path.exists():
        for file_path in sorted(raw_data_path.iterdir()):
            if not file_path.is_file():
                continue

            suffix = file_path.suffix.lower()
            if suffix not in LOCAL_SUPPORTED_SUFFIXES:
                skipped_items.append(
                    SkippedCollectionItem(
                        item_label=file_path.name,
                        item_origin="raw_scan",
                        reason=f"Unsupported file extension '{suffix}'.",
                    )
                )
                continue

            context = build_raw_scan_context(file_path)

            try:
                source = collect_source_from_path(file_path, project_root, collected_at, context)
                collected_sources.append(source)
                collected_source_ids.add(source.source_id)
                collected_paths.add(str(file_path.resolve()))
            except Exception as exc:
                skipped_items.append(
                    SkippedCollectionItem(
                        item_label=file_path.name,
                        item_origin="raw_scan",
                        reason=f"Collection failed: {exc}",
                    )
                )
    else:
        skipped_items.append(
            SkippedCollectionItem(
                item_label=str(raw_data_path),
                item_origin="raw_scan",
                reason="Raw data directory does not exist.",
            )
        )

    try:
        manifest_specs, manifest_skips, manifest_path, manifest_source_count = load_source_catalog(
            project_root
        )
        skipped_items.extend(manifest_skips)
    except Exception as exc:
        skipped_items.append(
            SkippedCollectionItem(
                item_label="data/source_catalog.json",
                item_origin="manifest",
                reason=f"Source catalog could not be loaded: {exc}",
            )
        )
        manifest_specs = []
        manifest_path = project_root / "data" / "source_catalog.json"

    for spec in manifest_specs:
        if spec.source_id in collected_source_ids:
            skipped_items.append(
                SkippedCollectionItem(
                    item_label=spec.source_id,
                    item_origin="manifest",
                    reason="Source id already exists in the current collection run.",
                )
            )
            continue

        try:
            file_path, context = materialise_manifest_source(spec, project_root, collected_at)

            if spec.acquisition_mode == "local_file" and str(file_path.resolve()) in collected_paths:
                skipped_items.append(
                    SkippedCollectionItem(
                        item_label=spec.source_id,
                        item_origin="manifest",
                        reason="Manifest local file duplicates a source already collected from data/raw.",
                    )
                )
                continue

            source = collect_source_from_path(file_path, project_root, collected_at, context)
            collected_sources.append(source)
            collected_source_ids.add(source.source_id)
            collected_paths.add(str(file_path.resolve()))
        except Exception as exc:
            skipped_items.append(
                SkippedCollectionItem(
                    item_label=spec.source_id,
                    item_origin="manifest",
                    reason=f"Collection failed: {exc}",
                )
            )

    report = build_collection_report(
        sources=collected_sources,
        skipped_items=skipped_items,
        collected_at=collected_at,
        raw_data_path=raw_data_path,
        project_root=project_root,
        manifest_path=manifest_path,
        manifest_source_count=manifest_source_count,
    )

    return collected_sources, report


def collect_sources() -> tuple[list[CollectedSource], CollectionReport]:
    project_root = Path(__file__).resolve().parents[2]
    return collect_sources_from_project_root(project_root)
