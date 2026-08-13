#!/bin/bash
set -euo pipefail

readonly SAFELINE_REPOSITORY="https://github.com/Pay4eck/SafeLine-Manager.git"
readonly INSTALL_ROOT="/opt/hiddify-manager"
readonly MARKER="$INSTALL_ROOT/.safeline-smoke-install"

usage() {
    cat <<'EOF'
Usage: sudo bash install-pinned.sh --commit <40-character SafeLine commit>

Installs one detached Pay4eck/SafeLine-Manager commit on a disposable,
fresh Ubuntu Server 24.04 LTS amd64 VPS. Branch names and moving tags are not
accepted.
EOF
}

die() {
    echo "ERROR: $*" >&2
    exit 1
}

cleanup_bootstrap_tmp() {
    case "${BOOTSTRAP_TMP:-}" in
        /tmp/tmp.*)
            [ ! -d "$BOOTSTRAP_TMP" ] || rm -rf -- "$BOOTSTRAP_TMP"
            ;;
    esac
}

require_empty_test_host() {
    [ ! -e "$INSTALL_ROOT" ] || die "$INSTALL_ROOT already exists; refusing to touch a possibly real installation"
    [ ! -e /opt/hiddify-config ] || die "/opt/hiddify-config already exists; refusing to migrate or overwrite it"
    [ ! -e /opt/hiddify-server ] || die "/opt/hiddify-server already exists; refusing to migrate or overwrite it"

    local inherited_units
    inherited_units=$(systemctl list-unit-files --type=service --no-legend 2>/dev/null | awk '$1 ~ /^hiddify-/ {print $1}')
    [ -z "$inherited_units" ] || die "inherited Hiddify services already exist: $inherited_units"

    if command -v ss >/dev/null 2>&1; then
        ! ss -H -lnt | awk '{print $4}' | grep -Eq '(^|:)(80|443)$' || \
            die "TCP port 80 or 443 is already listening; use a clean disposable VPS"
    fi
}

install_pinned_uv() {
    local archive="$BOOTSTRAP_TMP/uv.tar.gz"
    local extract_dir="$BOOTSTRAP_TMP/uv"

    curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error \
        --retry 3 --output "$archive" "$UV_AMD64_URL"
    printf '%s  %s\n' "$UV_AMD64_SHA256" "$archive" | sha256sum --check --status || \
        die "uv $UV_VERSION checksum mismatch"

    mkdir -p "$extract_dir"
    tar -xzf "$archive" -C "$extract_dir"
    [ -f "$extract_dir/uv-x86_64-unknown-linux-gnu/uv" ] || die "unexpected uv archive layout"
    install -m 0755 "$extract_dir/uv-x86_64-unknown-linux-gnu/uv" /usr/local/bin/uv
    [ "$(uv --version)" = "uv $UV_VERSION" ] || die "installed uv version does not match $UV_VERSION"
}

COMMIT=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --commit)
            [ "$#" -ge 2 ] || die "--commit requires a value"
            COMMIT="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
done

[ "$(id -u)" -eq 0 ] || die "run this installer with sudo/root"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "--commit must be an exact lowercase 40-character Git commit"
[ -r /etc/os-release ] || die "cannot identify the operating system"
source /etc/os-release
[ "${ID:-}" = "ubuntu" ] && [ "${VERSION_ID:-}" = "24.04" ] || \
    die "the first smoke test supports only Ubuntu Server 24.04 LTS"
[ "$(dpkg --print-architecture)" = "amd64" ] || die "the first smoke test supports only amd64"
[ "$(ps -p 1 -o comm= | tr -d ' ')" = "systemd" ] || die "systemd must be PID 1"

require_empty_test_host

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
    build-essential ca-certificates clang curl default-libmysqlclient-dev git \
    jq libev-dev libevdev2 pkg-config tar

git init "$INSTALL_ROOT"
git -C "$INSTALL_ROOT" remote add origin "$SAFELINE_REPOSITORY"
git -C "$INSTALL_ROOT" fetch --no-tags --depth=1 origin "$COMMIT"
git -C "$INSTALL_ROOT" checkout --detach FETCH_HEAD

ACTUAL_COMMIT=$(git -C "$INSTALL_ROOT" rev-parse HEAD)
[ "$ACTUAL_COMMIT" = "$COMMIT" ] || die "fetched Manager commit $ACTUAL_COMMIT instead of $COMMIT"
[ "$(git -C "$INSTALL_ROOT" remote get-url origin)" = "$SAFELINE_REPOSITORY" ] || die "unexpected Manager origin"

source "$INSTALL_ROOT/smoke-test/components.lock"

PINNED_GITLINK=$(git -C "$INSTALL_ROOT" ls-tree HEAD hiddify-panel/src | awk '{print $3}')
[ "$PINNED_GITLINK" = "$PANEL_COMMIT" ] || die "Panel gitlink does not match components.lock"
git -C "$INSTALL_ROOT" submodule sync --recursive
git -C "$INSTALL_ROOT" submodule update --init --recursive
ACTUAL_PANEL_COMMIT=$(git -C "$INSTALL_ROOT/hiddify-panel/src" rev-parse HEAD)
[ "$ACTUAL_PANEL_COMMIT" = "$PANEL_COMMIT" ] || die "Panel checkout does not match $PANEL_COMMIT"
[ "$(git -C "$INSTALL_ROOT" config --file .gitmodules --get submodule.hiddify-panel/src.url)" = "$PANEL_REPOSITORY" ] || \
    die "unexpected Panel repository"

