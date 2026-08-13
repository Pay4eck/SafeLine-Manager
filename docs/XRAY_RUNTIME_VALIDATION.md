# Reproducible Xray runtime validation

This test validates the inherited Hiddify Manager `v12.3.3` server templates
without modifying them. It deliberately separates three questions:

1. which Xray release the pinned Manager actually installs;
2. whether a production-shaped `current.json` renders the expected sections;
3. whether the resulting configuration is accepted by the real Xray parser and
   builder.

## Exact Xray version

The selected version is **Xray 26.3.27**. It is derived from the pinned source,
not chosen from the current upstream release list:

1. `xray/install.sh` sets `version=""` and calls
   `download_package xray sb.zip $version`.
2. `common/package_manager.sh:download_package` sends an empty requested
   version to `get_latest_version`.
3. `get_latest_version` filters `common/packages.lock` by package and host
   architecture, version-sorts the rows, and selects the last one.
4. In the Manager `v12.3.3` lock file, the highest Xray version for both
   supported architectures is `26.3.27`.

The Linux artifacts used by Hiddify and by CI are:

| Architecture | Official release asset | SHA-256 from `packages.lock` |
| --- | --- | --- |
| amd64 | `Xray-linux-64.zip` | `23cd9af937744d97776ee35ecad4972cf4b2109d1e0fe6be9930467608f7c8ae` |
| arm64 | `Xray-linux-arm64-v8a.zip` | `4d30283ae614e3057f730f67cd088a42be6fdf91f8639d82cb69e48cde80413c` |

