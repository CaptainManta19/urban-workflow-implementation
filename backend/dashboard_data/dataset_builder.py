import ast
import json
import sqlite3
import struct
from pathlib import Path

import pandas as pd
from pyproj import Transformer

from backend.features.engineering import (
    GRID_GPKG_PATH,
    OUTPUT_DIR,
    build_feature_tables,
    load_district_geojson,
)


GRID_TRANSFORMER = Transformer.from_crs(3035, 4326, always_xy=True)
GRID_LAYER_NAME = "grid_250m_lu_height_transport_rent_emvs_district"
CLUSTER_PROFILES_PATH = OUTPUT_DIR / "cluster_profiles_kmeans.json"
DISTRICT_CLUSTER_MIX_PATH = OUTPUT_DIR / "district_cluster_mix_kmeans.csv"
DISTRICT_ANOMALY_EXPLANATIONS_PATH = OUTPUT_DIR / "district_anomaly_explanations_isolation_forest.json"


def geopackage_envelope_size(flags: int) -> int:
    envelope_code = (flags >> 1) & 0b111
    if envelope_code == 0:
        return 0
    if envelope_code == 1:
        return 32
    if envelope_code in (2, 3):
        return 48
    if envelope_code == 4:
        return 64
    raise ValueError(f"Unsupported GeoPackage envelope code: {envelope_code}")


def parse_wkb_polygon(data: bytes, offset: int) -> list[list[tuple[float, float]]]:
    endian_flag = data[offset]
    byte_order = "<" if endian_flag == 1 else ">"
    wkb_type = struct.unpack(f"{byte_order}I", data[offset + 1:offset + 5])[0]
    if wkb_type != 3:
        raise ValueError(f"Unsupported WKB geometry type: {wkb_type}")

    ring_count = struct.unpack(f"{byte_order}I", data[offset + 5:offset + 9])[0]
    cursor = offset + 9
    rings: list[list[tuple[float, float]]] = []
    for _ in range(ring_count):
        point_count = struct.unpack(f"{byte_order}I", data[cursor:cursor + 4])[0]
        cursor += 4
        ring: list[tuple[float, float]] = []
        for _ in range(point_count):
            x = struct.unpack(f"{byte_order}d", data[cursor:cursor + 8])[0]
            y = struct.unpack(f"{byte_order}d", data[cursor + 8:cursor + 16])[0]
            cursor += 16
            ring.append((x, y))
        rings.append(ring)
    return rings


def parse_geopackage_polygon(blob: bytes) -> list[list[list[float]]]:
    if blob[:2] != b"GP":
        raise ValueError("Unsupported geometry blob format")
    flags = blob[3]
    header_size = 8 + geopackage_envelope_size(flags)
    rings_projected = parse_wkb_polygon(blob, header_size)
    rings_lon_lat: list[list[list[float]]] = []
    for ring in rings_projected:
        transformed_ring = []
        for x, y in ring:
            lon, lat = GRID_TRANSFORMER.transform(x, y)
            transformed_ring.append([lon, lat])
        rings_lon_lat.append(transformed_ring)
    return rings_lon_lat


def load_grid_geojson(grid_frame: pd.DataFrame) -> dict:
    query = f"""
        SELECT
            cell_id,
            geom
        FROM {GRID_LAYER_NAME}
    """
    frame_by_cell_id = grid_frame.set_index("cell_id", drop=False)
    features = []
    with sqlite3.connect(GRID_GPKG_PATH) as connection:
        cursor = connection.cursor()
        for cell_id, geom_blob in cursor.execute(query):
            cell_id_str = str(cell_id)
            if cell_id_str not in frame_by_cell_id.index:
                continue
            row = frame_by_cell_id.loc[cell_id_str]
            polygon_coordinates = parse_geopackage_polygon(geom_blob)
            features.append(
                {
                    "type": "Feature",
                    "id": cell_id_str,
                    "properties": {
                        "cell_id": cell_id_str,
                        "district_name": row["district_name"],
                        "lu_2018_class_simplified": row["lu_2018_class_simplified"],
                        "height_mean": row["height_mean"],
                        "height_max": row["height_max"],
                        "pt_stop_count": int(row["pt_stop_count"]),
                        "pt_access_good": bool(row["pt_access_good"]),
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": polygon_coordinates,
                    },
                }
            )
    return {"type": "FeatureCollection", "features": features}


