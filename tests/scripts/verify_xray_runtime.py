from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def run_checked(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n{output}"
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Xray's version and the public half of the test-only X25519 pair."
    )
    parser.add_argument("--xray", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--keypair", type=Path, required=True)
    arguments = parser.parse_args()

    metadata = json.loads(arguments.metadata.read_text(encoding="utf-8"))
    keypair = json.loads(arguments.keypair.read_text(encoding="utf-8"))
    executable = str(arguments.xray.resolve())

    version_output = run_checked([executable, "version"])
    version_match = re.search(r"^Xray\s+(\S+)", version_output, re.MULTILINE)
    if version_match is None or version_match.group(1) != metadata["version"]:
        raise RuntimeError(
            f"Unexpected Xray version output; expected {metadata['version']}:\n{version_output}"
        )

    x25519_output = run_checked(
        [executable, "x25519", "-i", keypair["private_key"]]
    )
    if keypair["public_key"] not in x25519_output:
        raise RuntimeError(
            "Xray did not derive the recorded public key from the test private key:\n"
            + x25519_output
        )

    print(version_output.strip())
    print("X25519 fixture pair verified by the pinned Xray binary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
