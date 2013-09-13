#!/bin/bash
rabbitmqctl add_user vumi vumi
rabbitmqctl add_vhost /go
rabbitmqctl set_permissions -p /go vumi '.*' '.*' '.*'

