#!/usr/bin/env python3
"""Extract point time series at the incident (and optional wreck) location."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.config import ensure_dirs, load_event, project_root  # noqa: E402
from lib.extract import extract_products_at_point  # noqa: E402


def _fields_from_gfs_wave(ds: xr.Dataset) -> dict:
    out = {}
    if "swh" in ds:
        out["swh"] = ds["swh"]
    if "swell" in ds:
        out["swell"] = ds["swell"]
    if "ugrdsfc" in ds and "vgrdsfc" in ds:
        out["wind_sfc_ms"] = np.hypot(ds["ugrdsfc"], ds["vgrdsfc"])
    return out


def _fields_from_gfs_atmos(ds: xr.Dataset) -> dict:
    if "u10" in ds and "v10" in ds:
        return {"wind10m_ms": np.hypot(ds["u10"], ds["v10"])}
    return {}


def _fields_from_current(ds: xr.Dataset) -> dict:
    out = {}
    if "speed" in ds:
        out["seacurrent_ms"] = ds["speed"]
    elif "water_u" in ds and "water_v" in ds:
        out["seacurrent_ms"] = np.hypot(ds["water_u"], ds["water_v"])
    return out


def _fields_from_era5(ds: xr.Dataset) -> dict:
    out = {}
    if "swh" in ds:
        out["swh"] = ds["swh"]
    if "swell" in ds:
        out["swell"] = ds["swell"]
    if "u10" in ds and "v10" in ds:
        out["wind10m_ms"] = np.hypot(ds["u10"], ds["v10"])
    return out


LOADERS = {
    ("gfs", "gfs_wave_subset.nc", "wave"): _fields_from_gfs_wave,
    ("gfs", "gfs_atmos_wind_subset.nc", "atmos"): _fields_from_gfs_atmos,
    ("hycom", "hycom_current_subset.nc", "current"): _fields_from_current,
    ("era5", "era5_subset.nc", "era5"): _fields_from_era5,
    ("cmems", "cmems_current_subset.nc", "current"): _fields_from_current,
}


def run(event_path: Path | None = None) -> list[Path]:
    cfg = load_event(event_path)
    ensure_dirs(cfg)
    root = project_root()
    point_dir = root / cfg["paths"]["point_dir"]
    written = []

    sites = [("incident", cfg["event"]["incident"])]
    if cfg["event"].get("wreck"):
        sites.append(("wreck", cfg["event"]["wreck"]))

    for (source, fname, tag), loader in LOADERS.items():
        path = root / cfg["paths"]["data_dir"] / source / fname
        if not path.exists():
            print(f"[SKIP] {path}")
            continue
        ds = xr.open_dataset(path)
        fields = loader(ds)
        if not fields:
            print(f"[SKIP] no fields in {path}")
            ds.close()
            continue
        for site_key, site in sites:
            df = extract_products_at_point(
                fields,
                lon=float(site["lon"]),
                lat=float(site["lat"]),
                label=site.get("label", site_key),
            )
            df["source"] = source
            out = point_dir / f"{source}_{tag}_{site_key}_timeseries.csv"
            df.to_csv(out, index=False)
            written.append(out)
            print(f"[OK] {out} rows={len(df)}")
        ds.close()

    # Combined primary CSV for convenience
    frames = []
    for p in written:
        if "_incident_" in p.name and (
            p.name.startswith("gfs_") or p.name.startswith("hycom_")
        ):
            frames.append(pd.read_csv(p, parse_dates=["time"]))
    if frames:
        combo = pd.concat(frames, ignore_index=True)
        combo_path = point_dir / "primary_incident_timeseries.csv"
        combo.to_csv(combo_path, index=False)
        written.append(combo_path)
        print(f"[OK] {combo_path}")
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, default=None)
    args = parser.parse_args()
    run(args.event)


if __name__ == "__main__":
    main()
