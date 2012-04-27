#!/bin/bash
if [ -d "ve" ]; then
    echo "Virtualenv already created"
else
    echo "Creating virtualenv"
    virtualenv --no-site-packages ve
fi

echo "Activating virtualenv"
source ve/bin/activate
hasher=$(which md5 or md5sum)
export DJANGO_SETTINGS_MODULE=go.settings
export PYTHONPATH=.

if [ -f 'requirements.pip.md5' ]; then
    current=$(cat requirements.pip | $hasher)
    cached=$(cat requirements.pip.md5)
    if [ "$current" = "$cached" ]; then
        echo "Requirements still up to date"
    else
        echo "Upgrading requirements"
        pip install --upgrade -r requirements.pip
        cat requirements.pip | $hasher > requirements.pip.md5
    fi
    true
else
    echo "Installing requirements"
    pip install -r requirements.pip && \
    cat requirements.pip | $hasher > requirements.pip.md5
fi

find ./go -name '*.pyc' -delete && \
coverage run --branch --include="go/*" ve/bin/django-admin.py test -evumitools && \
coverage run --branch --append --include="go/*" ve/bin/trial go/vumitools/ && \
coverage xml --include="go/*" && \
coverage html --include="go/*" && \
(find ./go -name '*.py' | xargs pep8 --repeat --exclude='0*' > pep8.log || true) && \
cat pep8.log && \
deactivate
