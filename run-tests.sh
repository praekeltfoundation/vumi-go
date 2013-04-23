#!/bin/sh -e

cd "$(dirname "$0")"

echo "=== Nuking old .pyc files..."
find go/ -name '*.pyc' -delete
find go/ -name '__pycache__' -delete
echo "=== Erasing previous coverage data..."
coverage erase
echo "=== Running tests..."
# This is necessary so that we import test modules from the working dir instead
# of the installed package.
export PYTHONPATH=.
./run-tests-pytest.sh --junitxml=test_results.xml
# echo "=== Processing coverage data..."
# coverage xml
echo "=== Checking for PEP-8 violations..."
pep8 --repeat vumi | tee pep8.txt
echo "=== Done."
