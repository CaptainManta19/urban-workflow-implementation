from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


AcquisitionMode = Literal["local_file", "remote_file", "api"]
SourceType = Literal["tabular", "geospatial"]
SourceFormat = Literal["csv", "geopackage", "json"]


class SourceProvenance(BaseModel):
    filename: str
    relative_path: str
    absolute_path: str
    file_size_bytes: int
    modified_at: datetime
    sha256: str


class AccessMetadata(BaseModel):
    acquisition_mode: AcquisitionMode
    manifest_declared: bool = False
    origin_url: str | None = None
    request_url: str | None = None
    request_params: dict[str, str] = Field(default_factory=dict)
    content_type: str | None = None
    retrieved_at: datetime | None = None
    cache_path: str | None = None
    used_cached_copy: bool = False
    discovery_notes: list[str] = Field(default_factory=list)


class GeospatialMetadata(BaseModel):
    selected_layer: str | None = None
    available_layers: list[str] = Field(default_factory=list)
    geometry_column: str | None = None
    geometry_types: list[str] = Field(default_factory=list)


class CompatibilityHints(BaseModel):
    inferred_reference_year: int | None = None
    year_inference_basis: list[str] = Field(default_factory=list)
    candidate_join_columns: list[str] = Field(default_factory=list)
    candidate_spatial_unit_columns: list[str] = Field(default_factory=list)
    geometry_present: bool = False


class CollectionTransparency(BaseModel):
    loader_name: str
    decisions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SourceMetadata(BaseModel):
    source_name: str
    source_type: SourceType
    file_path: str
    file_format: SourceFormat
    row_count: int
    column_count: int
    columns: list[str]
    column_types: dict[str, str] = Field(default_factory=dict)
    crs: str | None = None
    collected_at: datetime
    access_metadata: AccessMetadata
    provenance: SourceProvenance
    geospatial_metadata: GeospatialMetadata | None = None
    compatibility_hints: CompatibilityHints = Field(default_factory=CompatibilityHints)
    transparency: CollectionTransparency


class CollectedSource(BaseModel):
    source_id: str
    source_metadata: SourceMetadata
    data: Any


class CollectedSourceSummary(BaseModel):
    source_id: str
    source_name: str
    source_type: SourceType
    file_format: SourceFormat
    acquisition_mode: AcquisitionMode
    row_count: int
    column_count: int
    inferred_reference_year: int | None = None
    selected_layer: str | None = None
    origin_url: str | None = None
    cache_path: str | None = None
    warning_count: int = 0


class SkippedCollectionItem(BaseModel):
    item_label: str
    item_origin: Literal["raw_scan", "manifest"]
    reason: str


class CollectionReport(BaseModel):
    status: Literal["completed", "warning"]
    collected_at: datetime
    raw_data_path: str
    manifest_path: str | None = None
    manifest_source_count: int = 0
    source_count: int
    sources: list[CollectedSourceSummary] = Field(default_factory=list)
    skipped_items: list[SkippedCollectionItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SourceSpecification(BaseModel):
    source_id: str
    acquisition_mode: AcquisitionMode
    source_type: SourceType
    file_format: SourceFormat
    source_name: str | None = None
    path: str | None = None
    url: str | None = None
    params: dict[str, str] = Field(default_factory=dict)
    expected_file_name: str | None = None
    enabled: bool = True
    description: str | None = None
    discovery_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_location(self) -> "SourceSpecification":
        if self.acquisition_mode == "local_file" and not self.path:
            raise ValueError("Local file specifications require a 'path'.")

        if self.acquisition_mode in {"remote_file", "api"} and not self.url:
            raise ValueError("Remote file and API specifications require a 'url'.")

        if self.file_format == "geopackage" and self.source_type != "geospatial":
            raise ValueError("GeoPackage specifications must be marked as geospatial.")

        if self.acquisition_mode == "api" and self.source_type != "tabular":
            raise ValueError("API collection is currently bounded to tabular sources.")

        if (
            self.file_format == "json"
            and self.source_type == "geospatial"
            and self.acquisition_mode == "api"
        ):
            raise ValueError(
                "Geospatial JSON collection is currently bounded to local or remote-file sources, not API calls."
            )

        return self


class SourceManifest(BaseModel):
    sources: list[SourceSpecification] = Field(default_factory=list)


class HumanReviewState(BaseModel):
    after_collection: bool = False
    before_interpretation: bool = False


class ProcessedSourceSummary(BaseModel):
    source_id: str
    source_name: str
    source_type: SourceType
    file_format: str
    row_count: int
    column_count: int


class IndicatorHighlight(BaseModel):
    source_id: str
    source_name: str
    indicator_name: str
    headline: str
    interpretation_note: str


class IndicatorSelectionEntry(BaseModel):
    indicator_id: str
    indicator_name: str
    status: Literal["selected", "skipped", "empty_result"]
    description: str
    applicability_reason: str
    output_names: list[str] = Field(default_factory=list)
    tradeoffs: dict[str, str] = Field(default_factory=dict)


class IndicatorSourceReport(BaseModel):
    source_id: str
    source_name: str
    source_type: SourceType
    selected_indicators: list[IndicatorSelectionEntry] = Field(default_factory=list)
    skipped_indicators: list[IndicatorSelectionEntry] = Field(default_factory=list)


class IndicatorSelectionReport(BaseModel):
    status: Literal["completed", "warning"]
    generated_at: datetime
    source_count: int
    sources: list[IndicatorSourceReport] = Field(default_factory=list)
    workflow_notes: list[str] = Field(default_factory=list)


class InterpretationDraft(BaseModel):
    purpose: str
    processed_sources: list[ProcessedSourceSummary] = Field(default_factory=list)
    indicator_highlights: list[IndicatorHighlight] = Field(default_factory=list)

    compatibility_limits: list[str] = Field(default_factory=list)
    integration_requirements: list[str] = Field(default_factory=list)

    next_step: str
    human_review_note: str


class UrbanWorkflowState(BaseModel):
    sources: list[CollectedSource] = Field(default_factory=list)
    collection_report: dict = Field(default_factory=dict)
    harmonised_sources: list[CollectedSource] = Field(default_factory=list)

    profiles: list[dict] = Field(default_factory=list)
    # `build_compatibility_report()` always returns a dict; keep this non-optional
    # so downstream nodes (e.g. interpretation) can safely type-check.
    compatibility_report: dict = Field(default_factory=dict)
    indicator_results: dict = Field(default_factory=dict)
    indicator_report: dict = Field(default_factory=dict)
    interpretation_draft: InterpretationDraft | None = None
    interpretation_summary: str | None = None

    human_review: HumanReviewState = Field(default_factory=HumanReviewState)
