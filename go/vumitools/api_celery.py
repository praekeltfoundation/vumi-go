# -*- test-case-name: go.vumitools.tests.test_api_celery -*-
# -*- coding: utf-8 -*-

"""Celery tasks for sending commands to a Vumi API Worker."""

from celery.task import task

from go.vumitools.api import VumiApiCommand


def get_publisher(app, **options):
    connection = app.broker_connection()
    publisher = app.amqp.TaskPublisher(connection=connection, **options)
    return publisher


@task
def batch_send_task(batch_id, msg, addresses, publisher_config):
    logger = batch_send_task.get_logger()
    with get_publisher(batch_send_task.app, serializer="json",
                       **publisher_config) as publisher:
        for address in addresses:
            cmd = VumiApiCommand.send(batch_id, msg, address)
            publisher.publish(cmd.payload)
    logger.info("Sent %d messages to vumi api worker." % len(addresses))
