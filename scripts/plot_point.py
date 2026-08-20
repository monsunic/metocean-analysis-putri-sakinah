#!/usr/bin/env python3
"""Point time-series plots (±3 days) for sea state, wind, and current."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.config import ensure_dirs, load_event, project_root  # noqa: E402


VAR_PANELS = [
    ("swh", "Significant wave height (m)", "swh"),
    ("swell", "Primary swell (m)", "swell"),
    ("wind10m_ms", "10 m wind (m/s)", "wind"),
    ("wind_sfc_ms", "Wave-model surface wind (m/s)", "wind"),
    ("seacurrent_ms", "Surface current (m/s)", "current"),
]


def _load_primary(point_dir: Path) -> pd.DataFrame:
    combo = point_dir / "primary_incident_timeseries.csv"
    if combo.exists():
        return pd.read_csv(combo, parse_dates=["time"])
    frames = []
    for p in sorted(point_dir.glob("*_incident_timeseries.csv")):
        frames.append(pd.read_csv(p, parse_dates=["time"]))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def run(event_path: Path | None = None) -> Path | None:
    cfg = load_event(event_path)
    ensure_dirs(cfg)
    root = project_root()
    point_dir = root / cfg["paths"]["point_dir"]
    df = _load_primary(point_dir)
    if df.empty:
        print("[SKIP] no point CSV — run extract_point.py first")
        return None

    event_time = pd.Timestamp(cfg["event"]["time_utc"])
    if event_time.tzinfo is not None:
        event_time = event_time.tz_convert("UTC").tz_localize(None)
    swh_lo, swh_hi = cfg["event"].get("reported_swh_m", [2.0, 3.0])

    present = []
    for var, title, _group in VAR_PANELS:
        sub = df[df["variable"] == var]
        if not sub.empty:
            present.append((var, title, sub))

    if not present:
        print("[SKIP] no recognized variables in point CSV")
        return None

    n = len(present)
    fig, axes = plt.subplots(n, 1, figsize=(11, 2.4 * n), sharex=True, constrained_layout=True)
    if n == 1:
        axes = [axes]

    for ax, (var, title, sub) in zip(axes, present):
        for source, g in sub.groupby("source"):
            g = g.sort_values("time")
            ax.plot(g["time"], g["value"], label=source, linewidth=1.6)
        ax.axvline(event_time, color="#DC2626", linestyle="--", linewidth=1.2, label="Event ~12:30Z")
        if var in ("swh", "swell"):
            ax.axhspan(swh_lo, swh_hi, color="#F59E0B", alpha=0.15, label="Reported 2–3 m")
        ax.set_ylabel(title, fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", fontsize=7, ncol=2)

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %HZ"))
    axes[-1].set_xlabel("UTC")
    fig.suptitle(
        f"{cfg['event']['name']} — point series @ "
        f"{cfg['event']['incident']['lon']:.2f}E, {cfg['event']['incident']['lat']:.2f}N\n"
        f"{cfg['domain']['region_label']}",
        fontsize=11,
        fontfamily="monospace",
    )

    out = point_dir / f"primary_incident_timeseries.{cfg['plot']['fileformat']}"
    fig.savefig(out, dpi=int(cfg["plot"]["dpi"]), facecolor="white")
    plt.close(fig)
    print(f"[OK] {out}")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, default=None)
    args = parser.parse_args()
    run(args.event)


if __name__ == "__main__":
    main()
