#!/bin/bash
./go-admin.sh syncdb --migrate --noinput && \
./go-admin.sh go_setup_env --config-file=./setup_env/config.yaml \
	--tagpool-file=./setup_env/tagpools.yaml \
	--account-file=./setup_env/accounts.yaml \
	--conversation-file=./setup_env/conversations.yaml \
	--transport-file=./setup_env/transports.yaml \
    --application-file=./setup_env/applications.yaml