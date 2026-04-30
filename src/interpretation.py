import json
import os
from pathlib import Path
from typing import Any, cast

import pandas as pd
from dotenv import load_dotenv

try:
    from langchain_groq import ChatGroq
except ImportError:  # pragma: no cover - optional runtime dependency
    ChatGroq = None  # type: ignore[assignment]

from src.schemas import (
    IndicatorHighlight,
    IndicatorSelectionEntry,
    IndicatorSelectionReport,
    InterpretationDraft,
    ProcessedSourceSummary,
)


PREFERRED_INDICATOR_ORDER = (
    "historical_population",
    "landuse_area_summary",
    "transport_mode_summary",
    "records_by_area",
    "records_by_type",
)


def build_model_ready_context(context: dict[str, Any]) -> dict[str, Any]:
    """
    Keep the LLM input smaller than the full saved context and focus it on the
    fields that matter for `InterpretationDraft`.
    """
    return {
        "purpose": context.get("purpose", ""),
        "processed_sources": context.get("processed_sources", []),
        "indicator_highlights": context.get("indicator_highlights", []),
        "compatibility_limits": context.get("compatibility_limits", []),
        "compatibility_rule_summaries": context.get("compatibility_rule_summaries", []),
        "integration_requirements": context.get("integration_requirements", []),
        "suggested_next_step": context.get("suggested_next_step", ""),
        "transparency_note": context.get("transparency_note", ""),
        "human_review_note": context.get("human_review_note", ""),
    }


def build_structured_prompt(model_context: dict[str, Any]) -> str:
    return f"""
You are assisting a transparent urban data workflow about urban densification.

Produce a bounded interpretation draft based only on the provided context.
Do not make up datasets, indicators, planning conclusions, policy recommendations, or causal claims.
Keep the interpretation exploratory, cautious, and suitable for human review.

Return only the fields required by `InterpretationDraft`:
- purpose
- processed_sources
- indicator_highlights
- compatibility_limits
- integration_requirements
- next_step
- human_review_note

Do not echo extra context keys such as:
- compatibility_rule_summaries
- transparency_note
- suggested_next_step

Important guidance:
- Use indicator highlights as interpretation support, not as proof.
- Carry compatibility limits into the draft instead of smoothing them away.
- Distinguish transparency from explainability:
  transparency = making assumptions, limitations, and selection logic visible
  explainability = making the interpretation understandable to a reviewer
- `next_step` should be informed by the context field `suggested_next_step`.
- The final draft should be concise and useful for a multidisciplinary audience.

Context:
{json.dumps(model_context, ensure_ascii=False, indent=2)}
"""


def build_json_retry_prompt(model_context: dict[str, Any]) -> str:
    return f"""
Return one JSON object only.
Do not use markdown.
Do not use code fences.
Do not include any explanatory text before or after the JSON.

The JSON object must contain exactly these top-level keys:
"purpose", "processed_sources", "indicator_highlights",
"compatibility_limits", "integration_requirements",
"next_step", "human_review_note"

Use only the information contained in the context below.
Do not invent new datasets, indicators, or planning conclusions.
Use the value from "suggested_next_step" to inform "next_step".
Do not include "suggested_next_step" itself in the output.

Context:
{json.dumps(model_context, ensure_ascii=False, indent=2)}
"""


