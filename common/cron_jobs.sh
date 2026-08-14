#!/bin/bash

daily_cron_error() {
    printf 'ERROR: %s\n' "$1" >&2
}

cleanup_daily_cron_temp() {
    local temp_path="$1"

    if [ -n "$temp_path" ] && { [ -e "$temp_path" ] || [ -L "$temp_path" ]; }; then
        if ! rm -f -- "$temp_path" >/dev/null 2>&1; then
            printf 'WARNING: unable to remove temporary cron file %s\n' "$temp_path" >&2
        fi
    fi
}

install_daily_cron() {
    local cron_dir="${HIDDIFY_CRON_DIR:-/etc/cron.d}"
    local manager_root="${HIDDIFY_MANAGER_ROOT:-/opt/hiddify-manager}"
    local legacy_path="$cron_dir/hiddify_daily_memory_release"
    local target_path="$cron_dir/hiddify_daily"
    local temp_path=""
    local rc=0

    if [ ! -d "$cron_dir" ]; then
        daily_cron_error "cron directory does not exist: $cron_dir"
        return 1
    fi

    if [ -e "$legacy_path" ] || [ -L "$legacy_path" ]; then
        rm -f -- "$legacy_path"
        rc=$?
        if [ "$rc" -ne 0 ]; then
            daily_cron_error "unable to remove legacy cron file: $legacy_path"
            return "$rc"
        fi
    fi

    temp_path="$(mktemp "$cron_dir/.hiddify_daily.XXXXXX")"
    rc=$?
    if [ "$rc" -ne 0 ] || [ -z "$temp_path" ]; then
        if [ "$rc" -eq 0 ]; then
            rc=1
        fi
        daily_cron_error "unable to create temporary daily cron file in $cron_dir"
        return "$rc"
    fi

    printf '@daily root %s/common/daily_actions.sh >> %s/log/system/daily_actions.log 2>&1\n' \
        "$manager_root" "$manager_root" >"$temp_path"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        daily_cron_error "unable to write daily cron file: $temp_path"
        cleanup_daily_cron_temp "$temp_path"
        return "$rc"
    fi

    chmod 0644 "$temp_path"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        daily_cron_error "unable to set daily cron file permissions: $temp_path"
        cleanup_daily_cron_temp "$temp_path"
        return "$rc"
    fi

    chown root:root "$temp_path"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        daily_cron_error "unable to set daily cron file ownership: $temp_path"
        cleanup_daily_cron_temp "$temp_path"
        return "$rc"
    fi

    mv -fT -- "$temp_path" "$target_path"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        daily_cron_error "unable to atomically install daily cron file: $target_path"
        cleanup_daily_cron_temp "$temp_path"
        return "$rc"
    fi

    service cron reload
    rc=$?
    if [ "$rc" -ne 0 ]; then
        daily_cron_error "unable to reload cron after installing $target_path"
        return "$rc"
    fi

    return 0
}
