from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TESTS_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS_DIRECTORY))

from xray_test_support import render_xray_config_directory, validate_rendered_contract


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the inherited Hiddify Xray server templates into a test confdir."
    )
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--keypair", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    rendered = render_xray_config_directory(
        arguments.context,
        arguments.runtime,
        arguments.output,
    )
    coverage = validate_rendered_contract(
        arguments.output,
        arguments.context,
        arguments.keypair,
    )
    print(f"Rendered {len(rendered)} inherited Hiddify Xray JSON templates")
    print(json.dumps(coverage, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
