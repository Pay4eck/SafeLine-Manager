#!/usr/bin/env python3
"""Create a complete, reviewable inventory of Hiddify branding references."""

from __future__ import annotations

from collections import Counter
import argparse
import json
from pathlib import Path
import re


BRAND_PATTERN = re.compile(r"hiddify", re.IGNORECASE)
SKIP_PARTS = {".git", ".test-runtime", ".test-output", "node_modules", "__pycache__"}
SELF_REFERENTIAL_OUTPUTS = {
    "docs/BRANDING_AUDIT.md",
    "docs/BRANDING_AUDIT_INVENTORY.json",
    "docs/FRONTEND_SOURCE_AUDIT.md",
}


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_skipped(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return any(part in SKIP_PARTS for part in relative.parts) or relative.as_posix() in SELF_REFERENTIAL_OUTPUTS


def classify(relative: str, line: str, *, kind: str) -> tuple[str, str]:
    lowered_path = relative.lower()
    lowered = line.lower()

    if kind == "path":
        if lowered_path.startswith("docs/") or lowered_path.startswith("history"):
            return "B", "historical/documentation asset name; preserve provenance"
        if "/static/" in lowered_path or "/assets/" in lowered_path:
            return "A", "user-visible logo or branding asset name"
        return "C", "filesystem/module/component identifier used by inherited runtime"

    if any(token in lowered_path for token in ("license", "history", "readme", "docs/")):
        return "B", "license, provenance, history, or documentation reference"

    if lowered_path.startswith("safeline/frontend/patches/") or lowered_path == "safeline/tools/branding_audit.py":
        return "B", "reviewed upstream source context or required attribution"

    visible_path = any(
        token in lowered_path
        for token in (
            "/templates/",
            "/translations/",
            "/translations.i18n/",
            "messages.pot",
            "info_api.py",
            "login.py",
            "telegram",
            "notification",
            "email",
        )
    )
    visible_line = any(
        token in lowered
        for token in (
            "<title",
            "meta name=\"description\"",
            "powered by",
            "brand_title",
            "admin_message",
            "page-title",
            "copyright",
            "footer",
            "flash(",
            "gettext",
            "_(\"",
            "_('",
            "msgid",
            "msgstr",
        )
    )
    if visible_path and visible_line:
        return "A", "user/admin-visible copy or presentation asset"

    critical_tokens = (
        "hiddifypanel",
        "/opt/hiddify-manager",
        "hiddify_cfg_path",
        "hiddify-api-key",
        "hiddify://",
        "hiddify-panel.service",
        "hiddify-xray.service",
        "hiddify-nginx.service",
        "hiddify-haproxy.service",
        "hiddify-singbox.service",
        "hiddify-redis.service",
        "ghcr.io/hiddify/",
        "docker.io/hiddify/",
        "user=hiddify-panel",
        "group=hiddify-panel",
        "hiddify-panel.db",
    )
    critical_code = re.search(r"\b(import|from)\s+hiddify", lowered) is not None
    critical_config = lowered_path.endswith((".service", "docker-compose.yml", ".env"))
    if any(token in lowered for token in critical_tokens) or critical_code or critical_config:
        return "C", "compatibility-critical package, path, protocol, service, or runtime identifier"

    actual_client = any(
        token in lowered
        for token in (
            "hiddify next",
            "hiddifynext",
            "hiddifyng",
            "app.hiddify.com",
            "ang.hiddify.com",
            "hiddify-desktop",
        )
    )
    if actual_client:
        return "B", "real compatible client name/package/UA; do not mislabel it as SafeLine"

    if visible_path:
        return "A", "user/admin-facing template, localization, or message source"

    return "B", "upstream reference retained behind the SafeLine presentation boundary"


def inventory(root: Path) -> dict:
    records: list[dict] = []
    files_scanned = 0
    path_identifiers: set[str] = set()

    for path in sorted(root.rglob("*")):
        if _is_skipped(path, root):
            continue
        relative = _relative(path, root)

        for index, part in enumerate(path.relative_to(root).parts):
            if BRAND_PATTERN.search(part):
                identifier = Path(*path.relative_to(root).parts[: index + 1]).as_posix()
                path_identifiers.add(identifier)

        if not path.is_file():
            continue
        files_scanned += 1
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            count = data.lower().count(b"hiddify")
            if count:
                category, reason = classify(relative, "", kind="binary")
                records.append(
                    {
                        "category": category,
                        "kind": "binary-content",
                        "path": relative,
                        "line": None,
                        "matches": count,
                        "sample": "binary file contains ASCII Hiddify tokens",
                        "reason": reason,
                    }
                )
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            matches = BRAND_PATTERN.findall(line)
            if not matches:
                continue
            category, reason = classify(relative, line, kind="text")
            sample = " ".join(line.strip().split())
            if len(sample) > 240:
                sample = sample[:237] + "..."
            records.append(
                {
                    "category": category,
                    "kind": "text",
                    "path": relative,
                    "line": line_number,
                    "matches": len(matches),
                    "sample": sample,
                    "reason": reason,
                }
            )

    for identifier in sorted(path_identifiers):
        category, reason = classify(identifier, "", kind="path")
        records.append(
            {
                "category": category,
                "kind": "path",
                "path": identifier,
                "line": None,
                "matches": 1,
                "sample": "Hiddify-named file or directory",
                "reason": reason,
            }
        )

    records.sort(key=lambda item: (item["path"], item["line"] or 0, item["kind"]))
    category_records = Counter(record["category"] for record in records)
    category_matches = Counter()
    category_files: dict[str, set[str]] = {category: set() for category in "ABC"}
    for record in records:
        category_matches[record["category"]] += record["matches"]
        category_files[record["category"]].add(record["path"])

    return {
        "schema": 1,
        "scope": "all repository files, including the pinned Panel submodule worktree",
        "excluded": sorted(SELF_REFERENTIAL_OUTPUTS | {".git", ".test-runtime", ".test-output", "node_modules", "__pycache__"}),
        "summary": {
            "files_scanned": files_scanned,
            "records": len(records),
            "records_by_category": dict(sorted(category_records.items())),
            "matches_by_category": dict(sorted(category_matches.items())),
            "unique_paths_by_category": {
                category: len(paths) for category, paths in category_files.items()
            },
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/BRANDING_AUDIT_INVENTORY.json"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    result = inventory(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
