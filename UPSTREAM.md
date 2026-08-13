# SafeLine Manager upstream baseline

This repository was initialized from the official Hiddify Manager release on
2026-08-13. The upstream source is preserved as the technical baseline for the
SafeLine Manager fork.

## Pinned revisions

| Component | Source | Revision |
| --- | --- | --- |
| Manager and server configuration | <https://github.com/hiddify/Hiddify-Manager> | tag `v12.3.3`, commit `736aae99a68aab63568c515147a871d2723f18c7` |
| Python panel submodule | <https://github.com/hiddify/Hiddify-Panel> | tag `v12.3.3`, commit `cf2e60de038c7d658d2bf4b2d84c7b433e3c918d` |

The local development branch is `codex/safeline-0.1`. The `upstream` remote
points to the official Manager repository. A SafeLine-owned `origin` remote has
not been configured yet.

The upstream tag remains the immutable comparison point even after SafeLine
commits are added:

```text
git diff v12.3.3...HEAD
```

## Frontend provenance gap

The modern user portal included in Manager `v12.3.3` is a compiled artifact:

```text
hiddify-panel/src/hiddifypanel/static/new/assets/index-ccb9873c.js
```

Its editable source is not included in either pinned repository. The helper
script `hiddify-panel/src/hiddifypanel/static/new/get_new.sh` clones
`hiddify/hiddify-user-front`, checks out `gh-pages`, and copies the latest built
files without pinning a commit. Consequently, the exact source commit that
produced the bundled asset cannot be reproduced from this release alone.

SafeLine should create and pin its own frontend source and build pipeline rather
than continue editing the generated JavaScript bundle.

## License inventory

The imported tree is not governed by one unambiguous license file:

- Root `LICENSE` contains GNU GPL version 3.
- Root `LICENSE.md` contains CC0 text and a Hiddify-specific statement.
- `hiddify-panel/src/pyproject.toml` points to
  `hiddify-panel/src/LICENSE.md`.
- `hiddify-panel/src/LICENSE.md` states CC BY-NC-SA 4.0, including a
  non-commercial restriction.
- Bundled JavaScript, fonts, icons, proxy cores, and other third-party assets
  can have their own licenses and notices.

This inventory is not legal advice. Before SafeLine is sold, distributed, or
deployed as part of a paid service, the project needs a documented license
decision: obtain permission where required, receive qualified legal clearance,
or replace components whose terms are incompatible with the intended use.

Do not delete or rewrite upstream license and attribution files during
rebranding.

## Upstream update policy

SafeLine releases must never auto-update directly from Hiddify release channels.
Before a production release, the installer and updater need to be redirected to
SafeLine-owned, versioned artifacts with pinned hashes. Upstream changes should
instead be reviewed and merged deliberately against the pinned baseline.
