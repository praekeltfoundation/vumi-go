#!/bin/sh

# NOTE: This assumes we're in an appropriate virtualenv.

find ./go -name '*.pyc' -delete

# These are expected to be Twisted tests that trial should run.
vumi_tests="go/vumitools `find ./go -name 'test*vumi_app*.py'`"

echo $COVERAGE_COMMAND

eval $COVERAGE_COMMAND `which trial` ${vumi_tests}
r1=$?
eval $COVERAGE_COMMAND `which django-admin.py` test --settings=go.testsettings
r2=$?

exit $(($r1 + $r2))
