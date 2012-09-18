# -*- test-case-name: go.apps.wikipedia.tests.test_vumi_app -*-
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi_wikipedia.wikipedia import WikipediaWorker

from go.vumitools.api_worker import GoMessageMetadata
from go.vumitools.api import VumiApi


class WikipediaApplication(WikipediaWorker):
    """
    The primary reason for subclassing WikipediaWorker is that we need
    to do some trickery to get the SMS tag assigned to this conversation.

    In the UI there need to be two conversations, one with an SMS tag and one
    with a USSD tag. The USSD conversation should reference a conversation
    with an SMS tag and steal it by storing it in its metadata.

    """

    def validate_config(self):
        self.vumi_api = VumiApi.from_config(self.config)

    @inlineCallbacks
    def get_conversation_metadata(self, message):
        gm = GoMessageMetadata(self.vumi_api, message)
        conversation = yield gm.get_conversation()
        returnValue(conversation.get_metadata(default={}))

    @inlineCallbacks
    def send_sms_content(self, message, session):
        """
        Here we need to:

        1. Grab the conversation this outbound message is for
        2. Grab the tag from the conversation metadata
        3. Insert the tag into the `transport_name` in the outbound message
        4. Hand it over to the `vumigo_router` for delivery

        I cannot subclass since WikipediaWorker sets the transport_name
        to `self.sms_transport` and then immediate publishes it for delivery.

        Unfortunately this means I need to copy bits of code.
        """
        content_len, sms_content = self.sms_formatter.format_more(
            session['sms_content'], session['sms_offset'],
            self.more_content_postfix, self.no_more_content_postfix)
        session['sms_offset'] = session['sms_offset'] + content_len + 1
        if session['sms_offset'] >= len(session['sms_content']):
            session['state'] = None

        conv_metadata = yield self.get_metadata(message)

        bmsg = message.reply(sms_content)
        bmsg['from_addr'] = conv_metadata['from_addr']
        bmsg['transport_name'] = conv_metadata['transport_name']
        bmsg['transport_type'] = 'sms'
        if self.override_sms_address:
            bmsg['to_addr'] = self.override_sms_address
        self.transport_publisher.publish_message(
            bmsg, routing_key='%s.outbound' % (self.sms_transport,))
