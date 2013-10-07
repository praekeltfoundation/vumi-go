#!/bin/sh

BINS='grunt bower yuglify'
PROJECT_ROOT=$(cd "`dirname $0`/.."; pwd)

if [ -n $VIRTUAL_ENV ]; then
  for bin in $BINS
  do
    ln -si $PROJECT_ROOT/node_modules/.bin/$bin $VIRTUAL_ENV/bin/$bin
  done
fi
