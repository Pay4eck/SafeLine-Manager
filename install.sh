#!/bin/bash
set -o pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 1
cd "$SCRIPT_DIR" || exit 1

if [ -f "/opt/hiddify-manager/.safeline-smoke-install" ]; then
    export SAFELINE_SMOKE_TEST_MODE=1
    export HIDDIFY_DISABLE_UPDATE=true
    export HIDDIFY_PANLE_SOURCE_DIR=/opt/hiddify-manager/hiddify-panel/src
    export UV_NO_SYSTEM_CONFIG=1
    export UV_PYTHON_INSTALL_DIR=/usr/local/share/uv/python
fi

source ./common/utils.sh
NAME="0-install"
# Fix the installation directory
if [ ! -d "/opt/hiddify-manager/" ] && [ -d "/opt/hiddify-server/" ]; then
    mv /opt/hiddify-server /opt/hiddify-manager
    ln -s /opt/hiddify-manager /opt/hiddify-server
fi
if [ ! -d "/opt/hiddify-manager/" ] && [ -d "/opt/hiddify-config/" ]; then
    mv /opt/hiddify-config/ /opt/hiddify-manager/
    ln -s /opt/hiddify-manager /opt/hiddify-config
fi

export DEBIAN_FRONTEND=noninteractive
function run_required_step() {
    local description="$1"
    shift
    local rc

    "$@"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        error "$description failed with exit status $rc"
        return "$rc"
    fi
    return 0
}

