# -*- test-case-name: go.vumitools.tests.test_api -*-
# -*- coding: utf-8 -*-

"""Vumi API for high-volume messaging."""


class VumiApi(object):

    def batch_start(self):
        """Start a message batch.

        :rtype:
            Returns the batch_id of the new batch.
        """
        # create batch id in data store
        raise NotImplementedError

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
        """
        # run celery task that sends messages to Vumi API worker
        raise NotImplementedError

    def batch_status(batch_id):
        """Check the status of a batch of messages.

        :type batch_id:
        :param batch_id:
            batch to check the status of
        """
        # retrieve information about batch from data store
        raise NotImplementedError