def save_interpretation_summary(summary_text: str) -> Path:
    """
    Save the rendered interpretation summary as markdown.
    """
    output_path = Path("outputs/reports/interpretation_summary.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file_handle:
        file_handle.write(summary_text)

    return output_path


def save_interpretation_context(context: dict[str, Any]) -> Path:
    """
    Save the interpretation input context for later review and explanation.
    """
    output_path = Path("outputs/reports/interpretation_context.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file_handle:
        json.dump(context, file_handle, indent=2, ensure_ascii=False)

    return output_path


def save_interpretation_draft(draft: InterpretationDraft) -> Path:
    """
    Save the structured interpretation draft before markdown rendering.
    """
    output_path = Path("outputs/reports/interpretation_draft.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file_handle:
        json.dump(draft.model_dump(mode="json"), file_handle, indent=2, ensure_ascii=False)

    return output_path


def build_processed_source_summaries(profiles: list[dict]) -> list[ProcessedSourceSummary]:
    return [
        ProcessedSourceSummary(
            source_id=profile["source_id"],
            source_name=profile["source_name"],
            source_type=profile["source_type"],
            file_format=profile["file_format"],
            row_count=profile["row_count"],
            column_count=profile["column_count"],
        )
        for profile in profiles
    ]


def load_indicator_report(report_data: dict | None) -> IndicatorSelectionReport | None:
    if not report_data:
        return None

    try:
        return IndicatorSelectionReport.model_validate(report_data)
    except Exception:
        return None


def get_indicator_source_report(
    indicator_report: IndicatorSelectionReport | None,
    source_id: str,
):
    if indicator_report is None:
        return None

    for source_report in indicator_report.sources:
        if source_report.source_id == source_id:
            return source_report

    return None


def choose_indicator_entry(
    source_id: str,
    indicator_results: dict[str, dict[str, pd.DataFrame]],
    indicator_report: IndicatorSelectionReport | None,
) -> IndicatorSelectionEntry | None:
    source_indicators = indicator_results.get(source_id, {})
    if not source_indicators:
        return None

    source_report = get_indicator_source_report(indicator_report, source_id)
    if source_report is None:
        return None

    selected_entries = [
        entry
        for entry in source_report.selected_indicators
        if entry.status == "selected"
        and any(output_name in source_indicators for output_name in entry.output_names)
    ]

    for preferred_indicator_id in PREFERRED_INDICATOR_ORDER:
        for entry in selected_entries:
            if entry.indicator_id == preferred_indicator_id:
                return entry

    if selected_entries:
        return selected_entries[0]

    return None


def get_indicator_table(
    indicator_results: dict[str, dict[str, pd.DataFrame]],
    source_id: str,
    indicator_entry: IndicatorSelectionEntry | None,
) -> tuple[str, pd.DataFrame] | None:
    source_indicators = indicator_results.get(source_id)
    if not source_indicators:
        return None

    if indicator_entry is not None:
        for output_name in indicator_entry.output_names:
            table = source_indicators.get(output_name)
            if table is not None:
                return output_name, table

    for indicator_name, table in source_indicators.items():
        return indicator_name, table

    return None


def format_number(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)

    if isinstance(value, int):
        return f"{value:,}"

    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}"

    return str(value)


def format_label(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value)


def build_indicator_note(
    indicator_entry: IndicatorSelectionEntry | None,
    baseline_note: str,
) -> str:
    if indicator_entry is None:
        return baseline_note

    interpretability_note = indicator_entry.tradeoffs.get("interpretability")
    accuracy_note = indicator_entry.tradeoffs.get("accuracy")

    note_parts = [
        f"Why this indicator was selected: {indicator_entry.applicability_reason}",
        f"Interpretation caution: {baseline_note}",
    ]

    if interpretability_note:
        note_parts.append(f"Interpretability trade-off: {interpretability_note}")

    if accuracy_note:
        note_parts.append(f"Accuracy trade-off: {accuracy_note}")

    return " ".join(note_parts)


def build_indicator_highlight(
    source_name: str,
    indicator_name: str,
    table: pd.DataFrame,
    indicator_entry: IndicatorSelectionEntry | None,
) -> IndicatorHighlight | None:
    if table.empty:
        return None

    top_row = table.iloc[0]
    leading_label = format_label(top_row.iloc[0])

    if "trips" in table.columns and "percent_of_trips" in table.columns:
        headline = (
            f"Leading mobility category: {leading_label} "
            f"({format_number(top_row['trips'])} trips, {top_row['percent_of_trips']:.2f}%)."
        )
        baseline_note = (
            "This is a useful mobility signal, but coded modal categories still need human reading "
            "before they are translated into a planning-relevant claim."
        )

    elif "total_area_km2" in table.columns and "percent_of_total_area" in table.columns:
        headline = (
            f"Dominant mapped land-use class: {leading_label} "
            f"({top_row['total_area_km2']:.2f} km2, {top_row['percent_of_total_area']:.2f}% of mapped area)."
        )
        baseline_note = (
            "This summarises spatial distribution at a high level, but does not on its own explain why "
            "that pattern exists or whether it is desirable in densification terms."
        )

    elif "total_population" in table.columns and "percent_of_total_population" in table.columns:
        headline = (
            f"Largest aggregated population total appears in {leading_label} "
            f"({format_number(top_row['total_population'])}, "
            f"{top_row['percent_of_total_population']:.2f}% of the dataset total)."
        )
        baseline_note = (
            "This is an aggregate demographic signal and should not be read as a direct proxy for "
            "housing need, density pressure, or service adequacy without additional contextual evidence."
        )

    elif "records" in table.columns and "percent_of_records" in table.columns:
        headline = (
            f"Highest record concentration appears in {leading_label} "
            f"({format_number(top_row['records'])} records, "
            f"{top_row['percent_of_records']:.2f}% of observed records)."
        )
        baseline_note = (
            "This reflects how records are distributed within the source, not the underlying intensity, "
            "quality, or social importance of urban phenomena."
        )

    else:
        headline = f"Top row extracted from {indicator_name}: {leading_label}."
        baseline_note = (
            "A preliminary summary was extracted, but its meaning remains dependent on source-specific "
            "field definitions and human review."
        )

    return IndicatorHighlight(
        source_id="",
        source_name=source_name,
        indicator_name=indicator_name,
        headline=headline,
        interpretation_note=build_indicator_note(indicator_entry, baseline_note),
    )


def build_indicator_highlights(
    profiles: list[dict],
    indicator_results: dict[str, dict[str, pd.DataFrame]],
    indicator_report_data: dict | None,
) -> list[IndicatorHighlight]:
    indicator_report = load_indicator_report(indicator_report_data)
    highlights: list[IndicatorHighlight] = []

    for profile in profiles:
        source_id = profile["source_id"]
        indicator_entry = choose_indicator_entry(source_id, indicator_results, indicator_report)
        result = get_indicator_table(indicator_results, source_id, indicator_entry)
        if result is None:
            continue

        indicator_name, table = result
        highlight = build_indicator_highlight(
            source_name=profile["source_name"],
            indicator_name=indicator_name,
            table=table,
            indicator_entry=indicator_entry,
        )
        if highlight is None:
            continue

        highlight.source_id = source_id
        highlights.append(highlight)

    return highlights


def summarise_rule_evaluations(compatibility_report: dict) -> list[dict[str, str]]:
    summaries: list[dict[str, str]] = []

    for rule in compatibility_report.get("rule_evaluations", []):
        summaries.append(
            {
                "rule_name": rule.get("rule_name", "Unnamed rule"),
                "status": rule.get("status", "unknown"),
                "implication": rule.get("implication", ""),
            }
        )

    return summaries


def summarise_integration_paths(compatibility_report: dict) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []

    for path in compatibility_report.get("integration_paths", []):
        summaries.append(
            {
                "path_name": path.get("path_name", "Unnamed path"),
                "status": path.get("status", "unknown"),
                "description": path.get("description", ""),
                "tradeoffs": path.get("tradeoffs", {}),
            }
        )

    return summaries


def build_interpretation_context(
    profiles: list[dict],
    compatibility_report: dict,
    indicator_results: dict[str, dict[str, pd.DataFrame]],
    indicator_report: dict | None = None,
) -> dict[str, Any]:
    processed_sources = build_processed_source_summaries(profiles)
    indicator_highlights = build_indicator_highlights(
        profiles=profiles,
        indicator_results=indicator_results,
        indicator_report_data=indicator_report,
    )

    loaded_indicator_report = load_indicator_report(indicator_report)
    indicator_workflow_notes = []
    if loaded_indicator_report is not None:
        indicator_workflow_notes = loaded_indicator_report.workflow_notes

    return {
        "purpose": (
            "Provide an initial bounded interpretation of the processed datasets. "
            "The output must remain exploratory, reviewable, and explicit about uncertainty."
        ),
        "processed_sources": [item.model_dump() for item in processed_sources],
        "indicator_highlights": [item.model_dump() for item in indicator_highlights],
        "indicator_workflow_notes": indicator_workflow_notes,
        "compatibility_limits": compatibility_report.get("reasons", []),
        "compatibility_rule_summaries": summarise_rule_evaluations(compatibility_report),
        "integration_requirements": compatibility_report.get("requirements_for_integration", []),
        "integration_path_summaries": summarise_integration_paths(compatibility_report),
        "suggested_next_step": compatibility_report.get("suggested_next_step", ""),
        "transparency_note": (
            "Transparency means making visible how indicators were selected, what compatibility "
            "limits remain, and which integration paths were considered. Explainability means making "
            "the resulting interpretation understandable to a human reviewer."
        ),
        "human_review_note": (
            "Treat the interpretation as a starting point for expert review, "
            "not as a final conclusion or automated planning recommendation."
        ),
    }


def build_fallback_interpretation_draft(context: dict[str, Any], reason: str) -> InterpretationDraft:
    processed_sources = [
        ProcessedSourceSummary(**item)
        for item in context.get("processed_sources", [])
    ]
    indicator_highlights = [
        IndicatorHighlight(**item)
        for item in context.get("indicator_highlights", [])
    ]

    compatibility_limits = list(context.get("compatibility_limits", []))
    if reason:
        compatibility_limits = [
            f"Interpretation draft was generated with a deterministic local fallback because {reason}."
        ] + compatibility_limits

    integration_requirements = list(context.get("integration_requirements", []))
    if not integration_requirements:
        integration_requirements = [
            "Review source-level assumptions and compatibility conditions before making stronger cross-source claims."
        ]

    next_step = context.get("suggested_next_step", "")
    if not next_step:
        next_step = "Review the available indicators side by side before attempting deeper integration."

    return InterpretationDraft(
        purpose=context.get("purpose", ""),
        processed_sources=processed_sources,
        indicator_highlights=indicator_highlights,
        compatibility_limits=compatibility_limits,
        integration_requirements=integration_requirements,
        next_step=next_step,
        human_review_note=context.get(
            "human_review_note",
            "Treat the interpretation as a starting point for human review.",
        ),
    )


load_dotenv(".env", override=True)


def extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()

    for index, character in enumerate(text):
        if character != "{":
            continue

        try:
            parsed, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            return parsed

    raise ValueError("No valid JSON object could be extracted from the model response.")


def response_to_text(response: Any) -> str:
    content = getattr(response, "content", response)

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "".join(parts)

    return str(content)


def friendly_source_type(source_type: str) -> str:
    mapping = {
        "tabular": "tabular dataset",
        "geospatial": "geospatial dataset",
    }
    return mapping.get(source_type, source_type.replace("_", " "))


def friendly_file_format(file_format: str) -> str:
    mapping = {
        "csv": "CSV",
        "json": "JSON",
        "geopackage": "GeoPackage",
    }
    return mapping.get(file_format, file_format.upper())


def friendly_indicator_name(indicator_name: str) -> str:
    mapping = {
        "transport_mode_summary": "Transport mode summary",
        "landuse_area_summary": "Land-use area summary",
        "records_by_distrito": "Records by district",
        "records_by_desc_distrito": "Records by district",
        "records_by_tipo": "Records by type",
        "population_by_desc_distrito": "Population by district",
        "historical_population_total": "Historical population total",
    }
    return mapping.get(indicator_name, indicator_name.replace("_", " ").capitalize())


def friendly_compatibility_limit(limit: str) -> str:
    mapping = {
        "Collection-time warnings remain relevant for compatibility interpretation.": (
            "Some issues identified during data collection still matter for later comparison and interpretation."
        ),
        "No shared columns were found across all sources that would support a simple direct merge.": (
            "The datasets do not share one obvious field that would allow a simple all-in-one merge."
        ),
        "The sources do not provide a fully shared and explicit temporal reference.": (
            "The datasets do not all point to the same clearly defined time period, so time-based comparison remains uncertain."
        ),
    }
    return mapping.get(limit, limit)


def friendly_integration_requirement(requirement: str) -> str:
    mapping = {
        "Review source-specific warnings before treating any integration path as robust.": (
            "Check the warnings attached to individual datasets before treating any combined result as reliable."
        ),
        "Treat cross-source comparison as exploratory unless a shared time frame is confirmed.": (
            "Keep cross-dataset comparison exploratory until a shared time frame has been confirmed."
        ),
        "Use inferred spatial-unit or identifier fields instead of assuming a direct field-level join.": (
            "If the datasets are compared or linked, use reviewed area labels or identifiers rather than assuming a direct column match."
        ),
    }
    return mapping.get(requirement, requirement)


def split_interpretation_note(note: str) -> dict[str, str]:
    sections = {
        "selection_reason": "",
        "caution": "",
        "interpretability_tradeoff": "",
        "accuracy_tradeoff": "",
    }

    working_note = note.strip()

    tradeoff_prefixes = (
        ("interpretability_tradeoff", "Interpretability trade-off: "),
        ("accuracy_tradeoff", "Accuracy trade-off: "),
    )

    first_tradeoff_position = len(working_note)
    for _, prefix in tradeoff_prefixes:
        position = working_note.find(prefix)
        if position >= 0:
            first_tradeoff_position = min(first_tradeoff_position, position)

    core = working_note[:first_tradeoff_position].strip()
    tradeoff_text = working_note[first_tradeoff_position:].strip()

    for key, prefix in tradeoff_prefixes:
        if prefix not in tradeoff_text:
            continue

        after = tradeoff_text.split(prefix, 1)[1]
        next_positions = [
            after.find(next_prefix)
            for _, next_prefix in tradeoff_prefixes
            if next_prefix in after and next_prefix != prefix
        ]
        next_positions = [position for position in next_positions if position >= 0]

        if next_positions:
            cut_at = min(next_positions)
            sections[key] = after[:cut_at].strip()
        else:
            sections[key] = after.strip()

    selection_prefix = "Why this indicator was selected: "
    caution_prefix = "Interpretation caution: "

    if core.startswith(selection_prefix):
        selection_and_caution = core[len(selection_prefix):].strip()

        if caution_prefix in selection_and_caution:
            selection_reason, caution = selection_and_caution.split(caution_prefix, 1)
            sections["selection_reason"] = selection_reason.strip()
            sections["caution"] = caution.strip()
        else:
            sentence_end = selection_and_caution.find(". ")
            if sentence_end >= 0:
                sections["selection_reason"] = selection_and_caution[: sentence_end + 1].strip()
                sections["caution"] = selection_and_caution[sentence_end + 2 :].strip()
            else:
                sections["selection_reason"] = selection_and_caution.strip()
    else:
        sections["caution"] = core

    return sections


def build_at_a_glance_line(draft: InterpretationDraft) -> str:
    source_count = len(draft.processed_sources)
    tabular_count = sum(1 for source in draft.processed_sources if source.source_type == "tabular")
    geospatial_count = sum(
        1 for source in draft.processed_sources if source.source_type == "geospatial"
    )
    highlight_count = len(draft.indicator_highlights)

    return (
        f"This summary reviews {source_count} datasets: {tabular_count} tabular and "
        f"{geospatial_count} geospatial. It currently draws on {highlight_count} indicator-based findings."
    )


def generate_interpretation_draft(context: dict[str, Any]) -> InterpretationDraft:
    if ChatGroq is None:
        return build_fallback_interpretation_draft(
            context,
            reason="the optional 'langchain_groq' dependency is not installed",
        )

    if not os.getenv("GROQ_API_KEY"):
        return build_fallback_interpretation_draft(
            context,
            reason="no GROQ_API_KEY was available in the environment",
        )

    model_context = build_model_ready_context(context)
    model_name = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    try:
        llm = ChatGroq(
            model=model_name,
            temperature=0.0,
        )  # type: ignore[call-arg]

        structured_llm = llm.with_structured_output(InterpretationDraft)
        draft = structured_llm.invoke(build_structured_prompt(model_context))
        if isinstance(draft, dict):
            return InterpretationDraft(**draft)
        return cast(InterpretationDraft, draft)

    except Exception as structured_error:
        try:
            llm = ChatGroq(
                model=model_name,
                temperature=0.0,
            )  # type: ignore[call-arg]
            raw_response = llm.invoke(build_json_retry_prompt(model_context))
            raw_text = response_to_text(raw_response)
            parsed_payload = extract_json_object(raw_text)
            return InterpretationDraft(**parsed_payload)
        except Exception as json_error:
            error_reason = (
                "the LLM step was unavailable or failed after both the structured-output "
                f"and JSON-retry paths failed (structured: {structured_error}; json retry: {json_error})"
            )
            return build_fallback_interpretation_draft(
                context,
                reason=error_reason,
            )

    except BaseException as error:
        return build_fallback_interpretation_draft(
            context,
            reason=f"the LLM step was unavailable or failed ({error})",
        )


def render_interpretation_draft(draft: InterpretationDraft) -> str:
    """
    Convert a validated InterpretationDraft into markdown text.
    """
    lines: list[str] = []
    lines.append("# Interpretation Overview")
    lines.append("")

    lines.append("## What This Summary Does")
    lines.append(draft.purpose)
    lines.append("")

    lines.append("## At A Glance")
    lines.append(build_at_a_glance_line(draft))
    lines.append("")

    lines.append("## Sources Reviewed")
    for source in draft.processed_sources:
        lines.append(
            f"- **{source.source_name}**: {friendly_source_type(source.source_type)}, "
            f"{friendly_file_format(source.file_format)}, {format_number(source.row_count)} rows, "
            f"{format_number(source.column_count)} columns."
        )
    lines.append("")

    lines.append("## Key Readings From The Available Data")
    if draft.indicator_highlights:
        for highlight in draft.indicator_highlights:
            note_parts = split_interpretation_note(highlight.interpretation_note)
            lines.append(f"### {highlight.source_name}")
            lines.append(
                f"- **Main view used:** {friendly_indicator_name(highlight.indicator_name)}."
            )
            lines.append(f"- **What stands out:** {highlight.headline}")
            if note_parts["selection_reason"]:
                lines.append(f"- **Why this view was used:** {note_parts['selection_reason']}")
            if note_parts["caution"]:
                lines.append(f"- **Why this still needs care:** {note_parts['caution']}")
            if note_parts["interpretability_tradeoff"]:
                lines.append(
                    f"- **Readability trade-off:** {note_parts['interpretability_tradeoff']}"
                )
            if note_parts["accuracy_tradeoff"]:
                lines.append(
                    f"- **Accuracy trade-off:** {note_parts['accuracy_tradeoff']}"
                )
            lines.append("")
    else:
        lines.append("No indicator highlights were available for interpretation.")
        lines.append("")

    lines.append("## What The Workflow Cannot Claim Yet")
    fallback_notes = [
        item for item in draft.compatibility_limits
        if item.startswith("Interpretation draft was generated with a deterministic local fallback")
    ]
    interpretation_limits = [
        item for item in draft.compatibility_limits
        if item not in fallback_notes
    ]

    if interpretation_limits:
        for item in interpretation_limits:
            lines.append(f"- {friendly_compatibility_limit(item)}")
    else:
        lines.append("- No major compatibility limitations were reported.")
    lines.append("")

    lines.append("## What Would Help Next")
    if draft.integration_requirements:
        for item in draft.integration_requirements:
            lines.append(f"- {friendly_integration_requirement(item)}")
    else:
        lines.append("- No additional integration requirements were reported.")
    lines.append("")

    lines.append("## Suggested Next Step")
    lines.append(draft.next_step)
    lines.append("")

    if fallback_notes:
        lines.append("## System Note")
        for item in fallback_notes:
            lines.append(f"- {item}")
        lines.append("")

    lines.append("## Review Reminder")
    lines.append(draft.human_review_note)
    lines.append("")

    return "\n".join(lines)
