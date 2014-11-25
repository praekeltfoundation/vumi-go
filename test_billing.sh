export VUMITEST_REDIS_DB=1
export VUMIGO_TEST_DB=postgres
export VUMI_TEST_TIMEOUT=10
export PYTHONPATH=.
export DJANGO_SETTINGS_MODULE=go.testsettings
export SANDBOX_NODE_PATH=$PWD/node_modules

py.test --tb=native -s go/billing/tests/test_models.py::TestLowCreditNotification