from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, PngImagePlugin

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None


SEED = 42

# Bounding box (Los Angeles area)
# North-West: 34.3373 N, 118.6682 W
# South-East: 33.6996 N, 118.1553 W
LAT_MIN = 33.6996
LAT_MAX = 34.3373
LON_MIN = -118.6682
LON_MAX = -118.1553

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate clustered fake coordinates for mini-imagenet-test images."
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=Path("data/mini-imagenet-test"),
        help="Directory containing images to process.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("data/mini-imagenet-test-coordinates.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--num-clusters",
        type=int,
        default=50,
        help="Approximate number of cluster centers to simulate.",
    )
    parser.add_argument(
        "--min-run",
        type=int,
        default=4,
        help="Minimum consecutive images sharing same cluster.",
    )
    parser.add_argument(
        "--max-run",
        type=int,
        default=12,
        help="Maximum consecutive images sharing same cluster.",
    )
    parser.add_argument(
        "--spread-meters",
        type=float,
        default=6.0,
        help="Typical cluster spread in meters (smaller = tighter).",
    )
    parser.add_argument(
        "--write-png-metadata",
        action="store_true",
        help="Write standard EXIF GPS metadata into each PNG file.",
    )
    return parser.parse_args()


def list_images(image_dir: Path) -> list[Path]:
    images = [
        p
        for p in image_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]
    images.sort()
    return images


def meter_to_degree_lat(meters: float) -> float:
    return meters / 111_320.0


def meter_to_degree_lon(meters: float, latitude_deg: float) -> float:
    cos_lat = math.cos(math.radians(latitude_deg))
    cos_lat = max(cos_lat, 1e-8)
    return meters / (111_320.0 * cos_lat)


def make_cluster_centers(rng: np.random.Generator, num_clusters: int) -> np.ndarray:
    lat_centers = rng.uniform(LAT_MIN, LAT_MAX, size=num_clusters)
    lon_centers = rng.uniform(LON_MIN, LON_MAX, size=num_clusters)
    return np.column_stack([lat_centers, lon_centers])


