import re

from src.schemas import SourceMetadata, CollectedSource

def clean_column_name(column_name: str) -> str:
    """
    Make column names easier to work with:
    - lowercase
    - strip leading/trailing spaces
    - replace spaces and special chars with underscores
    - collapse repeated underscores
    """
    cleaned = column_name.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip("_")
    return cleaned


def harmonise_source(source: CollectedSource) -> CollectedSource:
    """
    Apply very basic harmonization to one source:
    - copy the dataframe/geodataframe
    - clean column names
    - remove fully empty rows
    - update metadata
    """
    df = source.data.copy()

    # 1. Clean column names
    cleaned_columns = [clean_column_name(col) for col in df.columns]
    df.columns = cleaned_columns

    # 2. Remove fully empty rows
    df = df.dropna(how="all")

    # 3. Build updated metadata
    updated_metadata = source.source_metadata.model_copy(
        update={
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": df.columns.tolist(),
            "column_types": {column: str(dtype) for column, dtype in df.dtypes.items()},
        }
    )

    # 4. Return updated collected source
    harmonised_source = CollectedSource(
        source_id=source.source_id,
        source_metadata=updated_metadata,
        data=df,
    )

    return harmonised_source