printf '%s  %s\n' "$PACKAGES_LOCK_SHA256" "$INSTALL_ROOT/common/packages.lock" | sha256sum --check --status || \
    die "common/packages.lock checksum mismatch"
printf '%s  %s\n' "$PANEL_UV_LOCK_SHA256" "$INSTALL_ROOT/hiddify-panel/src/uv.lock" | sha256sum --check --status || \
    die "Panel uv.lock checksum mismatch"
grep -Fqx "xray|$XRAY_VERSION|amd64|https://github.com/XTLS/Xray-core/releases/download/v$XRAY_VERSION/Xray-linux-64.zip|$XRAY_AMD64_SHA256" \
    "$INSTALL_ROOT/common/packages.lock" || die "pinned Xray row is missing"
grep -Fqx "singbox|$SINGBOX_VERSION|amd64|https://github.com/hiddify/hiddify-core/releases/download/v$SINGBOX_VERSION/hiddify-core-linux-amd64.tar.gz|$SINGBOX_AMD64_SHA256" \
    "$INSTALL_ROOT/common/packages.lock" || die "pinned sing-box/Hiddify Core row is missing"

for geo_database in GeoLite2-ASN.mmdb GeoLite2-Country.mmdb; do
    case "$geo_database" in
        GeoLite2-ASN.mmdb) geo_digest="$GEOLITE_ASN_SHA256" ;;
        GeoLite2-Country.mmdb) geo_digest="$GEOLITE_COUNTRY_SHA256" ;;
    esac
    geo_path="$INSTALL_ROOT/hiddify-panel/$geo_database"
    curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error \
        --retry 3 --output "$geo_path" \
        "https://raw.githubusercontent.com/P3TERX/GeoLite.mmdb/$GEOLITE_REPOSITORY_COMMIT/$geo_database"
    printf '%s  %s\n' "$geo_digest" "$geo_path" | sha256sum --check --status || \
        die "$geo_database checksum mismatch"
done

BOOTSTRAP_TMP=$(mktemp -d)
case "$BOOTSTRAP_TMP" in
    /tmp/tmp.*) ;;
    *) die "mktemp returned an unexpected path: $BOOTSTRAP_TMP" ;;
esac
trap cleanup_bootstrap_tmp EXIT
install_pinned_uv

UV_PYTHON_INSTALL_DIR=/usr/local/share/uv/python uv python install "$PYTHON_VERSION"
UV_PYTHON_INSTALL_DIR=/usr/local/share/uv/python uv venv \
    "$INSTALL_ROOT/.venv313" --python "$PYTHON_VERSION"
UV_NO_SYSTEM_CONFIG=1 \
UV_PYTHON_INSTALL_DIR=/usr/local/share/uv/python \
UV_PROJECT_ENVIRONMENT="$INSTALL_ROOT/.venv313" \
    uv sync --frozen --no-dev --project "$INSTALL_ROOT/hiddify-panel/src"
[ "$("$INSTALL_ROOT/.venv313/bin/python" --version)" = "Python $PYTHON_VERSION" ] || \
    die "Panel Python does not match $PYTHON_VERSION"

install -m 0600 /dev/null "$MARKER"
{
    echo "mode=pinned-smoke-test"
    echo "repository=$SAFELINE_REPOSITORY"
    echo "manager_commit=$COMMIT"
    echo "panel_repository=$PANEL_REPOSITORY"
    echo "panel_commit=$PANEL_COMMIT"
    echo "panel_version=$PANEL_VERSION"
    echo "python_version=$PYTHON_VERSION"
    echo "geolite_commit=$GEOLITE_REPOSITORY_COMMIT"
    echo "automatic_updates=disabled"
} >"$MARKER"

export SAFELINE_SMOKE_TEST_MODE=1
export HIDDIFY_DISABLE_UPDATE=true
export HIDDIFY_PANLE_SOURCE_DIR="$INSTALL_ROOT/hiddify-panel/src"
export UV_NO_SYSTEM_CONFIG=1
export UV_PYTHON_INSTALL_DIR=/usr/local/share/uv/python

cd "$INSTALL_ROOT"
bash ./install.sh --no-gui --no-log

[ "$(git rev-parse HEAD)" = "$COMMIT" ] || die "Manager checkout changed during installation"
[ -f "$MARKER" ] || die "smoke-test update marker disappeared"
[ ! -e /etc/cron.d/hiddify_auto_update ] || die "automatic update cron must not exist"

bash ./smoke-test/verify-install.sh

cat <<EOF

Pinned SafeLine smoke installation completed for:
  Manager: $COMMIT
  Panel:   $PANEL_COMMIT ($PANEL_VERSION)

Do not paste current.json, subscription URLs, UUIDs, Reality private keys,
database passwords, or administrator URLs into an issue or chat.
Read docs/LINUX_SMOKE_TEST.md before continuing with the browser/client checks.
EOF
