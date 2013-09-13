#!/bin/bash

function mrt() {
    ./go-admin.sh go_manage_routing_table --email-address $email_address "$@"
}

function assert_routing_exists() {
    local conv=$1
    count=$(mrt --show | grep -c $conv)
    if [ $count -le 0 ]; then
        echo "No routing table entries found for $conv"
        exit 1
    fi
}

function get_default_tag() {
    local conv=$1
    tag=$(mrt --show | grep -A1 "^  $conv" | grep 'default' | sed 's/.*->  \(.*\) -.*/\1/')
    echo ${tag:?"Can't find tag for $conv"}
}
