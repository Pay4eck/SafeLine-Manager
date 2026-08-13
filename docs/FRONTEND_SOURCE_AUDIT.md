# Hiddify 12.3.3 user frontend source investigation

## Exact provenance

The modern user page distributed in the pinned Panel submodule loads
`hiddifypanel/static/new/assets/index-ccb9873c.js`.  Its upstream repository is:

```text
https://github.com/hiddify/hiddify-user-front.git
```

The exact chain is recoverable:

- Panel template/bundle: Hiddify Panel `v12.3.3`, submodule commit
  `cf2e60de038c7d658d2bf4b2d84c7b433e3c918d`;
- deployment commit on `gh-pages`:
  `2d3edc24321f80c3292465f4034c94e522d4031d`;
- that deployment commit names source commit
  `5dc87f743f233b8fd0ff0c40b9a3ddbbe7c2812a` in its commit message;
- upstream raw bundle SHA-256:
  `a0a7af56079d68e83256da0bbb6a019839f598fc2d0f8aad8b3be25c48a0689c`;
- after the two path substitutions performed by Panel’s `get_new.sh`, the
  normalized bundle SHA-256 is
  `cb03c4e2c2d78f661e9c1e16309534f6685b5c5682c21ac2d0c4302847e1c32e`,
  byte-for-byte equal to the Panel copy after line-ending normalization.

Therefore the source commit is exact, not an estimate.

## How Panel imported and connected the build

`hiddifypanel/static/new/get_new.sh` cloned the frontend, checked out the
moving `gh-pages` branch, copied `assets/` and `i18n/` into
`hiddifypanel/static/new/`, and copied `index.html` to
`hiddifypanel/panel/user/templates/new.html`.  It then changed absolute asset
paths to `../static/new/...` and inserted Jinja profile/version placeholders.

`UserView.new()` renders `new.html`.  The shipped template loads:

```text
../static/new/assets/index-ccb9873c.js
../static/new/assets/index-fa00de9a.css
```

The original import script was not reproducible because it followed a moving
branch and did not record source/tool versions.

## Toolchain and dependencies

The exact source uses React 18, TypeScript 5, Vite 4, MUI 5, React Router 6,
react-query 3, i18next 23, Axios 1, Tailwind/PostCSS, and the other packages in
its `package.json`/`yarn.lock`.  Its upstream deploy workflow used:

- Ubuntu `latest`;
- Node.js 16;
- globally installed, unversioned Yarn;
- `yarn` followed by `yarn build` (`tsc && vite build`).

SafeLine pins Node.js `16.20.2` and Yarn `1.22.22`.  The exact upstream commit’s
`yarn.lock` omitted the declared `moment` dependency, so
`yarn install --frozen-lockfile` failed.  The reviewed SafeLine source patch
adds only the resolved `moment@2.30.1` lock entry, then CI requires a frozen
install.  The lock metadata lives in `safeline/frontend/frontend.lock.json`.

The local verification used the official Node.js 16.20.2 Windows archive from
`nodejs.org`; its SHA-256
`f8bb35f6c08dc7bf14ac753509c06ed1a7ebf5b390cd3fbdc8f8c1aedd020ec3`
matched the official `SHASUMS256.txt`.  Yarn was installed at exactly 1.22.22
through that verified Node/npm runtime.

## SafeLine build strategy

SafeLine does not hand-edit the generated JavaScript.  It stores a small,
reviewable source patch at
`safeline/frontend/patches/0001-safeline-branding.patch`, builds the exact
commit, and publishes the result with `publish_frontend.py`.  Product values
are supplied at runtime from the centralized `safeline/brand.json`; the source
patch contains layout/behavior, not duplicate product configuration.

Published files are isolated under:

```text
safeline/static/user-front/assets/
safeline/static/user-front/i18n/
safeline/templates/new.html
```

The template loader gives the SafeLine `new.html` priority over the unchanged
submodule template.  Its bundle and locale paths point to the SafeLine static
route.  The `hiddify://` import deep link remains unchanged because it is a
client compatibility protocol, not product chrome.

CI checks out the exact source commit with `core.autocrlf=false`, checks and
applies the patch, verifies Node and Yarn versions, installs with
`--frozen-lockfile`, builds, performs the same path transforms as the Panel
importer, and compares every output file to the committed assets.  Explicit LF
handling keeps Vite content hashes identical on Windows and Linux.  A
differing, missing, or extra file fails the job.

If the upstream repository later becomes unavailable, the safe next step is
to vendor the exact source snapshot or maintain a dedicated SafeLine frontend
fork at the recorded commit.  Patching a minified bundle is not an accepted
fallback.
