# -*- test-case-name: go.vumitools.tests.test_api_celery -*-
# -*- coding: utf-8 -*-

"""Celery tasks for sending commands to a Vumi API Worker."""
import warnings

from celery.task import task

from go.vumitools.api import VumiApiCommand


def get_publisher(app, **options):
    connection = app.broker_connection()
    publisher = app.amqp.TaskPublisher(connection=connection, **options)
    return publisher


@task
def send_command_task(command, publisher_config):
    logger = send_command_task.get_logger()
    with get_publisher(send_command_task.app, serializer="json",
                        **publisher_config) as publisher:
        publisher.publish(command.payload)
    logger.info("Sent command %s" % (command,))


@task
def batch_send_task(batch_id, msg, msg_options, addresses, publisher_config):
    warnings.warn('Use `send_command_task` instead.', DeprecationWarning)
    logger = batch_send_task.get_logger()
    with get_publisher(batch_send_task.app, serializer="json",
                       **publisher_config) as publisher:
        for address in addresses:
            worker_name = msg_options['worker_name']
            cmd = VumiApiCommand.command(worker_name, 'send',
                batch_id=batch_id, content=msg, msg_options=msg_options,
                to_addr=address)
            publisher.publish(cmd.payload)
    logger.info("Sent %d messages to vumi api worker." % len(addresses))
