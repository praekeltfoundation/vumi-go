export DJANGO_SETTINGS_MODULE=go.testsettings
export SANDBOX_NODE_PATH=$PWD/node_modules
py.test --tb=native "$@"
