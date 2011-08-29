#!/bin/bash
virtualenv --no-site-packages ve && \
source ve/bin/activate && \
    pip install -r requirements.pip && \
    find ./go -name '*.pyc' -delete && \
    python go/manage.py test --with-coverage --cover-package=go --with-xunit && \
    coverage xml --include="go/*" && \
    coverage html --include="go/*" && \
    (find ./go -name '*.py' | xargs pep8 --exclude='0*' > pep8.log || true) && \
    cat pep8.log && \
deactivate
