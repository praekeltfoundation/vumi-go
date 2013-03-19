# -*- test-case-name: go.vumitools.tests.test_api_celery -*-
# -*- coding: utf-8 -*-

"""Celery tasks for sending commands to a Vumi API Worker."""
from celery.task import task


def get_publisher(app, **options):
    connection = app.broker_connection()
    publisher = app.amqp.TaskPublisher(connection=connection, **options)
    return publisher


@task(ignore_result=True)
def send_command_task(command, publisher_config):
    logger = send_command_task.get_logger()
    with get_publisher(send_command_task.app, serializer="json",
                        **publisher_config) as publisher:
        publisher.publish(command.payload)
    logger.info("Sent command %s" % (command,))
