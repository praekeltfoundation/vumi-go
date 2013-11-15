from datetime import datetime, timedelta
from StringIO import StringIO
import uuid

from django.test import TestCase
from django.core.paginator import Paginator
from django.core.management.base import CommandError
from django.contrib.auth import get_user_model

from vumi.tests.fake_amqp import FakeAMQPBroker
from vumi.message import TransportUserMessage, TransportEvent

# from go.vumitools.tests.utils import GoPersistenceMixin, FakeAmqpConnection


# class VumiGoDjangoTestCase(GoPersistenceMixin, TestCase):
#     sync_persistence = True

#     _cleanup_funcs = None

#     def setUp(self):
#         self._persist_setUp()

#     def tearDown(self):
#         # Run any cleanup code we've registered with .add_cleanup().
#         if self._cleanup_funcs is not None:
#             for cleanup, args, kw in reversed(self._cleanup_funcs):
#                 cleanup(*args, **kw)
#         self._persist_tearDown()

#     def add_cleanup(self, func, *args, **kw):
#         if self._cleanup_funcs is None:
#             self._cleanup_funcs = []
#         self._cleanup_funcs.append((func, args, kw))

#     def create_conversation(self, started=False, **kwargs):
#         params = {
#             'conversation_type': u'test_conversation_type',
#             'name': u'conversation name',
#             'description': u'hello world',
#             'config': {},
#         }
#         if started:
#             params['status'] = u'running'
#         params.update(kwargs)
#         return self.user_api.wrap_conversation(
#             self.user_api.new_conversation(**params))

#     def create_router(self, started=False, **kwargs):
#         params = {
#             'router_type': u'test_router_type',
#             'name': u'router name',
#             'description': u'hello world',
#             'config': {},
#         }
#         if started:
#             params['status'] = u'running'
#         params.update(kwargs)
#         return self.user_api.new_router(**params)

#     def ack_message(self, msg_out):
#         ack = TransportEvent(
#             event_type='ack',
#             user_message_id=msg_out['message_id'],
#             sent_message_id=msg_out['message_id'],
#             transport_type='sms',
#             transport_name='sphex')
#         self.api.mdb.add_event(ack)
#         return ack

#     def nack_message(self, msg_out, reason="nacked"):
#         nack = TransportEvent(
#             event_type='nack',
#             user_message_id=msg_out['message_id'],
#             nack_reason=reason,
#         )
#         self.api.mdb.add_event(nack)
#         return nack

#     def delivery_report_on_message(self, msg_out, status='delivered'):
#         assert status in TransportEvent.DELIVERY_STATUSES
#         dr = TransportEvent(
#             event_type='delivery_report',
#             user_message_id=msg_out['message_id'],
#             delivery_status=status,
#         )
#         self.api.mdb.add_event(dr)
#         return dr

#     def add_messages_to_conv(self, message_count, conversation, reply=False,
#                              ack=False, start_date=None, time_multiplier=10):
#         now = start_date or datetime.now().date()
#         batch_key = conversation.batch.key

#         messages = []
#         for i in range(message_count):
#             msg_in = TransportUserMessage(
#                 to_addr='9292',
#                 from_addr='from-%s' % (i,),
#                 content='hello',
#                 transport_type='sms',
#                 transport_name='sphex')
#             ts = now - timedelta(hours=i * time_multiplier)
#             msg_in['timestamp'] = ts
#             self.api.mdb.add_inbound_message(msg_in, batch_id=batch_key)
#             if not reply:
#                 messages.append(msg_in)
#                 continue

#             msg_out = msg_in.reply('thank you')
#             msg_out['timestamp'] = ts
#             self.api.mdb.add_outbound_message(msg_out, batch_id=batch_key)
#             if not ack:
#                 messages.append((msg_in, msg_out))
#                 continue

#             ack = self.ack_message(msg_out)
#             messages.append((msg_in, msg_out, ack))
#         return messages

