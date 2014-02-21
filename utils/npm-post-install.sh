#!/bin/sh

BINS='grunt bower yuglify'
PROJECT_ROOT=$(cd "`dirname $0`/.."; pwd)

function make_links {
    if [ -n $VIRTUAL_ENV ]; then
        for bin in $BINS
        do
            ln -s $PROJECT_ROOT/node_modules/.bin/$bin $VIRTUAL_ENV/bin/$bin
        done
    fi
}

make_links || :
