# SafeLine Manager 0.1 Linux installation smoke test

Status: **prepared, not yet passed**. CI and Xray configuration validation are
prerequisites only. This stage passes only after a compatible client makes a
real VLESS Reality connection to a new disposable VPS, traffic accounting and
user blocking work, and the connection still works after a VPS reboot.

## Supported first-test environment

- Fresh **Ubuntu Server 24.04 LTS amd64** with systemd as PID 1.
- KVM/full virtual machine; do not use an existing Hiddify/SafeLine server.
- Suggested minimum test envelope: 2 vCPU, 2 GB RAM, 20 GB disk, public IPv4.
- Root/sudo SSH access using an SSH key.
- A snapshot taken before installation, or a VPS that can be destroyed and
  recreated without affecting any production service.
- A separate client device/network for the real connection test.

The installer refuses Ubuntu versions/architectures outside that envelope,
existing `/opt/hiddify-*` paths, existing `hiddify-*` systemd units, and hosts
where TCP 80 or 443 is already listening.

## Network ports

Allow these in the VPS provider firewall/security group before installation:

| Direction | Protocol/port | Purpose |
| --- | --- | --- |
| inbound | TCP 22 | SSH administration (or the provider's chosen SSH port) |
| inbound | TCP 80 | initial web entry/redirect and certificate workflow |
| inbound | TCP 443 | administrative/user web and VLESS Reality through HAProxy |
| inbound | UDP 443 | inherited full-protocol configuration; not required for the VLESS Reality TCP proof itself |
| outbound | TCP 443, TCP 80, DNS | GitHub, Ubuntu/PyPI/component downloads, DNS and external HTTPS test |

Panel 9000, Xray API 10085, Redis 6379, MariaDB 3306 and nginx dispatcher
ports are internal and must not be opened in the provider firewall.

## Exact installation procedure

The preparation handoff supplies `SAFELINE_COMMIT`, the exact 40-character
commit to test. A commit cannot contain its own future Git object ID, so it is
intentionally supplied out-of-band in the signed-off handoff, never resolved
from a branch, tag, `latest`, `main`, or `master` by the installer.

SSH to the **new test VPS**, then run:

```bash
export SAFELINE_COMMIT='<paste the exact 40-character commit from the preparation report>'
test "${#SAFELINE_COMMIT}" -eq 40
mkdir -p /tmp/safeline-smoke
curl --proto '=https' --tlsv1.2 -fL "https://raw.githubusercontent.com/Pay4eck/SafeLine-Manager/${SAFELINE_COMMIT}/smoke-test/install-pinned.sh" -o /tmp/safeline-smoke/install-pinned.sh
curl --proto '=https' --tlsv1.2 -fL "https://raw.githubusercontent.com/Pay4eck/SafeLine-Manager/${SAFELINE_COMMIT}/smoke-test/install-pinned.sh.sha256" -o /tmp/safeline-smoke/install-pinned.sh.sha256
cd /tmp/safeline-smoke
sha256sum --check install-pinned.sh.sha256
sudo bash ./install-pinned.sh --commit "$SAFELINE_COMMIT"
```

Do not pipe a network response directly to `bash`. The bootstrap file is fetched
from the exact Manager commit and checked before execution. The installer then
verifies the fetched Manager commit, Panel gitlink/checkout, lock-file digests,
and the official checksum of the pinned uv bootstrap. Xray and Sing-box are
verified by the inherited checksum-enforcing package manager.

Secrets are generated on the VPS by Panel, MariaDB and Redis. Do not create a
`config.env` containing real data and do not copy production databases/keys to
this server.

## Expected installation layout

Expected active services:

- `hiddify-panel.service`
- `hiddify-panel-background-tasks.service`
- `hiddify-nginx.service`
- `hiddify-haproxy.service`
- `hiddify-xray.service`
- `hiddify-singbox.service` (installed by the inherited manager even though
  Xray is selected for this test)
- `hiddify-redis.service`
- `mariadb.service`

Important paths (internal compatibility names remain deliberately unchanged):

| Path | Content/sensitivity |
| --- | --- |
| `/opt/hiddify-manager/.safeline-smoke-install` | non-secret pinned commit marker |
| `/opt/hiddify-manager/current.json` | **secret** runtime export; never send it |
| `/opt/hiddify-manager/hiddify-panel/app.cfg` | **secret** database/Redis configuration |
| `/opt/hiddify-manager/xray/configs/` | rendered server config; contains Reality private key and UUIDs |
| `/opt/hiddify-manager/nginx/` | nginx templates/rendered config |
| `/opt/hiddify-manager/haproxy/` | HAProxy configuration |
| `/opt/hiddify-manager/ssl/` | private keys/certificates |
| `/opt/hiddify-manager/log/system/` | service/install logs; redact URLs, UUIDs and keys before sharing |

## Automated status check

Run locally on the VPS:

```bash
sudo bash /opt/hiddify-manager/smoke-test/verify-install.sh
sudo systemctl --failed --no-pager
sudo ss -lntup
```

The verification script prints the exact Xray test command and checks services,
restart counts, ports, local web status, the pinned versions, a rendered VLESS
Reality inbound, Vision flow, generated Reality key syntax, short IDs,
serverNames and `xray run -test`. It never prints the private key or UUIDs.

To view the administrator link **only in your SSH terminal**:

```bash
sudo jq -r '.panel_links[]' /opt/hiddify-manager/current.json
```

Do not paste that link into chat. Open it privately in a browser.

## Mandatory smoke-test checklist

Record pass/fail, UTC time, and non-secret evidence for each item.

### System

- [ ] All expected systemd services are `active`.
- [ ] nginx and HAProxy are active and configuration checks succeed.
- [ ] Panel, Xray and the inherited Sing-box companion are active.
- [ ] Required listening ports exist; internal database/cache ports are not publicly exposed.
- [ ] `NRestarts` remains stable for at least 10 minutes; no crash loop.
- [ ] `update.sh` exits with code 78 and no auto-update cron exists.

### Web

- [ ] Private administrator URL opens without a 5xx response.
- [ ] Administrative UI visibly says **SafeLine Manager**.
- [ ] User page visibly says **SafeLine VPN**.
- [ ] title, favicon and manifest are SafeLine-branded.
- [ ] Browser Network panel shows no frontend asset 404s.
- [ ] Repeated admin/user page requests show no 5xx responses.

### User lifecycle

- [ ] Create a new, clearly named smoke-test user (do not reuse the default user).
- [ ] Set and save an expiry/package duration and a small traffic limit.
- [ ] Reload the edit page: UUID, expiry and limit remain unchanged.
- [ ] A subscription URL is generated and opens successfully.
- [ ] A QR code is generated and decodes to the same subscription/config.
- [ ] Keep UUID, QR and full subscription URL private.

### Reality

- [ ] VLESS Reality is enabled and a corresponding inbound exists.
- [ ] Reality X25519 keys were generated on this VPS; the private key never leaves it.
- [ ] `serverNames`/SNI and at least one `shortId` are present.
- [ ] The VLESS client entry uses `xtls-rprx-vision`.
- [ ] This exact command succeeds:

  ```bash
  sudo env XRAY_LOCATION_ASSET=/opt/hiddify-manager/xray/bin \
    /opt/hiddify-manager/xray/bin/xray run -test \
    -confdir /opt/hiddify-manager/xray/configs/
  ```

### Real client connection (the actual acceptance criterion)

- [ ] Add the private subscription URL to a compatible, current VLESS Reality client.
- [ ] Confirm the selected node is VLESS + Reality + Vision with the expected public IP/SNI/short ID.
- [ ] Connect from a device outside the VPS network.
- [ ] Open an external HTTPS site successfully through the VPN.
- [ ] Confirm the client's observed public IP is the test VPS IP.
- [ ] Generate a small, measured amount of traffic and confirm Panel usage increases.
- [ ] Disable/block the smoke user, apply configuration, and confirm the existing/new connection stops.
- [ ] Re-enable only if needed for the reboot test.

### Reboot

- [ ] Run `sudo reboot` and wait for SSH to return.
- [ ] Re-run `verify-install.sh` and `systemctl --failed`.
- [ ] Confirm services started automatically and restart counters are stable.
- [ ] Repeat the real Reality connection and external HTTPS request.
- [ ] Confirm traffic accounting still increases.

## Failure collection

Send only these non-secret results back for analysis:

```bash
cat /etc/os-release
uname -a
sudo cat /opt/hiddify-manager/.safeline-smoke-install
sudo bash /opt/hiddify-manager/smoke-test/verify-install.sh
sudo systemctl --failed --no-pager
sudo systemctl show hiddify-panel hiddify-xray hiddify-nginx hiddify-haproxy -p Id -p ActiveState -p SubState -p NRestarts
```

Also report browser/client name and version, pass/fail timestamps, HTTP status
codes, whether the external IP changed to the VPS IP, traffic before/after as
numbers, disable-user behavior, and reboot behavior. If a service fails, send a
small redacted journal excerpt for that service only.

Never send `current.json`, `app.cfg`, database/Redis passwords, full admin or
subscription URLs, UUIDs, QR images, Xray JSON, Reality private/public key pair,
TLS keys, API keys, Telegram tokens, or production data.

## Removal and rollback

The supported cleanup for this stage is to **destroy the disposable VPS** in
the provider console. The supported rollback is to restore the pre-install VPS
snapshot or recreate the same clean Ubuntu 24.04 image and rerun the exact
pinned commit.

Do **not** run inherited `uninstall.sh purge`: it broadly removes files/packages
but does not reliably reverse all firewall, users, cron, database and systemd
changes. In-place uninstall/rollback will be designed only after the clean-VPS
smoke test succeeds.
