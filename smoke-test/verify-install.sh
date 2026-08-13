#!/bin/bash
set -uo pipefail

readonly INSTALL_ROOT=/opt/hiddify-manager
readonly MARKER="$INSTALL_ROOT/.safeline-smoke-install"
FAILURES=0

pass() { printf '[PASS] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*" >&2; FAILURES=$((FAILURES + 1)); }

check_service() {
    local service="$1"
    local restarts
    if systemctl is-active --quiet "$service"; then
        pass "$service is active"
    else
        fail "$service is not active"
        return
    fi
    restarts=$(systemctl show "$service" --property=NRestarts --value 2>/dev/null || echo unknown)
    if [[ "$restarts" =~ ^[0-9]+$ ]] && [ "$restarts" -le 5 ]; then
        pass "$service automatic restarts=$restarts"
    else
        fail "$service restart count is suspicious: $restarts"
    fi
}

check_tcp_port() {
    local port="$1"
    if ss -H -lnt | awk '{print $4}' | grep -Eq "(^|:)${port}$"; then
        pass "TCP port $port is listening"
    else
        fail "TCP port $port is not listening"
    fi
}

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo/root" >&2; exit 1; }
[ -f "$MARKER" ] || { echo "Missing $MARKER" >&2; exit 1; }
source "$INSTALL_ROOT/smoke-test/components.lock"

MARKED_COMMIT=$(sed -n 's/^manager_commit=//p' "$MARKER")
ACTUAL_COMMIT=$(git -C "$INSTALL_ROOT" rev-parse HEAD 2>/dev/null || true)
[ -n "$MARKED_COMMIT" ] && [ "$ACTUAL_COMMIT" = "$MARKED_COMMIT" ] && pass "Manager commit matches smoke marker: $ACTUAL_COMMIT" || \
    fail "Manager commit does not match smoke marker"
[ "$(git -C "$INSTALL_ROOT" remote get-url origin 2>/dev/null)" = "https://github.com/Pay4eck/SafeLine-Manager.git" ] && \
    pass "Manager origin is Pay4eck/SafeLine-Manager" || fail "Manager origin is unexpected"

ACTUAL_PANEL_COMMIT=$(git -C "$INSTALL_ROOT/hiddify-panel/src" rev-parse HEAD 2>/dev/null || true)
[ "$ACTUAL_PANEL_COMMIT" = "$PANEL_COMMIT" ] && pass "Panel commit is $PANEL_COMMIT" || fail "Panel commit is not pinned"
[ "$("$INSTALL_ROOT/.venv313/bin/python" --version 2>/dev/null)" = "Python $PYTHON_VERSION" ] && \
    pass "Panel Python is $PYTHON_VERSION" || fail "Panel Python is not $PYTHON_VERSION"
[ ! -e /etc/cron.d/hiddify_auto_update ] && pass "automatic update cron is absent" || fail "automatic update cron exists"
if printf '%s  %s\n' "$PACKAGES_LOCK_SHA256" "$INSTALL_ROOT/common/packages.lock" | sha256sum --check --status && \
   printf '%s  %s\n' "$PANEL_UV_LOCK_SHA256" "$INSTALL_ROOT/hiddify-panel/src/uv.lock" | sha256sum --check --status; then
    pass "Manager and Panel dependency locks match components.lock"
else
    fail "Manager or Panel dependency lock changed"
fi

bash "$INSTALL_ROOT/update.sh" --no-gui --no-log >/tmp/safeline-update-guard.log 2>&1
UPDATE_GUARD_RC=$?
[ "$UPDATE_GUARD_RC" -eq 78 ] && pass "SafeLine update channel is disabled (exit 78)" || \
    fail "update.sh returned $UPDATE_GUARD_RC instead of 78"

for service in \
    hiddify-panel.service \
    hiddify-panel-background-tasks.service \
    hiddify-nginx.service \
    hiddify-haproxy.service \
    hiddify-xray.service \
    hiddify-singbox.service \
    hiddify-redis.service \
    mariadb.service; do
    check_service "$service"
done

check_tcp_port 80
check_tcp_port 443
check_tcp_port 9000

XRAY_BIN="$INSTALL_ROOT/xray/bin/xray"
if [ -x "$XRAY_BIN" ] && "$XRAY_BIN" version | head -n 1 | grep -Fq "$XRAY_VERSION"; then
    pass "Xray version is $XRAY_VERSION"
else
    fail "Xray version is not $XRAY_VERSION"
fi
[ "$(sed -n 's/^xray|//p' "$INSTALL_ROOT/common/packages.db" 2>/dev/null | tail -n 1)" = "$XRAY_VERSION" ] && \
    pass "installed-package database pins Xray $XRAY_VERSION" || fail "installed-package database does not pin Xray $XRAY_VERSION"
[ "$(sed -n 's/^singbox|//p' "$INSTALL_ROOT/common/packages.db" 2>/dev/null | tail -n 1)" = "$SINGBOX_VERSION" ] && \
    pass "installed-package database pins Sing-box/Hiddify Core $SINGBOX_VERSION" || fail "installed-package database does not pin Sing-box/Hiddify Core $SINGBOX_VERSION"

echo "[INFO] Xray validation command: XRAY_LOCATION_ASSET=$INSTALL_ROOT/xray/bin $XRAY_BIN run -test -confdir $INSTALL_ROOT/xray/configs/"
if XRAY_LOCATION_ASSET="$INSTALL_ROOT/xray/bin" "$XRAY_BIN" run -test -confdir "$INSTALL_ROOT/xray/configs/" >/tmp/safeline-xray-test.log 2>&1; then
    pass "Xray configuration test succeeded"
else
    fail "Xray configuration test failed; inspect /tmp/safeline-xray-test.log on this test VPS"
fi

if grep -Rqs '"protocol"[[:space:]]*:[[:space:]]*"vless"' "$INSTALL_ROOT/xray/configs" && \
   grep -Rqs '"security"[[:space:]]*:[[:space:]]*"reality"' "$INSTALL_ROOT/xray/configs"; then
    pass "rendered VLESS Reality inbound exists"
else
    fail "rendered VLESS Reality inbound is missing"
fi
grep -Rqs 'xtls-rprx-vision' "$INSTALL_ROOT/xray/configs" && pass "xtls-rprx-vision exists" || fail "xtls-rprx-vision is missing"

mapfile -t XRAY_UUIDS < <(jq -r '.. | objects | .clients? // empty | .[] | .id? // empty' "$INSTALL_ROOT"/xray/configs/*.json 2>/dev/null)
INVALID_UUIDS=0
for candidate_uuid in "${XRAY_UUIDS[@]}"; do
    "$INSTALL_ROOT/.venv313/bin/python" -c 'import sys, uuid; uuid.UUID(sys.argv[1])' "$candidate_uuid" >/dev/null 2>&1 || \
        INVALID_UUIDS=$((INVALID_UUIDS + 1))
done
if [ "${#XRAY_UUIDS[@]}" -gt 0 ] && [ "$INVALID_UUIDS" -eq 0 ]; then
    pass "all rendered Xray user UUIDs are syntactically valid"
else
    fail "rendered Xray user UUIDs are missing or invalid"
fi

REALITY_PRIVATE_KEY=$(jq -r '.. | objects | .realitySettings?.privateKey? // empty' "$INSTALL_ROOT"/xray/configs/*.json 2>/dev/null | head -n 1)
if [ -n "$REALITY_PRIVATE_KEY" ] && "$XRAY_BIN" x25519 -i "$REALITY_PRIVATE_KEY" >/dev/null 2>&1; then
    pass "Reality private key is accepted by Xray"
else
    fail "Reality private key is absent or invalid"
fi

SHORT_ID_COUNT=$(jq -r '.. | objects | .realitySettings?.shortIds? // empty | .[]' "$INSTALL_ROOT"/xray/configs/*.json 2>/dev/null | wc -l)
[ "$SHORT_ID_COUNT" -gt 0 ] && pass "Reality shortIds are present" || fail "Reality shortIds are missing"
SERVER_NAME_COUNT=$(jq -r '.. | objects | .realitySettings?.serverNames? // empty | .[]' "$INSTALL_ROOT"/xray/configs/*.json 2>/dev/null | wc -l)
[ "$SERVER_NAME_COUNT" -gt 0 ] && pass "Reality serverNames are present" || fail "Reality serverNames are missing"

HTTP_STATUS=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' http://127.0.0.1/ 2>/dev/null || echo 000)
if [[ "$HTTP_STATUS" =~ ^[1-4][0-9][0-9]$ ]]; then
    pass "local web entry point returned HTTP $HTTP_STATUS (not 5xx)"
else
    fail "local web entry point returned HTTP $HTTP_STATUS"
fi

if [ "$FAILURES" -ne 0 ]; then
    echo "$FAILURES automated smoke precheck(s) failed." >&2
    exit 1
fi

echo "Automated installation checks passed. Real browser, user lifecycle, client connection, traffic, disable, and reboot checks remain mandatory."
