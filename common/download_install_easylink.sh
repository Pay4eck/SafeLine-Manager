#!/bin/sh

echo "Disabled in SafeLine Manager 0.1: the easy-link bootstrap downloads Hiddify main." >&2
echo "Use smoke-test/install-pinned.sh with an exact Pay4eck/SafeLine-Manager commit." >&2
exit 78

export CREATE_EASYSETUP_LINK="true"
bash -c "$(curl -Lfo- https://raw.githubusercontent.com/hiddify/hiddify-manager/main/common/download_install.sh)"
