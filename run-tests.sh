#!/bin/sh -e

cd "$(dirname "$0")"

echo "=== Nuking old .pyc files..."
find go/ -name '*.pyc' -delete
find go/ -name '__pycache__' -delete
echo "=== Erasing previous coverage data..."
coverage erase
echo "=== Running tests..."
export VUMI_TEST_NODE_PATH="$(which node)"
# This is necessary so that we import test modules from the working dir instead
# of the installed package.
export PYTHONPATH=.
if [ -z "$NO_COVERAGE" ]; then
    COVERAGE="--cov=go"
else
    COVERAGE=""
fi
./run-tests-pytest.sh $COVERAGE go/
echo "=== Checking for PEP-8 violations..."
pep8 --repeat go | grep -v '^go/\(base\|billing\)/\(auth_\|registration_\)\?migrations/' | tee pep8.txt
echo "=== Done."
