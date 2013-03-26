# -*- test-case-name: go.apps.wikipedia.tests.test_vumi_app -*-
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi_wikipedia.wikipedia import WikipediaWorker
from vumi import log

from go.vumitools.app_worker import GoApplicationMixin


class WikipediaApplication(WikipediaWorker, GoApplicationMixin):
    """
    The primary reason for subclassing WikipediaWorker is that we need
    to do some trickery to get the SMS tag assigned to this conversation.

    In the UI there need to be two conversations, one with an SMS tag and one
    with a USSD tag. The USSD conversation should reference a conversation
    with an SMS tag and steal it by storing it in its metadata.

    """
    worker_name = 'wikipedia_ussd_application'

    def validate_config(self):
        super(WikipediaApplication, self).validate_config()
        self._go_validate_config()
        self._tagpool_metadata = None

    @inlineCallbacks
    def setup_application(self):
        # Avoid metrics setup in the underlying app.
        metrics_prefix, self.metrics_prefix = self.metrics_prefix, None
        yield super(WikipediaApplication, self).setup_application()
        self.metrics_prefix = metrics_prefix
        yield self._go_setup_application()

    @inlineCallbacks
    def teardown_application(self):
        yield super(WikipediaApplication, self).teardown_application()
        yield self._go_teardown_application()

    def fire_metric(self, metric_name, metric_suffix=None, value=1):
        # Don't try to collect metrics.
        pass

    @inlineCallbacks
    def get_conversation_metadata(self, message):
        gm = self.get_go_metadata(message)
        conversation = yield gm.get_conversation()
        if conversation and conversation.config:
            returnValue(conversation.config)
        returnValue({})

    @inlineCallbacks
    def get_tagpool_metadata(self, tagpool, key, default=None):
        if self._tagpool_metadata is None:
            self._tagpool_metadata = yield self.vumi_api.tpm.get_metadata(
                tagpool)
        returnValue(self._tagpool_metadata.get(key, default))

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

        bmsg = message.reply(sms_content)
        bmsg['transport_type'] = 'sms'

        conv_metadata = yield self.get_conversation_metadata(message)
        if conv_metadata:
            # If we've got the metadata then this is the first message
            # we're sending out which means we need to explicitly set
            # the from_addr and tagpool_metadata to set the correct
            # transport_name.
            #
            # All replies coming in through this will be received via the
            # correct transport and tagged accordingly which means replies
            # are routed back without a problem.
            from_tagpool = conv_metadata['send_from_tagpool']
            from_addr = conv_metadata['send_from_tag']
            bmsg['from_addr'] = from_addr
            tagpool_metadata = yield self.get_tagpool_metadata(from_tagpool,
                'msg_options')
            bmsg.payload.update(tagpool_metadata)

        if self.override_sms_address:
            bmsg['to_addr'] = self.override_sms_address

        self.transport_publisher.publish_message(
            bmsg, routing_key='%s.outbound' % (self.sms_transport,))
        returnValue(session)

    def process_command_start(self, batch_id, conversation_type,
                              conversation_key, msg_options,
                              is_client_initiated, **extra_params):
        log.debug('Conversation %r has been started, no need to '
                    'do anything.' % (conversation_key,))
