# SafeLine 0.1 installer and updater supply-chain audit

Audit baseline: SafeLine checkpoint `00178458`, inherited from Hiddify Manager
`v12.3.3`. This document distinguishes historical upstream mechanisms from the
only installation path approved for the first SafeLine Linux smoke test.

## Manager and Panel acquisition paths

| Entry point | What the inherited code downloads | Ref selection | Overwrite risk | SafeLine 0.1 disposition |
| --- | --- | --- | --- | --- |
| `update.sh` | Hiddify `common/download.sh`, then Manager and Panel | `main`, `dev`, or `beta`; release ultimately uses `releases/latest` | Executes remote shell and overwrites `/opt/hiddify-manager` | Disabled before network access; there is no SafeLine production update channel |
| `common/download.sh` | `common/hiddify_installer.sh` and `common/utils.sh` from Hiddify | tag, `beta`, `dev`, otherwise `main` | Executes downloaded installer without checksum | Disabled in SafeLine |
| `common/hiddify_installer.sh` release | Manager release ZIP and PyPI Panel | Manager `releases/latest`; unversioned `uv pip install -U wheel hiddifypanel` | Both product layers can become upstream Hiddify | Online/native modes disabled; local Docker mode retained because it uses checkout content |
| `common/hiddify_installer.sh` beta | Manager release ZIP and prerelease Panel | latest prerelease discovered through GitHub/PyPI APIs | Moving release selection; no archive checksum | Disabled in SafeLine |
| `common/hiddify_installer.sh` develop | Manager branch archive and Git Panel | Hiddify `dev`; Panel repository default branch | Moving branches; no archive checksum | Disabled in SafeLine |
| `common/hiddify_installer.sh` `v*` | tagged Manager asset and tagged Git Panel | caller-supplied tag | Manager tag is named, but downloads still lack a local checksum policy | Disabled for the first SafeLine stage |
| `common/downgrade.sh` | Manager and Panel | Manager `releases/latest`, Panel latest stable discovered at runtime | Replaces SafeLine files and Python package | Disabled in SafeLine |
| `common/download_install.sh` | old `hiddify-config` release and Panel 8.8.99 | Manager/config v10.5.73, Panel fixed PyPI version | Installs the wrong upstream product/baseline | Disabled in SafeLine |
| `common/download_install_easylink.sh` | previous bootstrap from Hiddify | Hiddify `main` | Remote shell execution from moving branch | Disabled in SafeLine |
| `common/docker-installer.sh` | Docker installer, Hiddify checkout/Compose/images | Docker installer script, default branch, `main`, `latest` | Can clone or pull upstream Manager | Disabled for SafeLine 0.1 |
| `cloud-init.yml` | Hiddify Manager Git checkout | repository default branch | Fresh VPS silently becomes Hiddify, not SafeLine | Disabled and points to the pinned smoke-test documentation |
| `docker-compose.yml` | previously `ghcr.io/hiddify/hiddify-manager:latest` | moving `latest` | Pulls upstream Manager image | Changed to build only the current local checkout; not the approved VPS smoke path |
| `.gitmodules` | Hiddify Panel source | Manager gitlink `cf2e60de038c7d658d2bf4b2d84c7b433e3c918d` | Safe only if the gitlink is verified | Retained as upstream source, pinned and verified by the smoke installer |

The Panel repository remains an upstream Hiddify source because it is still the
internal Python package of this compatibility stage. It is not followed by
branch name: the Manager gitlink and `smoke-test/components.lock` both require
commit `cf2e60de038c7d658d2bf4b2d84c7b433e3c918d` (Panel 12.3.3).

## Component acquisition during a native install

