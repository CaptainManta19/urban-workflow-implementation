import json
from pathlib import Path

from src.schemas import CollectedSource


def build_source_profile(source: CollectedSource) -> dict:
    """
    Build a JSON-friendly profile for one harmonised source.
    """
    df = source.data
    meta = source.source_metadata

    missing_values = df.isna().sum().to_dict()

    profile = {
        "source_id": source.source_id,
        "source_name": meta.source_name,
        "source_type": meta.source_type,
        "file_format": meta.file_format,
        "file_path": meta.file_path,
        "row_count": meta.row_count,
        "column_count": len(meta.columns),
        "columns": meta.columns,
        "crs": meta.crs,
        "collected_at": meta.collected_at.isoformat(),
        "missing_values": missing_values,
    }

    return profile


def build_source_profiles(sources: list[CollectedSource]) -> list[dict]:
    """
    Build profiles for all harmonised sources.
    """
    return [build_source_profile(source) for source in sources]


def save_source_profiles(profiles: list[dict]) -> Path:
    """
    Save all source profiles to outputs/reports/source_profiles.json
    """
    output_path = Path("outputs/reports/source_profiles.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)

    return output_path