Both URLs point to the exact
[`XTLS/Xray-core` v26.3.27 release](https://github.com/XTLS/Xray-core/releases/tag/v26.3.27).
The test installer rejects a non-official URL, a `latest` URL, an unpinned
version, a malformed digest, a checksum mismatch, archive traversal, and
archive symlinks before making the binary executable.

The Windows amd64 artifact is used only for a native developer-machine check.
Its pinned SHA-256,
`d004c39288ce9ada487c6f398c7c545f7d749e44bdfdd59dbc9f865afba4e1ad`,
comes from the digest field of the same official GitHub release. CI uses the
exact Linux amd64 artifact and checksum present in Hiddify's lock file.

## How the server config is rendered

On an installed server, `reload_all_configs` writes
`/opt/hiddify-manager/current.json` from the panel HTTP API or
`hiddify-panel-cli all-configs`. The panel's `all_configs_for_cli()` exports:

- active, non-quota-exhausted users as `users`;
- eligible virtual-child domains, including calculated internal ports, as
  `domains`;
- database-backed configuration for every child as `chconfigs`;
- administrator API/path/link metadata.

`common/jinja.py` converts child IDs to integers, exposes `chconfigs[0]` as
`hconfigs`, loads the unchanged templates, provides the same filters and
globals, parses rendered JSON5, and writes normalized JSON files. The test
renderer follows that sequence and maps only Hiddify's absolute template
include prefix to the repository checkout.

The production-shaped fixture enables all current generic Xray combinations:
VLESS, VMess, and Trojan over XHTTP, WebSocket, gRPC, TCP, and HTTPUpgrade. It
also enables VLESS Reality over TCP, gRPC, and XHTTP. KCP remains disabled, as
it is in Hiddify's initialized configuration; the reason is recorded below.

The Reality keypair is the public Alice X25519 test vector from RFC 7748,
encoded as unpadded base64url for Xray. It is explicitly test-only and is not a
server credential. CI asks Xray itself to derive the recorded public key from
the test private key before rendering the server configuration.

## Commands

Linux CI installs and verifies the binary with:

```text
python tests/scripts/install_verified_xray.py --platform linux-amd64 --destination .test-runtime/xray-linux
python tests/scripts/verify_xray_runtime.py --xray .test-runtime/xray-linux/xray --metadata tests/fixtures/xray-v26.3.27.json --keypair tests/fixtures/xray-test-keypair.json
```

It renders and validates the inherited server configuration with:

```text
python tests/scripts/render_hiddify_xray.py --context tests/fixtures/xray-full-current.json --runtime tests/fixtures/xray-render-runtime.json --keypair tests/fixtures/xray-test-keypair.json --output .test-output/xray-config
XRAY_LOCATION_ASSET="$PWD/.test-runtime/xray-linux" .test-runtime/xray-linux/xray run -test -confdir .test-output/xray-config
```

The last command is Xray's standard configuration test mode. GeoIP and geosite
data come from the same checksum-verified release archive.

## Coverage

The structural assertions run before Xray and produce a compact coverage
summary. The real Xray test then parses and builds the combined configuration.

| Area | Covered now |
| --- | --- |
| VLESS Reality | TCP, gRPC, and XHTTP inbounds from unchanged Hiddify templates |
| Users | Canonical UUID syntax and the exact identities rendered into VLESS, VMess, and Trojan clients |
| Vision | `xtls-rprx-vision` on Reality TCP clients; empty flow on non-TCP Reality clients |
| Reality key | 32-byte test-only private/public values and public-key derivation by Xray |
| Short IDs | Empty ID plus configured even-length hexadecimal values up to eight bytes |
| SNI | Each `serverNames` entry and matching `dest` host |
| Routing | Rule construction, local-address fixture, DNS/API rules, block rules, and valid outbound references |
| Outbounds | `freedom`, `WARP`, `blackhole`, `forbidden_sites`, and `DNS-Internal` |
| DNS | Configured resolver, fallback resolvers, IPv4 strategy, and internal DNS tag |
| Logging | Rendered log level and inherited log options |
| API/statistics | Handler, logger, and stats services; API routing; user/system statistics policy; `stats` section |
| Other inherited inbounds | Full 15-entry protocol/transport matrix and local SOCKS inbound |

## Runtime context and remaining gaps

The repository does not contain a live Hiddify database or a configured VPS.
The test therefore makes the following boundaries explicit:

- Users, domains, child configuration, admin paths, and panel links are
  synthetic values with the same JSON shape as `all_configs_for_cli()`. They
  do not prove database migrations or SQL queries on a live installation.
- Domain internal ports normally depend on database IDs and values such as
  `special_port`. The fixture records the calculated output that would be
  exported, not the calculation against a live database.
- `03_routing.json.j2` executes one host command to enumerate local IPv4
  addresses. Its exact command and deterministic documentation-range result
  are kept separately in `xray-render-runtime.json`; any other command fails
  the test instead of being silently stubbed.
- The legacy TLS/XTLS template is guarded by a literal `if 0`, so certificate
  discovery and certificate-file loading are not part of the generated
  `v12.3.3` Xray config. No fake certificate paths are supplied.
- The legacy dispatcher templates read `hconfigs['domains']`, although the
  panel exports domains at the top level, and their loop-local flag does not
  escape Jinja's loop scope. They therefore render empty in the real pipeline
  and in this test. No nested-domain placeholder is injected.
- KCP is disabled. Enabling the inherited KCP branch makes Xray 26.3.27 reject
  its `mkcp seed` setting because that feature was removed and migrated to new
  transports. This is an inherited compatibility issue; fixing the template
  would be a product-code change and is intentionally outside this task.
- Xray `run -test` parses and builds the config but does not prove that HAProxy,
  nginx, abstract Unix sockets, the WARP interface, DNS reachability, Reality
  destinations, or API consumers are available at runtime.
- API/statistics configuration is checked, but live gRPC API calls and traffic
  counters require a running service and real traffic.
- The fixture covers child `0`; multi-child database export and routing are not
  exercised.
- Xray reports deprecation warnings for several inherited transports and
  protocols. Warnings do not fail config test mode, but future Xray upgrades
  will need a separate compatibility review.

These gaps require an integration test on a disposable Linux installation with
the actual panel database and companion services. They are not replaced with
unlabelled mocks in this suite.
