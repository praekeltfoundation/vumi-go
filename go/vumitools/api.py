# -*- test-case-name: go.vumitools.tests.test_api -*-
# -*- coding: utf-8 -*-

"""Vumi API for high-volume messaging."""

from uuid import uuid4

from celery import task


class VumiApi(object):

    def __init__(self, config):
        # message store
        self.mdb = MessageStore(config['message_store'])
        # message sending API
        self.mapi = MessageSender(config['message_sender'])

    def batch_start(self):
        """Start a message batch.

        :rtype:
            Returns the batch_id of the new batch.
        """
        return self.mdb.batch_start()

    def batch_send(self, batch_id, msg, addresses):
        """Send a batch of text message to a list of addresses.

        Use multiple calls to :meth:`batch_send` if you have *lots* of
        addresses and don't want to pass them all in one API
        call. Messages passed to multiple calls to :meth:`batch_send`
        do not have to be the same.

        :type batch_id:
        :param batch_id:
            batch to append the messages too
        :type msg: unicode
        :param msg:
            text to send
        :type addresses:
        :param msg:
            list of addresses to send messages to
        :rtype:
            None.
        """
        return self.mapi.batch_send(batch_id, msg, addresses)

    def batch_status(self, batch_id):
        """Check the status of a batch of messages.

        :type batch_id:
        :param batch_id:
            batch to check the status of
        :rtype:
            TODO: define return
        """
        return self.mdb.batch_status()


class MessageStore(object):
    def __init__(self, config):
        self.config = config

    def batch_start(self):
        batch_id = uuid4()
        # TODO: put batch into store
        return batch_id

    def batch_status(self, batch_id):
        # TODO: fetch and return status of batch
        pass


class MessageSender(object):
    def __init__(self, config):
        self.config = config
        self.publisher_config = {
            'exchange': 'vumi',
            'exchange_type': 'direct',
            'routing_key': 'vumi.api',
            }

    def batch_send(self, batch_id, msg, addresses):
        batch_send_task.delay(batch_id, msg, addresses, self.publisher_config)


class VumiApiCommand(object):

    def __init__(self, payload):
        self.payload = payload

    @classmethod
    def send(cls, batch_id, msg, address):
        return cls({
            'command': 'send',
            'batch_id': batch_id,
            'content': msg,
            'to_addr': address,
            })


@task
def batch_send_task(batch_id, msg, addresses, publisher_config):
    logger = batch_send_task.get_logger()
    with batch_send_task.get_publisher(**publisher_config) as publisher:
        for address in addresses:
            msg = VumiApiCommand.send(batch_id, msg, address)
            publisher.publish(msg.payload)
    logger.info("Sent %d messages to vumi api worker." % len(addresses))
