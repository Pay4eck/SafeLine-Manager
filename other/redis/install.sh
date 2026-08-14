#!/bin/bash

REDIS_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 1
REDIS_MANAGER_ROOT="$(cd -- "$REDIS_SCRIPT_DIR/../.." && pwd)" || exit 1
source "$REDIS_MANAGER_ROOT/common/utils.sh"

redis_package_installed() {
    [ "$(dpkg-query -W -f='${Status}' redis-server 2>/dev/null)" = "install ok installed" ]
}

redis_server_available() {
    command -v redis-server >/dev/null 2>&1
}

redis_user_available() {
    getent passwd redis >/dev/null 2>&1
}

redis_group_available() {
    getent group redis >/dev/null 2>&1
}

verify_redis_package() {
    redis_package_installed || {
        error "redis-server package is not installed"
        return 1
    }
    redis_server_available || {
        error "redis-server binary is missing after package installation"
        return 1
    }
    redis_user_available || {
        error "redis user is missing after package installation"
        return 1
    }
    redis_group_available || {
        error "redis group is missing after package installation"
        return 1
    }
    return 0
}

install_redis_package() {
    if ! redis_package_installed; then
        add-apt-repository -y universe || return $?
    fi
    install_package redis-server || return $?
    verify_redis_package
}

stop_distribution_redis() {
    systemctl disable --now redis-server >/dev/null 2>&1 || true
    pkill -9 redis-server >/dev/null 2>&1 || true
}

prepare_redis_files() {
    local log_dir="$REDIS_MANAGER_ROOT/log/system"
    local log_file="$log_dir/redis-server.log"
    local redis_config="$REDIS_SCRIPT_DIR/redis.conf"
    local random_password

    mkdir -p "$log_dir" || return $?
    touch "$log_file" || return $?
    chown redis:redis "$log_file" || return $?
    chmod 0640 "$log_file" || return $?

    chown -R redis:redis "$REDIS_SCRIPT_DIR" || return $?
    chmod 0600 "$redis_config" || return $?

    if ! grep -q '^requirepass[[:space:]]' "$redis_config"; then
        random_password=$(< /dev/urandom tr -dc 'a-zA-Z0-9' | head -c49)
        [ -n "$random_password" ] || {
            error "failed to generate Redis password"
            return 1
        }
        printf 'requirepass %s\n' "$random_password" >>"$redis_config" || return $?
    fi

    ln -sf "$REDIS_SCRIPT_DIR/hiddify-redis.service" /etc/systemd/system/hiddify-redis.service || return $?
    return 0
}

start_redis_service() {
    systemctl daemon-reload || return $?
    systemctl enable --now hiddify-redis || return $?
}

redis_listens_on_localhost() {
    ss -H -lnt 2>/dev/null | awk '$4 == "127.0.0.1:6379" { found=1 } END { exit !found }'
}

redis_authenticated_ping() {
    local redis_password
    local response

    if ! command -v redis-cli >/dev/null 2>&1; then
        warning "redis-cli is unavailable; authenticated readiness PING is skipped"
        return 0
    fi

    redis_password=$(awk '$1 == "requirepass" { print $2; exit }' "$REDIS_SCRIPT_DIR/redis.conf")
    [ -n "$redis_password" ] || return 1
    response=$(REDISCLI_AUTH="$redis_password" redis-cli --no-auth-warning -h 127.0.0.1 -p 6379 ping 2>/dev/null) || return 1
    [ "$response" = "PONG" ]
}

redis_is_ready() {
    systemctl is-active --quiet hiddify-redis || return 1
    redis_listens_on_localhost || return 1
    redis_authenticated_ping || return 1
}

wait_for_redis_readiness() {
    local attempt

    for attempt in $(seq 1 20); do
        redis_is_ready && return 0
        sleep 1
    done
    error "hiddify-redis did not become ready on 127.0.0.1:6379"
    return 1
}

redis_install_main() {
    install_redis_package || return $?
    verify_redis_package || return $?
    stop_distribution_redis
    prepare_redis_files || return $?
    start_redis_service || return $?
    wait_for_redis_readiness || return $?
    return 0
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    redis_install_main
    exit $?
fi
