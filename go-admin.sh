#!/bin/bash
COMMAND="$1"
shift 1
export PYTHONPATH=.:$PYTHONPATH
exec django-admin.py "$COMMAND" --settings=go.settings "$@"