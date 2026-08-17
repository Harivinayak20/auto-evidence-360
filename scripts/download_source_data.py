#!/usr/bin/env python3
"""Download public Auto Evidence 360 sources with reproducibility metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "sources.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw"
USER_AGENT = "AutoEvidence360-Portfolio/1.0 (public-data research)"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(archive: Path, destination: Path) -> list[str]:
    destination_root = destination.resolve()
    extracted = []
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            member_path = (destination / member.filename).resolve()
            if destination_root not in member_path.parents and member_path != destination_root:
                raise ValueError(f"Unsafe archive member: {member.filename}")
        bundle.extractall(destination)
        extracted = [member.filename for member in bundle.infolist() if not member.is_dir()]
    return extracted


def download(source: dict, output_root: Path, force: bool, extract: bool) -> dict:
    source_dir = output_root / source["id"]
    source_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(urllib.parse.urlparse(source["url"]).path).name or f"{source['id']}.{source['format']}"
    target = source_dir / filename
    metadata_path = source_dir / "source_metadata.json"

    if target.exists() and metadata_path.exists() and not force:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["status"] = "reused"
        return metadata

    part = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(source["url"], headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, part.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
            headers = dict(response.headers.items())
    except (urllib.error.URLError, TimeoutError):
        part.unlink(missing_ok=True)
        raise
    part.replace(target)

    extracted_files = []
    if source["format"] == "zip" and extract:
        extracted_dir = source_dir / "extracted"
        extracted_dir.mkdir(exist_ok=True)
        extracted_files = safe_extract(target, extracted_dir)

    metadata = {
        "source_id": source["id"],
        "publisher": source["publisher"],
        "landing_page": source["landing_page"],
        "download_url": source["url"],
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
        "bytes": target.stat().st_size,
        "sha256": sha256_file(target),
        "http_last_modified": headers.get("Last-Modified"),
        "http_etag": headers.get("ETag"),
        "content_type": headers.get("Content-Type"),
        "grain": source["grain"],
        "refresh": source["refresh"],
        "extracted_files": extracted_files,
        "status": "downloaded",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--only", action="append", help="Download only this source ID; repeat for more than one")
    parser.add_argument("--force", action="store_true", help="Replace an existing local download")
    parser.add_argument("--no-extract", action="store_true", help="Keep ZIP files compressed")
    parser.add_argument("--list", action="store_true", help="List configured source IDs and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    sources = config["sources"]
    if args.list:
        for source in sources:
            print(f"{source['id']}: {source['publisher']}")
        return

    selected = set(args.only or [])
    unknown = selected - {source["id"] for source in sources}
    if unknown:
        raise SystemExit(f"Unknown source ID(s): {', '.join(sorted(unknown))}")

    results = []
    for source in sources:
        if selected and source["id"] not in selected:
            continue
        print(f"Fetching {source['id']}...", file=sys.stderr)
        results.append(download(source, args.output, args.force, not args.no_extract))

    print(json.dumps({"project": config["project"], "sources": results}, indent=2))


if __name__ == "__main__":
    main()
