#!/bin/sh -e

cd "$(dirname "$0")"

echo "=== Nuking old .pyc files..."
find go/ -name '*.pyc' -delete
find go/ -name '__pycache__' -delete
echo "=== Erasing previous coverage data..."
[ -z "$NO_COVERAGE" ] && coverage erase
echo "=== Running tests..."
export VUMI_TEST_NODE_PATH="$(which node)"
# This is necessary so that we import test modules from the working dir instead
# of the installed package.
export PYTHONPATH=.
[ -z "$NO_COVERAGE" ] && COVERAGE_ARGS="--cov=go"
VUMI_TEST_ASSERT_CLOSED=true ./run-tests-pytest.sh $COVERAGE_ARGS go --maxfail=100
echo "=== Checking for PEP-8 violations..."
pep8 --repeat go | grep -v '^go/\(base\|billing\)/\(auth_\|registration_\)\?migrations/' | tee pep8.txt
echo "=== Done."