| Component | Inherited source and selection | Integrity/reproducibility in the approved smoke mode |
| --- | --- | --- |
| SafeLine Manager | New pinned installer fetches `Pay4eck/SafeLine-Manager` | Required lowercase 40-character commit; detached checkout; fetched SHA must match |
| Hiddify Panel compatibility package | `hiddify/Hiddify-Panel` submodule | Exact commit above; gitlink and checkout both verified; dependencies installed with committed `uv.lock --frozen` |
| SafeLine user frontend | Files stored in the Manager commit | Build source/toolchain remain pinned by `safeline/frontend/frontend.lock.json` |
| uv bootstrap | Inherited code ran `https://astral.sh/uv/install.sh` without a version | Smoke installer preinstalls official uv 0.11.16 and verifies SHA-256 `74947f...6131`; inherited moving installer is not reached |
| Xray | `common/packages.lock` through `download_package` | 26.3.27; official XTLS asset; SHA-256 `23cd9a...c8ae` is checked before execution |
| Sing-box/Hiddify Core | `common/packages.lock` through `download_package` | 4.0.4; exact release URL; SHA-256 `2a05fd...7169` is checked before execution |
| Optional locked helpers | `wgcf`, `ssh-liberty-bridge`, `mtproxygo`, `telemt`, `dnstm`, `vaydns`, `v2ray-plugin` rows in `packages.lock` | Versioned URLs and SHA-256 exist, but the Reality-only smoke profile disables the corresponding optional features before their installer steps |
| nginx | nginx.org signing key and apt repository | Package constraint `1.26.*`; repository signature is checked by apt, but the exact Debian package build is not snapshot-pinned |
| HAProxy | `ppa:vbernat/haproxy-3.3` on Ubuntu 24.04 (`3.0` on 22.04) | Package constraint `3.3.*`; PPA metadata is signed, exact build is not snapshot-pinned |
| MariaDB, Redis and base tools | Ubuntu apt repositories | Distribution packages; versions depend on the Ubuntu 24.04 repository snapshot at install time |
| Python runtime | uv-managed Python requested by inherited code | Smoke installer creates the Panel environment first with exact Python 3.13.9; Panel wheels/sdists are hash-locked by `uv.lock` |
| ACME client | inherited `https://get.acme.sh`, followed by `acme.sh --upgrade` | Explicitly skipped in smoke mode because it is moving; generated self-signed setup remains sufficient for the disposable IP/Reality test |
| GeoLite databases | inherited `P3TERX/GeoLite.mmdb` `download` branch | Smoke mode downloads commit `836c4a73...` paths and verifies both SHA-256 values; the moving branch remains only in the non-smoke compatibility path |
| Linux kernel fallback | `common/google-bbr.sh` can query Ubuntu mainline | Ubuntu 24.04 already satisfies the kernel check, so the smoke path only enables BBR and does not select/download a kernel |

“Reproducible” for this stage means the application source graph, Panel
dependency graph, and VPN binaries are fixed and verified. It does not yet mean
a bit-identical operating-system image. Production packaging still needs an OS
package snapshot and a production certificate-client policy.

The highest version selected from `common/packages.lock` for each optional
component is explicit even though the Reality-only profile disables it:

| Lock name | Resolved version | Origin |
| --- | --- | --- |
| `xray` | 26.3.27 | `XTLS/Xray-core` GitHub release |
| `singbox` | 4.0.4 | `hiddify/hiddify-core` GitHub release |
| `wgcf` | 2.2.30 | `ViRb3/wgcf` GitHub release |
| `ssh-liberty-bridge` | 1.3.0 | `hiddify/ssh-liberty-bridge` GitHub release |
| `mtproxygo` | 2.1.7 | `9seconds/mtg` GitHub release |
| `telemt` | 3.3.31 | `telemt/telemt` GitHub release |
| `dnstm` | 0.7.0 | `hiddify/dnstm` GitHub release |
| `vaydns` | 0.2.5 | `net2share/vaydns` GitHub release |
| `v2ray-plugin` | 1.3.2 | `shadowsocks/v2ray-plugin` GitHub release |

Every selected `packages.lock` asset has architecture, URL and SHA-256 fields.
Historical lower-version rows are retained for compatibility but are not
selected by the current version-sort resolver.

## How upstream could overwrite SafeLine before these changes

1. Panel `auto_update` created `/etc/cron.d/hiddify_auto_update`, which called
   `update.sh` nightly.
2. `update.sh` selected a Hiddify mode and executed a remotely downloaded
   `common/download.sh`.
3. `common/hiddify_installer.sh` installed an unpinned/most-recent Panel and
   unpacked a Manager archive directly over `/opt/hiddify-manager`.
4. The release and downgrade paths did not verify archive checksums and did not
   preserve SafeLine-specific files as a separate layer.

The approved smoke install writes `/opt/hiddify-manager/.safeline-smoke-install`,
sets `auto_update=false`, removes the auto-update cron file, and uses an
`update.sh` which has no enabled channel. The marker records only repository
and commit metadata; it contains no UUID, key, password, domain, or URL.

## Deliberately unsupported in 0.1

- No production update, downgrade, cloud-init, release, or container channel.
- The inherited release/Docker GitHub workflows still describe Hiddify-era
  publishing and must not be triggered for SafeLine releases.
- `uninstall.sh purge` is not an approved cleanup method: it is broad, does not
  fully reverse host changes, and is unsafe as a rollback primitive.
- An in-place upgrade of an existing Hiddify or SafeLine server is explicitly
  outside this smoke test.

Only `smoke-test/install-pinned.sh --commit <exact SHA>` is approved for the
first disposable VPS test.
