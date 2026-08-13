#!/usr/bin/env python3
"""Publish a Vite dist directory in the layout expected by Hiddify Panel.

The path transforms intentionally mirror hiddifypanel/static/new/get_new.sh,
but point at the isolated SafeLine asset route.  This script never edits a
minified bundle semantically; branding changes are compiled from the source
patch before this packaging step.
"""

from __future__ import annotations

import argparse
import filecmp
from pathlib import Path
import shutil
import sys
import tempfile


ASSET_PREFIX = "../safeline-static/user-front/assets/"
I18N_PREFIX = "../safeline-static/user-front/i18n/"


def _normalized_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def publish(dist: Path, static_output: Path, template_output: Path) -> None:
    if not (dist / "index.html").is_file():
        raise ValueError(f"Vite index is missing: {dist / 'index.html'}")
    if not (dist / "assets").is_dir() or not (dist / "i18n").is_dir():
        raise ValueError("Vite dist must contain both assets/ and i18n/")

    static_output.mkdir(parents=True, exist_ok=True)
    for directory in ("assets", "i18n"):
        target = static_output / directory
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(dist / directory, target)

    html = (dist / "index.html").read_text(encoding="utf-8")
    html = html.replace("/assets/", ASSET_PREFIX)
    template_output.parent.mkdir(parents=True, exist_ok=True)
    template_output.write_text(html, encoding="utf-8", newline="\n")

    for javascript in (static_output / "assets").glob("*.js"):
        source = javascript.read_text(encoding="utf-8")
        source = source.replace("../i18n/", I18N_PREFIX)
        source = source.replace("/assets/", ASSET_PREFIX)
        javascript.write_text(source, encoding="utf-8", newline="\n")


def compare_trees(actual: Path, expected: Path) -> list[str]:
    differences: list[str] = []
    comparison = filecmp.dircmp(actual, expected)

    def walk(node: filecmp.dircmp, prefix: Path = Path()) -> None:
        for name in node.left_only:
            differences.append(f"unexpected: {prefix / name}")
        for name in node.right_only:
            differences.append(f"missing: {prefix / name}")
        for name in node.diff_files:
            left = node.left / name
            right = node.right / name
            if _normalized_bytes(left) != _normalized_bytes(right):
                differences.append(f"different: {prefix / name}")
        for name, child in node.subdirs.items():
            walk(child, prefix / name)

    walk(comparison)
    return differences


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", required=True, type=Path)
    parser.add_argument("--static-output", type=Path)
    parser.add_argument("--template-output", type=Path)
    parser.add_argument("--check-static", type=Path)
    parser.add_argument("--check-template", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checking = args.check_static is not None or args.check_template is not None
    if checking and (args.check_static is None or args.check_template is None):
        raise ValueError("--check-static and --check-template must be used together")

    if checking:
        with tempfile.TemporaryDirectory(prefix="safeline-front-") as temporary:
            root = Path(temporary)
            static_output = root / "static"
            template_output = root / "new.html"
            publish(args.dist, static_output, template_output)
            differences = compare_trees(static_output, args.check_static)
            if _normalized_bytes(template_output) != _normalized_bytes(args.check_template):
                differences.append("different: new.html")
            if differences:
                print("SafeLine frontend output is not reproducible:", file=sys.stderr)
                print("\n".join(f"- {item}" for item in differences), file=sys.stderr)
                return 1
            print("SafeLine frontend output matches the committed assets and template.")
            return 0

    if args.static_output is None or args.template_output is None:
        raise ValueError("publishing requires --static-output and --template-output")
    publish(args.dist, args.static_output, args.template_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
