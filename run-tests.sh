#!/bin/bash
virtualenv --no-site-packages ve && \
source ve/bin/activate && \
    pip install -r requirements.pip && \
    find ./go -name '*.pyc' -delete && \
    python go/manage.py test --with-coverage --cover-package=go --with-xunit && \
    coverage xml --include="go/*" && \
    coverage html --include="go/*" && \
    (pyflakes go/ > pyflakes.log || true) && \
    (pep8 go/ > pep8.log || true) && \
deactivate
