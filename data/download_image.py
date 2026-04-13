from __future__ import annotations

import argparse
import html
import re
import tarfile
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None


DEFAULT_URL = (
    "https://drive.google.com/file/d/1iiAmXmpcxcLszk2K65GC8asCXrBn4BOo/view?usp=drive_link"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a .tar dataset from Google Drive and extract it into data/."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Google Drive share URL.")
    parser.add_argument(
        "--tar-path",
        type=Path,
        default=Path("data/mini-imagenet-test.tar"),
        help="Local tar file path.",
    )
    parser.add_argument(
        "--extract-dir",
        type=Path,
        default=Path("data"),
        help="Directory to extract tar into.",
    )
    parser.add_argument(
        "--overwrite-tar",
        action="store_true",
        help="Overwrite local tar if it already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate actions only (no download, no extraction).",
    )
    parser.add_argument(
        "--validate-local-tar",
        action="store_true",
        help="In dry-run mode, inspect local tar structure if file exists.",
    )
    return parser.parse_args()


def extract_drive_file_id(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    if "id" in qs and qs["id"]:
        return qs["id"][0]

    match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", parsed.path)
    if match:
        return match.group(1)

    raise ValueError(f"Could not parse Google Drive file id from URL: {url}")


def build_direct_download_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def get_confirm_token(page_html: str) -> str | None:
    patterns = [
        r'name="confirm"\s+value="([^"]+)"',
        r"confirm=([0-9A-Za-z_]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html)
        if match:
            return html.unescape(match.group(1))
    return None


def parse_suggested_filename(content_disposition: str | None) -> str | None:
    if not content_disposition:
        return None

    match_utf = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition, re.I)
    if match_utf:
        return urllib.parse.unquote(match_utf.group(1).strip().strip('"'))

    match = re.search(r'filename="?([^";]+)"?', content_disposition, re.I)
    if match:
        return match.group(1).strip()

    return None


def download_from_google_drive(url: str, output_path: Path, overwrite: bool = False) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not overwrite:
        print(f"[skip] Tar already exists: {output_path}")
        return output_path

    file_id = extract_drive_file_id(url)
    direct_url = build_direct_download_url(file_id)
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    request = urllib.request.Request(direct_url, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(request) as resp:
        content_type = resp.headers.get("Content-Type", "")
        content_disposition = resp.headers.get("Content-Disposition")

        # Direct binary response.
        if "text/html" not in content_type.lower():
            return stream_to_file(resp, output_path)

        # Google Drive large-file warning page; need confirm token.
        page_html = resp.read().decode("utf-8", errors="ignore")
        token = get_confirm_token(page_html)
        if not token:
            raise RuntimeError("Failed to get Google Drive confirm token.")

    confirm_url = f"{direct_url}&confirm={urllib.parse.quote(token)}"
    confirm_request = urllib.request.Request(
        confirm_url, headers={"User-Agent": "Mozilla/5.0"}
    )
    with opener.open(confirm_request) as resp:
        suggested = parse_suggested_filename(resp.headers.get("Content-Disposition"))
        if suggested and output_path.suffix == "":
            output_path = output_path.with_name(suggested)
        return stream_to_file(resp, output_path)


def stream_to_file(response, output_path: Path) -> Path:
    total_bytes = response.headers.get("Content-Length")
    total = int(total_bytes) if total_bytes and total_bytes.isdigit() else None
    chunk_size = 1024 * 1024

    with output_path.open("wb") as f:
        if tqdm is None:
            downloaded = 0
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    percent = downloaded / total * 100
                    print(
                        f"\rDownloading: {downloaded / (1024**2):.1f}MB / "
                        f"{total / (1024**2):.1f}MB ({percent:.1f}%)",
                        end="",
                    )
            if total:
                print()
        else:
            with tqdm(
                total=total,
                unit="B",
                unit_scale=True,
                desc="Downloading tar",
            ) as pbar:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    pbar.update(len(chunk))

    print(f"[ok] Downloaded: {output_path}")
    return output_path


def safe_extract_tar(tar_path: Path, extract_dir: Path) -> None:
    extract_dir = extract_dir.resolve()
    extract_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tar_path, "r:*") as tar:
        for member in tar.getmembers():
            member_target = (extract_dir / member.name).resolve()
            if not str(member_target).startswith(str(extract_dir)):
                raise RuntimeError(f"Unsafe path in tar: {member.name}")
        tar.extractall(path=extract_dir)

    print(f"[ok] Extracted to: {extract_dir}")


def dry_run_report(url: str, tar_path: Path, extract_dir: Path, validate_local_tar: bool) -> None:
    file_id = extract_drive_file_id(url)
    direct_url = build_direct_download_url(file_id)

    print("[dry-run] No download/extract will be executed.")
    print(f"[dry-run] Parsed file_id: {file_id}")
    print(f"[dry-run] Direct URL: {direct_url}")
    print(f"[dry-run] Tar path: {tar_path}")
    print(f"[dry-run] Extract dir: {extract_dir}")

    if validate_local_tar and tar_path.exists():
        with tarfile.open(tar_path, "r:*") as tar:
            members = tar.getmembers()
            print(f"[dry-run] Local tar is readable, members: {len(members)}")
            for m in members[:10]:
                print(f"[dry-run] sample member: {m.name}")
    elif validate_local_tar:
        print(f"[dry-run] Local tar not found, skipped validation: {tar_path}")


def main() -> None:
    args = parse_args()

    tar_path = args.tar_path
    extract_dir = args.extract_dir

    if args.dry_run:
        dry_run_report(
            url=args.url,
            tar_path=tar_path,
            extract_dir=extract_dir,
            validate_local_tar=args.validate_local_tar,
        )
        return

    downloaded_tar = download_from_google_drive(
        url=args.url,
        output_path=tar_path,
        overwrite=args.overwrite_tar,
    )
    safe_extract_tar(downloaded_tar, extract_dir)


if __name__ == "__main__":
    main()
