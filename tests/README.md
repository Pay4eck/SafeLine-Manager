# SafeLine characterization tests

These tests protect the inherited Hiddify `v12.3.3` behavior while SafeLine is
being separated from the upstream product. They deliberately use only the
Python standard library, so they can run before the full privileged Linux stack
is installed.

Run them from the repository root:

```text
python -m unittest discover -s tests -v
```

The suite currently checks:

- selected upstream files against reviewed SHA-256 fingerprints;
- the exact inherited user activation and expiration semantics;
- the administrator/user API surface required by the future SafeLine adapter;
- VLESS Reality template invariants and their coupling to the Xray usage driver;
- locked runtime package metadata and the config-application pipeline.

## Updating the baseline

`fixtures/upstream-v12.3.3.json` is a review gate, not an instruction to restore
old files automatically. When an intentional change modifies a protected file:

1. inspect the source diff;
2. add or update a semantic test for the intended behavior;
3. run the complete suite;
4. calculate the new SHA-256 digest;
5. update only the relevant fixture entry and explain the change in the commit.

Do not bulk-regenerate the fixture without reviewing each changed file.

These checks do not replace clean-VPS installation, generated-config validation
with the real Xray/Hiddify Core binaries, or security testing.