def build_grid_caches(frame: pd.DataFrame, geojson: dict) -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    frame_cache: dict[str, pd.DataFrame] = {}
    geojson_cache: dict[str, dict] = {}
    for district_name in sorted(frame["district_name"].dropna().unique()):
        district_frame = frame[frame["district_name"] == district_name].copy()
        frame_cache[district_name] = district_frame
        district_cell_ids = set(district_frame["cell_id"].tolist())
        geojson_cache[district_name] = {
            "type": "FeatureCollection",
            "features": [
                feature
                for feature in geojson["features"]
                if feature["properties"]["cell_id"] in district_cell_ids
            ],
        }
    return frame_cache, geojson_cache


def load_typology_artifacts() -> tuple[dict[str, dict], dict[str, dict]]:
    profile_lookup: dict[str, dict] = {}
    district_mix_lookup: dict[str, dict] = {}

    if Path(CLUSTER_PROFILES_PATH).exists():
        profile_rows = json.loads(Path(CLUSTER_PROFILES_PATH).read_text())
        profile_lookup = {
            str(row["cluster_label"]): row
            for row in profile_rows
        }

    if Path(DISTRICT_CLUSTER_MIX_PATH).exists():
        district_mix_frame = pd.read_csv(DISTRICT_CLUSTER_MIX_PATH)
        for row in district_mix_frame.to_dict(orient="records"):
            cluster_shares = row.get("cluster_shares", {})
            if isinstance(cluster_shares, str):
                cluster_shares = ast.literal_eval(cluster_shares)
            district_mix_lookup[str(row["district_name"])] = {
                "district_name": row["district_name"],
                "district_key": row["district_key"],
                "cluster_shares": {
                    str(key): float(value)
                    for key, value in dict(cluster_shares).items()
                },
                "dominant_cluster_label": row.get("dominant_cluster_label"),
            }

    return profile_lookup, district_mix_lookup


def load_anomaly_artifacts() -> dict[str, dict]:
    anomaly_lookup: dict[str, dict] = {}
    if not Path(DISTRICT_ANOMALY_EXPLANATIONS_PATH).exists():
        return anomaly_lookup

    anomaly_rows = json.loads(Path(DISTRICT_ANOMALY_EXPLANATIONS_PATH).read_text())
    for row in anomaly_rows:
        anomaly_lookup[str(row["district_name"])] = row
    return anomaly_lookup


def build_dashboard_datasets() -> dict:
    district_geojson = load_district_geojson()
    grid_features, district_features = build_feature_tables()
    grid_geojson = load_grid_geojson(grid_features)
    mobility_grid_frame = grid_features[grid_features["pt_stop_count"] > 0].copy()
    mobility_grid_geojson = {
        "type": "FeatureCollection",
        "features": [
            feature
            for feature in grid_geojson["features"]
            if feature["properties"]["pt_stop_count"] > 0
        ],
    }
    land_use_frame_cache, land_use_geojson_cache = build_grid_caches(grid_features, grid_geojson)
    mobility_frame_cache, mobility_geojson_cache = build_grid_caches(
        mobility_grid_frame,
        mobility_grid_geojson,
    )
    cluster_profile_lookup, district_typology_lookup = load_typology_artifacts()
    district_anomaly_lookup = load_anomaly_artifacts()
    return {
        "district_geojson": district_geojson,
        "grid_frame": grid_features,
        "district_frame": district_features,
        "grid_geojson": grid_geojson,
        "mobility_grid_frame": mobility_grid_frame,
        "mobility_grid_geojson": mobility_grid_geojson,
        "land_use_district_frame_cache": land_use_frame_cache,
        "land_use_district_geojson_cache": land_use_geojson_cache,
        "mobility_district_frame_cache": mobility_frame_cache,
        "mobility_district_geojson_cache": mobility_geojson_cache,
        "cluster_profile_lookup": cluster_profile_lookup,
        "district_typology_lookup": district_typology_lookup,
        "district_anomaly_lookup": district_anomaly_lookup,
    }