function main() {
    update_progress "Please wait..." "We are going to install Hiddify..." 0
    export ERROR=0
    
    export PROGRESS_ACTION="Installing..."
    if [ "$MODE" == "apply_users" ];then
        export DO_NOT_INSTALL="true"
    elif [ -d "/hiddify-data-default/" ] && [ -z "$(ls -A /hiddify-data/ 2>/dev/null)" ]; then
        cp -r /hiddify-data-default/* /hiddify-data/
    fi
    if [ "$DO_NOT_INSTALL" == "true" ];then
        PROGRESS_ACTION="Applying..."
    fi

    export USE_VENV=313

    run_required_step "Python installation" install_python || return $?
    run_required_step "Python virtual environment activation" activate_python_venv || return $?
    
    if [ "$MODE" != "apply_users" ]; then
        clean_files
        update_progress "${PROGRESS_ACTION}" "Common Tools and Requirements" 2
        run_required_step "Common prerequisites installation" runsh install.sh common || return $?
        if [ "$MODE" != "docker" ];then
            run_required_step "Redis installation" install_run other/redis || return $?
            run_required_step "MariaDB installation" install_run other/mysql || return $?
        fi
        # Because we need to generate reality pair in panel
        # is_installed xray || bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install --version 1.8.4
        
        run_required_step "Panel installation" install_run hiddify-panel || return $?

        if [[ "$SAFELINE_SMOKE_TEST_MODE" == "1" || "$SAFELINE_SMOKE_TEST_MODE" == "true" ]]; then
            run_required_step "SafeLine smoke profile configuration" bash ./smoke-test/configure-profile.sh || return $?
        fi
    fi
    
    # source common/set_config_from_hpanel.sh
    if [ "$DO_NOT_RUN" != "true" ];then
      update_progress "HiddifyPanel" "Reading Configs from Panel..." 5
      set_config_from_hpanel

      update_progress "Applying Configs" "..." 8

      bash common/replace_variables.sh
    fi
    
    if [ "$MODE" != "apply_users" ]; then
        run_required_step "Deprecated component cleanup" bash ./other/deprecated/remove_deprecated.sh || return $?
        update_progress "Configuring..." "System and Firewall settings" 10
        run_required_step "Common system configuration" runsh run.sh common || return $?
        
        update_progress "${PROGRESS_ACTION}" "Nginx" 15
        run_required_step "Nginx installation" install_run nginx || return $?
        
        update_progress "${PROGRESS_ACTION}" "Haproxy for Spliting Traffic" 20
        run_required_step "HAProxy installation" install_run haproxy || return $?
        
        update_progress "${PROGRESS_ACTION}" "Getting Certificates" 30
        if [[ "$SAFELINE_SMOKE_TEST_MODE" == "1" || "$SAFELINE_SMOKE_TEST_MODE" == "true" ]]; then
            echo "SafeLine smoke mode: skip the moving get.acme.sh bootstrap; local self-signed setup remains available."
        else
            run_required_step "ACME installation" install_run acme.sh || return $?
        fi
        
        update_progress "${PROGRESS_ACTION}" "Personal SpeedTest" 35
        run_required_step "Speedtest component" install_run other/speedtest "$(hconfig "speed_test")" || return $?

        update_progress "${PROGRESS_ACTION}" "dnstt Proxy" 40
        run_required_step "DNSTT component" install_run other/dnstt "$(hconfig "dnstt_enable")" || return $?

        update_progress "${PROGRESS_ACTION}" "Telegram Proxy" 40
        run_required_step "Telegram component" install_run other/telegram "$(hconfig "telegram_enable")" || return $?
        
        update_progress "${PROGRESS_ACTION}" "FakeTlS Proxy" 45
        run_required_step "FakeTLS component" install_run other/ssfaketls "$(hconfig "ssfaketls_enable")" || return $?
        
        # update_progress "${PROGRESS_ACTION}" "V2ray WS Proxy" 50
        # install_run other/v2ray $ENABLE_V2RAY
        
        update_progress "${PROGRESS_ACTION}" "SSH Proxy" 55
        run_required_step "SSH proxy component" install_run other/ssh 0 || return $?
        
        #update_progress "${PROGRESS_ACTION}" "ShadowTLS" 60
        #install_run other/shadowtls $(hconfig "shadowtls_enable")
        
        update_progress "${PROGRESS_ACTION}" "Warp" 70
        
        if [[ $(hconfig "warp_mode") != "disable" ]];then
            run_required_step "WARP component" install_run other/warp 1 || return $?
        else   
            run_required_step "WARP component disable" install_run other/warp 0 || return $?
        fi

        update_progress "${PROGRESS_ACTION}" "Xray" 75
        
        run_required_step "Xray installation" install_run xray 1 || return $?
        
        
        update_progress "${PROGRESS_ACTION}" "HiddifyCli" 80
        run_required_step "CLI component" install_run other/hiddify-cli "$(hconfig "hiddifycli_enable")" || return $?
        
    fi


    update_progress "${PROGRESS_ACTION}" "Wireguard" 85
    run_required_step "WireGuard component" install_run other/wireguard "$(hconfig "wireguard_enable")" || return $?
    
    update_progress "${PROGRESS_ACTION}" "Singbox" 95
    run_required_step "Sing-box installation" install_run singbox || return $?
    
    update_progress "${PROGRESS_ACTION}" "Almost Finished" 98
    echo "---------------------Finished!------------------------"
    remove_lock $NAME
    if [ "$MODE" != "apply_users" ]; then
        systemctl kill -s SIGTERM hiddify-panel
    fi
    run_required_step "Panel service start" systemctl start hiddify-panel || return $?
    update_progress "${PROGRESS_ACTION}" "Done" 100
    
}

function clean_files() {
    rm -rf log/system/xray*
    rm -rf /opt/hiddify-manager/xray/configs/*.json
    rm -rf /opt/hiddify-manager/singbox/configs/*.json
    rm -rf /opt/hiddify-manager/haproxy/*.cfg
    find ./ -type f -name "*.template" -exec rm -f {} \;
}

function cleanup() {
    error "Script interrupted. Exiting..."
    # disable_ansii_modes
    remove_lock $NAME
    exit 9
}

# Trap the Ctrl+C signal and call the cleanup function
trap cleanup SIGINT

function set_config_from_hpanel() {
    reload_all_configs >/dev/null
    if [[ $? != 0 ]]; then
        error "Exception in Hiddify Panel. Please send the log to hiddify@gmail.com"
        exit 4
    fi
    
    export SERVER_IP=$(curl --connect-timeout 1 -s https://v4.ident.me/)
    export SERVER_IPv6=$(curl --connect-timeout 1 -s https://v6.ident.me/)
}

function install_run() {
    local rc

    echo "======================$1====================================={"
    if [ "$DO_NOT_INSTALL" != "true" ];then
        runsh install.sh "$@"
        rc=$?
        if [ "$rc" -ne 0 ]; then
            error "$1 install.sh failed with exit status $rc"
            return "$rc"
        fi
        if [ "$MODE" != "apply_users" ] && [ "$MODE" != "docker"  ]; then
            systemctl daemon-reload || return $?
        fi
    fi
    if [ "$DO_NOT_RUN" != "true" ];then
        runsh run.sh "$@"
        rc=$?
        if [ "$rc" -ne 0 ]; then
            error "$1 run.sh failed with exit status $rc"
            return "$rc"
        fi
    fi
    echo "}========================$1==================================="
    return 0
}

function runsh() {
    local command=$1
    local component_dir=$2
    local rc=0
    local popd_rc=0

    if [[ ${3:-} == "false" || ${3:-} == "0" ]]; then
        command=disable.sh
    fi

    pushd "$component_dir" >>/dev/null || return $?
    if [ -f "$command" ]; then
        echo "===$command $component_dir"
        bash "$command"
        rc=$?
    fi
    popd >>/dev/null || popd_rc=$?

    if [ "$rc" -ne 0 ]; then
        return "$rc"
    fi
    return "$popd_rc"
}

function installer_entrypoint() {
    local error_code

    if [ "$(id -u)" -ne 0 ]; then
        echo 'This script must be run by root' >&2
        return 1
    fi
    LOG_FILE="$(log_file "$NAME")"

    if [[ " $@ " == *" --no-gui "* ]]; then
        set -- "${@/--no-gui/}"
        export MODE="$1"
        set_lock "$NAME"
        if [[ " $@ " == *" --no-log "* ]]; then
            set -- "${@/--no-log/}"
            main
        else
            main |& tee "$LOG_FILE"
        fi
        error_code=$?
        remove_lock "$NAME"
    else
        show_progress_window --subtitle "$(get_installed_config_version)" --log "$LOG_FILE" ./install.sh "$@" --no-gui --no-log
        error_code=$?
        if [[ $error_code != "0" ]]; then
            msg_with_hiddify "Installation Failed! $error_code"
        else
            msg_with_hiddify "The installation has successfully completed."
            check_hiddify_panel "$@" |& tee -a "$LOG_FILE"
        fi
    fi

    return "$error_code"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    installer_entrypoint "$@"
    exit $?
fi
