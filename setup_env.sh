#!/bin/bash

# To die on the first error instead of carrying on.
set -e


setup_db() {
    ./go-admin.sh syncdb --migrate --noinput
}

setup_environment() {
    ./go-admin.sh go_setup_env \
        --config-file=./setup_env/config.yaml \
	    --tagpool-file=./setup_env/tagpools.yaml \
	    --account-file=./setup_env/accounts.yaml \
	    --conversation-file=./setup_env/conversations.yaml \
	    --transport-file=./setup_env/transports.yaml \
        --application-file=./setup_env/applications.yaml
}

setup_groups_and_contacts() {
    local user=$1; shift
    local group=$1; shift
    local contacts=$1; shift

    group_key=$(
        ./go-admin.sh go_manage_contact_group \
            --email-address $user@example.org --create --group $group \
            | grep -o '^ \* [^ ]\+' | cut -c4-
    )

    ./go-admin.sh go_import_contacts --email-address $user@example.org \
        --contacts $contacts --group $group_key
}


setup_db
setup_environment
setup_groups_and_contacts user1 group1 ./setup_env/contacts.csv
setup_groups_and_contacts user2 group2 ./setup_env/contacts.csv
