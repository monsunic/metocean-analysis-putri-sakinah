# Analisis metocean KM Putri Sakinah (Labuan Bajo / Selat Padar)

Konten analisis tenggelamnya KM Putri Sakinah (26 Des 2025 ~20:30 WITA / 12:30 UTC) di Selat Padar.

Sumber berita: [ANTARA](https://www.antaranews.com/berita/5351357/tragedi-km-putri-sakinah-gerak-cepat-polda-ntt-penanganan-tuntas-dan-transparan)

## Yang diplot

| Mode | Isi |
|------|-----|
| **Spasial** | SWH, primary swell, angin 10 m, arus permukaan — domain 2°×2° sekitar kejadian |
| **Titik** | Time series di estimasi lokasi tenggelam, **±3 hari**, timestep native sumber |

Densifikasi display default **0.01° (~1.1 km)** — interpolasi + Gaussian ringan di atas grid native (GFS 0.25°). Ini **bukan** resolusi fisik baru.

## Dataset

| Variabel | Primary | Optional |
|----------|---------|----------|
| SWH, swell | GFS Wave (AWS archive, 3 h) | ERA5 (CDS, 1 h) |
| Angin 10 m | GFS Atmos (AWS, 3 h) | ERA5 |
| Arus permukaan | HYCOM ESPC archive (3 h) | Marine Copernicus |

Konfigurasi: [`event.yaml`](event.yaml)

## Setup

```bash
cd blog/01-putri-sakinah
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt
```

Opsional: `~/.cdsapirc` + `cdsapi` untuk ERA5; `copernicusmarine login` untuk CMEMS.

## Pipeline

```bash
# 1) Unduh primary (±3 hari)
python scripts/download_gfs.py
python scripts/download_hycom.py

# Opsional
python scripts/download_era5.py
python scripts/download_cmems.py

# 2) Densifikasi spasial + ekstrak titik
python scripts/refine_field.py
python scripts/extract_point.py

# 3) Plot (pakai --every 4 untuk draft cepat)
python scripts/plot_spatial.py
python scripts/plot_point.py
```

Notebook: [`notebooks/analyze_putri_sakinah.ipynb`](notebooks/analyze_putri_sakinah.ipynb)

Output:

- `figures/spatial/{gfs,hycom}/…`
- `figures/point/…`

## Catatan metodologi

- GFS Wave/Atmos historis dari `noaa-gfs-bdp-pds` (NOMADS terlalu pendek untuk Des 2025).
- HYCOM memakai archive NCSS `ESPC-D-V02/{u,v}3z/2025` (maks. 1 hari per request).
- Marker peta: estimasi titik tenggelam + lokasi bangkai (6 Jan 2026).
- Upsampling hanya untuk readability peta; sinyal asli tetap skala model.
