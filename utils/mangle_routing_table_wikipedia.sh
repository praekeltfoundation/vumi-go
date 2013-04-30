#!/bin/bash

if [ $# -ne 3 ]; then
    echo "usage:"
    echo "  $0 <user email> <USSD conv key> <SMS conv key>"
    exit 1
fi

email_address="$1"
ussd_conv="CONVERSATION:wikipedia_ussd:$2"
sms_conv="CONVERSATION:wikipedia_sms:$3"

. $(dirname $0)/mangle_routing_table_utils.sh

assert_routing_exists $ussd_conv
assert_routing_exists $sms_conv

sms_tag=$(get_default_tag $sms_conv) || exit 1

# If any of these steps fail, stop immediately
set -e

mrt --remove $sms_conv default $sms_tag default
mrt --remove $sms_tag default $sms_conv default
mrt --add $ussd_conv sms_content $sms_tag default
mrt --add $sms_tag default $ussd_conv sms_content
