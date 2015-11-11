#!/bin/sh

BINS='grunt bower uglify'
PROJECT_ROOT=$(cd "`dirname $0`/.."; pwd)

link () {
    src="$PROJECT_ROOT/node_modules/.bin/$1"
    dest="$VIRTUAL_ENV/bin/$1"
    ln -s $src $dest  2> /dev/null || echo "Skipping $1, symlink already exists."
}


if [ -n $VIRTUAL_ENV ]; then
    for bin in $BINS
    do
        link $bin
    done
fi
