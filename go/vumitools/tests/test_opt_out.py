from go.vumitools.tests.test_handler import EventHandlerTestCase

from twisted.internet.defer import inlineCallbacks


class OptInHandlerTestCase(EventHandlerTestCase):

    handlers = [
        ('conv', 'go.vumitools.opt_out.handlers.OptInHandler', {})
    ]

    @inlineCallbacks
    def setUp(self):
        yield super(OptInHandlerTestCase, self).setUp()
        self.contact_store = self.user_api.contact_store
        contact = yield self.contact_store.new_contact(
            name=u'J Random', surname=u'Person', msisdn=u'27831234567')
        self.contact_id = contact.key
        self.track_event(self.account.key, self.conversation.key,
                         'opt_in', 'conv')

    def mkevent_opt(self, operation):
        return self.mkevent('opt_in', {
            'contact_id': self.contact_id,
            'campaign_name': 'testcampaign',
            'operation': operation,
            }, conv_key=self.conversation.key, account_key=self.account.key)

    @inlineCallbacks
    def assert_opted(self, value):
        contact = yield self.contact_store.get_contact_by_key(self.contact_id)
        self.assertEqual(contact.optin['testcampaign'], value)

    @inlineCallbacks
    def test_opt_in(self):
        yield self.assert_opted(None)
        yield self.publish_event(self.mkevent_opt('opt_in'))
        yield self.assert_opted('opted_in')

    @inlineCallbacks
    def test_opt_out(self):
        yield self.assert_opted(None)
        yield self.publish_event(self.mkevent_opt('opt_out'))
        yield self.assert_opted('opted_out')

    @inlineCallbacks
    def test_opt_hokey_pokey(self):
        yield self.assert_opted(None)
        yield self.publish_event(self.mkevent_opt('opt_in'))
        yield self.assert_opted('opted_in')
        yield self.publish_event(self.mkevent_opt('opt_in'))
        yield self.assert_opted('opted_in')
        yield self.publish_event(self.mkevent_opt('opt_out'))
        yield self.assert_opted('opted_out')
        yield self.publish_event(self.mkevent_opt('opt_in'))
        yield self.assert_opted('opted_in')
