#!/bin/sh

PROJECT_ROOT="`dirname $0`/../"
npm install --prefix=$VIRTUAL_ENV -g `cat $PROJECT_ROOT/globals.npm | tr '\n' ' '`
npm install
