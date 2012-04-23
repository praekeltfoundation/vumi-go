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
./go-admin.sh test --nocapture --with-coverage --cover-package=go --with-xunit && \
coverage run ve/bin/trial go/vumitools/ && \
coverage xml --include="go/*" && \
coverage html --include="go/*" && \
(find ./go -name '*.py' | xargs pep8 --exclude='0*' > pep8.log || true) && \
cat pep8.log && \
deactivate