#     def add_message_to_conv(self, conversation, reply=False, sensitive=False,
#                             transport_type='sms'):
#         msg = TransportUserMessage(
#             to_addr='9292',
#             from_addr='from-addr',
#             content='hello',
#             transport_type=transport_type,
#             transport_name='sphex')
#         if sensitive:
#             msg['helper_metadata']['go'] = {'sensitive': True}
#         self.api.mdb.add_inbound_message(msg, batch_id=conversation.batch.key)
#         if reply:
#             msg_out = msg.reply('hi')
#             if sensitive:
#                 msg_out['helper_metadata']['go'] = {'sensitive': True}
#             self.api.mdb.add_outbound_message(
#                 msg_out, batch_id=conversation.batch.key)

#     def declare_tags(self, pool, num_tags, metadata=None, user_select=None):
#         """Declare a set of long codes to the tag pool."""
#         if metadata is None:
#             metadata = {
#                 "display_name": "Long code",
#                 "delivery_class": "sms",
#                 "transport_type": "sms",
#                 "server_initiated": True,
#                 "transport_name": "sphex",
#             }
#         if user_select is not None:
#             metadata["user_selects_tag"] = user_select
#         self.api.tpm.declare_tags([(pool, u"default%s" % i) for i
#                                    in range(10001, 10001 + num_tags)])
#         self.api.tpm.set_metadata(pool, metadata)

#     def add_tagpool_permission(self, tagpool, max_keys=None):
#         permission = self.api.account_store.tag_permissions(
#             uuid.uuid4().hex, tagpool=tagpool, max_keys=max_keys)
#         permission.save()
#         account = self.user_api.get_user_account()
#         account.tagpools.add(permission)
#         account.save()

#     def add_app_permission(self, application):
#         permission = self.api.account_store.application_permissions(
#             uuid.uuid4().hex, application=application)
#         permission.save()

#         account = self.user_api.get_user_account()
#         account.applications.add(permission)
#         account.save()


class FakeMessageStoreClient(object):

    def __init__(self, token=None, tries=2):
        self.token = token or uuid.uuid4().hex
        self.tries = tries
        self._times_called = 0

    def match(self, batch_id, direction, query):
        return self.token

    def match_results(self, batch_id, direction, token, start, stop):
        return self.results[start:stop]


class FakeMatchResult(object):
    def __init__(self, tries=1, results=[], page_size=20):
        self._times_called = 0
        self._tries = tries
        self.results = results
        self.paginator = Paginator(self, page_size)

    def __getitem__(self, value):
        return self.results.__getitem__(value)

    def count(self):
        return len(self.results)

    def is_in_progress(self):
        self._times_called += 1
        return self._tries > self._times_called


# class GoAccountCommandTestCase(VumiGoDjangoTestCase):
#     use_riak = True
#     command_class = None

#     def setUp(self):
#         super(GoAccountCommandTestCase, self).setUp()
#         self.setup_api()
#         self.setup_user_api()
#         self.command = self.command_class()
#         self.command.stdout = StringIO()
#         self.command.stderr = StringIO()

#     def call_command(self, *command, **options):
#         # Make sure we have options for the command(s) specified
#         for cmd_name in command:
#             self.assertTrue(
#                 cmd_name in self.command.list_commands(),
#                 "Command '%s' has no command line option" % (cmd_name,))
#         # Make sure we have options for any option keys specified
#         opt_dests = set(opt.dest for opt in self.command.option_list)
#         for opt_dest in options:
#             self.assertTrue(
#                 opt_dest in opt_dests,
#                 "Option key '%s' has no command line option" % (opt_dest,))
#         # Call the command handler
#         return self.command.handle(
#             email_address=self.django_user.email, command=command, **options)

#     def assert_command_error(self, regexp, *command, **options):
#         self.assertRaisesRegexp(
#             CommandError, regexp, self.call_command, *command, **options)

#     def assert_command_output(self, expected_output, *command, **options):
#         self.call_command(*command, **options)
#         self.assertEqual(expected_output, self.command.stdout.getvalue())
