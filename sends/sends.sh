#!/bin/bash

password=$1

cd /var/praekelt/vumi-go && \
    source ve/bin/activate && \
    cd sends && \
    PYTHONPATH=.. python sends.py --config=../config/multipoll.yaml --account=19c21ba18f654afeb80d1d4e5df904a4 --conversation=b85c82cc82854f8faffb31facd90f19c --username=mama --password=$password --live=1 | mail -s "MAMA SMS sends on `date`" david@praekeltfoundation.org && \
    deactivate
