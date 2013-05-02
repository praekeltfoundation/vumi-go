#!/bin/bash

# To die on the first error instead of carrying on.
set -e

./go-admin.sh syncdb --migrate --noinput

./go-admin.sh go_setup_env \
    --config-file=./setup_env/config.yaml \
	--tagpool-file=./setup_env/tagpools.yaml \
	--account-file=./setup_env/accounts.yaml \
	--conversation-file=./setup_env/conversations.yaml \
	--transport-file=./setup_env/transports.yaml \
    --application-file=./setup_env/applications.yaml \
    --contact-group-file=./setup_env/contact_groups.yaml

echo "Please run ./setup_env/build/go_startup_env.sh to complete setup."
