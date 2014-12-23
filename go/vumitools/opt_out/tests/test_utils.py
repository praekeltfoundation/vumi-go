from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.vumitools.utils import MessageMetadataHelper
from go.vumitools.tests.helpers import VumiApiHelper, GoMessageHelper
from go.vumitools.opt_out.utils import OptOutHelper


class TestOptOutHelper(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.make_user(u'testuser')
        self.vumi_api = self.vumi_helper.get_vumi_api()
        self.account = yield self.user_helper.get_user_account()
        self.msg_helper = self.add_helper(GoMessageHelper())

    @inlineCallbacks
    def test_process_message_opt_out(self):
        opt_outs = OptOutHelper(self.vumi_api, {'keywords': ['stop', 'halt']})

        msg = self.msg_helper.make_inbound('stop')
        yield opt_outs.process_message(self.account, msg)

        self.assertEqual(msg['helper_metadata']['opt_out'], {
            'opt_out': True,
            'opt_out_keyword': 'stop',
        })

        msg = self.msg_helper.make_inbound('halt')
        yield opt_outs.process_message(self.account, msg)

        self.assertEqual(msg['helper_metadata']['opt_out'], {
            'opt_out': True,
            'opt_out_keyword': 'halt',
        })

    @inlineCallbacks
    def test_process_message_non_opt_out(self):
        opt_outs = OptOutHelper(self.vumi_api, {'keywords': ['stop', 'halt']})

        msg = self.msg_helper.make_inbound('hi')
        yield opt_outs.process_message(self.account, msg)
        self.assertEqual(msg['helper_metadata']['opt_out'], {'opt_out': False})

    @inlineCallbacks
    def test_process_message_case_insensitive(self):
        opt_outs = OptOutHelper(self.vumi_api, {
            'case_sensitive': False,
            'keywords': ['STOP']
        })

        msg = self.msg_helper.make_inbound('stop')
        yield opt_outs.process_message(self.account, msg)

        self.assertEqual(msg['helper_metadata']['opt_out'], {
            'opt_out': True,
            'opt_out_keyword': 'stop',
        })

        msg = self.msg_helper.make_inbound('sToP')
        yield opt_outs.process_message(self.account, msg)

        self.assertEqual(msg['helper_metadata']['opt_out'], {
            'opt_out': True,
            'opt_out_keyword': 'stop',
        })

        msg = self.msg_helper.make_inbound('STOP')
        yield opt_outs.process_message(self.account, msg)

        self.assertEqual(msg['helper_metadata']['opt_out'], {
            'opt_out': True,
            'opt_out_keyword': 'stop',
        })

    @inlineCallbacks
    def test_process_message_case_sensitive(self):
        opt_outs = OptOutHelper(self.vumi_api, {
            'case_sensitive': True,
            'keywords': ['STOP']
        })

        msg = self.msg_helper.make_inbound('stop')
        yield opt_outs.process_message(self.account, msg)
        self.assertEqual(msg['helper_metadata']['opt_out'], {'opt_out': False})

        msg = self.msg_helper.make_inbound('sToP')
        yield opt_outs.process_message(self.account, msg)
        self.assertEqual(msg['helper_metadata']['opt_out'], {'opt_out': False})

        msg = self.msg_helper.make_inbound('STOP')
        yield opt_outs.process_message(self.account, msg)

        self.assertEqual(msg['helper_metadata']['opt_out'], {
            'opt_out': True,
            'opt_out_keyword': 'STOP',
        })

    @inlineCallbacks
    def test_process_message_disabled_by_tagpool(self):
        opt_outs = OptOutHelper(self.vumi_api, {'keywords': ['stop']})

        yield self.vumi_helper.setup_tagpool(u'pool1', [u'tag1'], {
            'disable_global_opt_out': True
        })

        msg = self.msg_helper.make_inbound('stop')
        md = MessageMetadataHelper(self.vumi_api, msg)
        md.set_tag((u'pool1', u'tag1'))

        yield opt_outs.process_message(self.account, msg)
        self.assertEqual(msg['helper_metadata']['opt_out'], {'opt_out': False})

    def test_is_opt_out_message(self):
        msg = self.msg_helper.make_inbound('hi')
        self.assertFalse(OptOutHelper.is_opt_out_message(msg))

        msg['helper_metadata'] = {'opt_out': {'opt_out': True}}
        self.assertTrue(OptOutHelper.is_opt_out_message(msg))

        msg['helper_metadata'] = {'opt_out': {'opt_out': False}}
        self.assertFalse(OptOutHelper.is_opt_out_message(msg))
