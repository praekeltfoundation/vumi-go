#!/bin/bash

# To die on the first error instead of carrying on.
set -e

./go-admin.sh syncdb --migrate --noinput

./go-admin.sh go_setup_env \
    --config-file=./setup_env/config.yaml \
	--tagpool-file=./setup_env/tagpools.yaml \
	--workers-file=./setup_env/workers.yaml \
	--account-setup-file=./setup_env/account_1.yaml \
	--account-setup-file=./setup_env/account_2.yaml \

echo "Please run ./setup_env/build/go_startup_env.sh to complete setup."