def make_cluster_assignments(
    n_items: int,
    num_clusters: int,
    min_run: int,
    max_run: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if min_run <= 0 or max_run < min_run:
        raise ValueError("min_run and max_run are invalid.")

    assignments: list[int] = []
    cluster_cycle = rng.permutation(num_clusters).tolist()
    cycle_idx = 0

    while len(assignments) < n_items:
        if cycle_idx >= len(cluster_cycle):
            cluster_cycle = rng.permutation(num_clusters).tolist()
            cycle_idx = 0

        cluster_id = cluster_cycle[cycle_idx]
        cycle_idx += 1
        run_length = int(rng.integers(min_run, max_run + 1))
        assignments.extend([cluster_id] * run_length)

    return np.array(assignments[:n_items], dtype=np.int32)


def iter_with_progress(items: list[Path], desc: str) -> Iterable[tuple[int, Path]]:
    if tqdm is not None:
        yield from enumerate(tqdm(items, desc=desc, unit="img"))
        return

    total = len(items)
    checkpoint = max(total // 20, 1)
    for idx, item in enumerate(items):
        if idx % checkpoint == 0 or idx == total - 1:
            pct = (idx + 1) / total * 100
            print(f"{desc}: {idx + 1}/{total} ({pct:.1f}%)")
        yield idx, item


def decimal_to_dms(value: float) -> tuple[float, float, float]:
    value_abs = abs(value)
    degree = int(value_abs)
    minute_full = (value_abs - degree) * 60
    minute = int(minute_full)
    second = (minute_full - minute) * 60
    return (float(degree), float(minute), float(second))


def write_png_metadata(
    image_path: Path,
    latitude: float,
    longitude: float,
    metadata: dict[str, str] | None = None,
) -> bool:
    try:
        with Image.open(image_path) as img:
            if img.format != "PNG":
                return False

            exif = img.getexif()
            gps_ifd = exif.get_ifd(0x8825) if 0x8825 in exif else {}
            gps_ifd[0] = b"\x02\x03\x00\x00"  # GPSVersionID
            gps_ifd[1] = "N" if latitude >= 0 else "S"  # GPSLatitudeRef
            gps_ifd[2] = decimal_to_dms(latitude)  # GPSLatitude
            gps_ifd[3] = "E" if longitude >= 0 else "W"  # GPSLongitudeRef
            gps_ifd[4] = decimal_to_dms(longitude)  # GPSLongitude
            gps_ifd[5] = 0  # GPSAltitudeRef
            gps_ifd[6] = 0.0  # GPSAltitude
            gps_ifd[29] = datetime.now(timezone.utc).strftime("%Y:%m:%d")  # GPSDateStamp
            exif[0x8825] = gps_ifd

            pnginfo = PngImagePlugin.PngInfo()

            # Preserve existing text metadata if present.
            for key, value in img.info.items():
                if isinstance(value, str):
                    pnginfo.add_text(key, value)

            if metadata:
                for key, value in metadata.items():
                    pnginfo.add_text(key, value)

            tmp_path = image_path.with_suffix(image_path.suffix + ".tmp")
            img.save(tmp_path, format="PNG", pnginfo=pnginfo, exif=exif.tobytes())
            tmp_path.replace(image_path)
        return True
    except Exception:
        return False


def main() -> None:
    args = parse_args()

    if not args.image_dir.exists():
        raise FileNotFoundError(f"Image directory not found: {args.image_dir}")

    rng = np.random.default_rng(SEED)
    images = list_images(args.image_dir)

    if not images:
        raise RuntimeError(f"No images found in {args.image_dir}")

    num_clusters = min(args.num_clusters, len(images))
    centers = make_cluster_centers(rng, num_clusters)
    assignments = make_cluster_assignments(
        n_items=len(images),
        num_clusters=num_clusters,
        min_run=args.min_run,
        max_run=args.max_run,
        rng=rng,
    )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    wrote_png = 0
    failed_png = 0
    progress_desc = "Generating coordinates"
    if args.write_png_metadata:
        progress_desc = "Generating coordinates + writing PNG metadata"

    with args.output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "image_path",
                "latitude",
                "longitude",
                "cluster_id",
                "cluster_center_latitude",
                "cluster_center_longitude",
            ]
        )

        for idx, image_path in iter_with_progress(images, desc=progress_desc):
            cluster_id = int(assignments[idx])
            center_lat, center_lon = centers[cluster_id]

            # Nearby image points stay in a tight local neighborhood (a few meters).
            lat_noise_m = rng.normal(0.0, args.spread_meters)
            lon_noise_m = rng.normal(0.0, args.spread_meters)
            lat = center_lat + meter_to_degree_lat(float(lat_noise_m))
            lon = center_lon + meter_to_degree_lon(float(lon_noise_m), center_lat)

            lat = float(np.clip(lat, LAT_MIN, LAT_MAX))
            lon = float(np.clip(lon, LON_MIN, LON_MAX))

            lat_str = f"{lat:.7f}"
            lon_str = f"{lon:.7f}"
            center_lat_str = f"{center_lat:.7f}"
            center_lon_str = f"{center_lon:.7f}"

            writer.writerow(
                [
                    image_path.as_posix(),
                    lat_str,
                    lon_str,
                    cluster_id,
                    center_lat_str,
                    center_lon_str,
                ]
            )

            if args.write_png_metadata:
                ok = write_png_metadata(
                    image_path,
                    latitude=lat,
                    longitude=lon,
                    metadata={
                        "coord_latitude": lat_str,
                        "coord_longitude": lon_str,
                        "coord_cluster_id": str(cluster_id),
                        "coord_cluster_center_latitude": center_lat_str,
                        "coord_cluster_center_longitude": center_lon_str,
                        "coord_seed": str(SEED),
                    },
                )
                if ok:
                    wrote_png += 1
                else:
                    failed_png += 1

    print(f"Done. Generated {len(images)} image coordinates.")
    print(f"Clusters used: {num_clusters}")
    print(f"CSV saved to: {args.output_csv}")
    if args.write_png_metadata:
        print(f"PNG metadata write success: {wrote_png}")
        print(f"PNG metadata write failed/skipped: {failed_png}")


if __name__ == "__main__":
    main()
