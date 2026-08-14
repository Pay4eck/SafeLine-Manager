#!/bin/bash

parse_uv_semantic_version() {
    [ "$#" -eq 1 ] || return 2

    local uv_output="$1"
    local uv_version_pattern='^uv[[:space:]]+([0-9]+\.[0-9]+\.[0-9]+)([[:space:]]+\([^)]*\))?[[:space:]]*$'

    [[ "$uv_output" =~ $uv_version_pattern ]] || return 1
    printf '%s\n' "${BASH_REMATCH[1]}"
}
