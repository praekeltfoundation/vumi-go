#!/bin/sh
npm install --prefix=$VIRTUAL_ENV -g `cat globals.npm | tr '\n' ' '`
npm install
