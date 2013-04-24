#!/bin/bash

if [ $# -ne 3 ]; then
    echo "usage:"
    echo "  $0 <user email> <conv key> <tagpool:tagname>"
    exit 1
fi

email_address="$1"
conv="jsbox:$2"
tag="$3"

. $(dirname $0)/mangle_routing_table_utils.sh

assert_routing_exists "$conv"
assert_routing_exists "$tag"

mrt --add $conv $tag $tag default
