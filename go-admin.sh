#!/bin/bash
COMMAND="$1"
shift 1
export PYTHONPATH=.:$PYTHONPATH
django-admin.py "$COMMAND" --settings=go.settings "$@"