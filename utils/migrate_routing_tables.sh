#!/bin/bash

for email_address in $(./go-admin.sh go_list_accounts | sed 's/.*<\(.*\)>.*/\1/'); do
    echo -e "\nAccount email: $email_address"
    ./go-admin.sh go_manage_routing_table --email-address $email_address --show
done
