export DJANGO_SETTINGS_MODULE=go.testsettings
export SANDBOX_NODE_PATH=$PWD/node_modules
PYTESTARGS="--tb=native"
if [ $VUMIGO_SKIP_DJANGO ]; then
    PYTESTARGS="$PYTESTARGS -p no:django"
fi
py.test $PYTESTARGS "$@"
