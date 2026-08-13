# SafeLine characterization tests

These tests protect the inherited Hiddify `v12.3.3` behavior while SafeLine is
being separated from the upstream product. The small test dependency set is
pinned independently, so the suite can run before the full privileged Linux
stack is installed.

Run them from the repository root:

```text
python -m pip install --requirement tests/requirements.txt
python -m unittest discover -s tests -v
```

The suite currently checks:

- selected upstream files against reviewed SHA-256 fingerprints;
- the exact inherited user activation and expiration semantics;
- the administrator/user API surface required by the future SafeLine adapter;
- VLESS Reality template invariants and their coupling to the Xray usage driver;
- actual Jinja rendering and JSON5 parsing of a representative VLESS Reality
  inbound;
- locked runtime package metadata and the config-application pipeline.
- exact Xray version selection from Hiddify's package lock;
- checksum-verified installation of the official pinned Xray binary in CI;
- full inherited server-config rendering and Xray's native `run -test` mode.
- centralized SafeLine 0.1 brand values and compatibility-boundary wiring;
- exact modern frontend source/toolchain pins and generated branding invariants.

See `docs/XRAY_RUNTIME_VALIDATION.md` for the exact version chain, commands,
coverage, explicit runtime fixtures, and remaining integration gaps.

## Updating the baseline

`fixtures/upstream-v12.3.3.json` is a review gate, not an instruction to restore
old files automatically. When an intentional change modifies a protected file:

1. inspect the source diff;
2. add or update a semantic test for the intended behavior;
3. run the complete suite;
4. calculate the new SHA-256 digest;
5. update only the relevant fixture entry and explain the change in the commit.

Do not bulk-regenerate the fixture without reviewing each changed file.

These checks do not replace clean-VPS installation, live companion-service
integration, or security testing. The generated Xray configuration itself is
now validated with the pinned real Xray binary in CI.
