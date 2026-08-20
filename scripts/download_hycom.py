#!/usr/bin/env python3
"""Download HYCOM ESPC-D-V02 surface currents via OpenDAP archive.

NCSS day-range requests for v3z frequently stall; OpenDAP subsets are reliable.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.config import download_bbox, ensure_dirs, load_event, project_root  # noqa: E402
from lib.io_util import ensure_time_dim, normalize_lon_lat, save_dataset  # noqa: E402

U_OPENDAP = "https://tds.hycom.org/thredds/dodsC/ESPC-D-V02/u3z/{year}"
V_OPENDAP = "https://tds.hycom.org/thredds/dodsC/ESPC-D-V02/v3z/{year}"
TIME_ORIGIN = pd.Timestamp("2000-01-01T00:00:00")


def _hours_since_2000(ts: pd.Timestamp) -> float:
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return (ts - TIME_ORIGIN) / pd.Timedelta(hours=1)


def _open_component(url: str, varname: str) -> xr.DataArray:
    ds = xr.open_dataset(url, decode_times=False, drop_variables=["tau"])
    if varname not in ds:
        raise ValueError(f"{varname} missing in {url}; found {list(ds.data_vars)}")
    return ds[varname]


def _subset(
    da: xr.DataArray,
    bbox: tuple[float, float, float, float],
    t0: pd.Timestamp,
    t1: pd.Timestamp,
    step_hours: int,
) -> xr.DataArray:
    lon0, lon1, lat0, lat1 = bbox
    h0 = _hours_since_2000(t0)
    h1 = _hours_since_2000(t1)
    # depth surface
    if "depth" in da.dims:
        da = da.sel(depth=0, method="nearest")
    # lon/lat naming
    lon_name = "lon" if "lon" in da.dims else "longitude"
    lat_name = "lat" if "lat" in da.dims else "latitude"
    lat = da[lat_name]
    if float(lat[0]) > float(lat[-1]):
        lat_slice = slice(lat1, lat0)
    else:
        lat_slice = slice(lat0, lat1)
    da = da.sel(
        {
            "time": slice(h0, h1),
            lon_name: slice(lon0, lon1),
            lat_name: lat_slice,
        }
    )
    # Convert time coordinate to datetime
    times = TIME_ORIGIN + pd.to_timedelta(np.asarray(da["time"].values), unit="h")
    da = da.assign_coords(time=("time", times.to_numpy()))
    if step_hours > 1 and da.sizes.get("time", 0) > 0:
        keep = [i for i, t in enumerate(pd.to_datetime(da["time"].values)) if t.hour % step_hours == 0]
        if keep:
            da = da.isel(time=keep)
    return da


def run(event_path: Path | None = None, skip_existing: bool = True) -> Path:
    cfg = load_event(event_path)
    ensure_dirs(cfg)
    root = project_root()
    data_dir = root / cfg["paths"]["data_dir"] / "hycom"
    data_dir.mkdir(parents=True, exist_ok=True)
    out = data_dir / "hycom_current_subset.nc"
    if skip_existing and out.exists() and out.stat().st_size > 1000:
        print(f"[OK] HYCOM already present: {out}")
        return out

    start = pd.Timestamp(cfg["time_window"]["start"])
    end = pd.Timestamp(cfg["time_window"]["end"])
    bbox = download_bbox(cfg)
    step = int(cfg["datasets"]["hycom"].get("step_hours", 3))

    # Window may span years; here it is entirely 2025.
    years = sorted({start.year, end.year})
    u_parts = []
    v_parts = []
    for year in years:
        print(f"[INFO] OpenDAP HYCOM u3z/v3z {year}…")
        u = _open_component(U_OPENDAP.format(year=year), "water_u")
        v = _open_component(V_OPENDAP.format(year=year), "water_v")
        u_sub = _subset(u, bbox, start, end, step)
        v_sub = _subset(v, bbox, start, end, step)
        print(f"[INFO] loading u times={u_sub.sizes.get('time')} …")
        u_parts.append(u_sub.load())
        print(f"[INFO] loading v times={v_sub.sizes.get('time')} …")
        v_parts.append(v_sub.load())
        u.close()
        v.close()

    water_u = xr.concat(u_parts, dim="time").sortby("time")
    water_v = xr.concat(v_parts, dim="time").sortby("time")
    # Align in case of minor mismatches
    water_u, water_v = xr.align(water_u, water_v, join="inner")
    ds = xr.Dataset({"water_u": water_u, "water_v": water_v})
    ds["speed"] = np.hypot(ds["water_u"], ds["water_v"])
    ds = normalize_lon_lat(ds)
    ds = ensure_time_dim(ds)
    save_dataset(ds, out)
    print(f"[OK] Wrote {out} times={ds.sizes.get('time')}")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run(args.event, skip_existing=not args.force)


if __name__ == "__main__":
    main()
