#!/bin/sh

psql -c "create user go with createdb password 'go';" -U postgres
psql -c 'create database go owner go;' -U postgres
django-admin.py syncdb --migrate --noinput --settings=go.testsettings
