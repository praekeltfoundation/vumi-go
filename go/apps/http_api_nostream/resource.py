# -*- test-case-name: go.apps.http_api_nostream.tests.test_vumi_app -*-

import json
import copy

from twisted.web import resource, http, util
from twisted.web.server import NOT_DONE_YET
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue

from vumi import errors
from vumi.blinkenlights import metrics
from vumi.message import TransportUserMessage
from vumi.errors import InvalidMessage
from vumi.config import ConfigContext
from vumi import log

from go.vumitools.utils import MessageMetadataHelper

from go.apps.http_api_nostream.definition import DEFAULT_METRIC_STORE

# NOTE: Things in this module are subclassed and used by go.apps.http_api.


class BaseResource(resource.Resource):

    def __init__(self, worker, conversation_key):
        resource.Resource.__init__(self)
        self.worker = worker
        self.conversation_key = conversation_key
        self.vumi_api = self.worker.vumi_api
        self.user_apis = {}

    def get_user_api(self, user_account):
        if user_account in self.user_apis:
            return self.user_apis[user_account]

        user_api = self.vumi_api.get_user_api(user_account)
        self.user_apis[user_account] = user_api
        return user_api

    def get_conversation(self, user_account, conversation_key=None):
        conversation_key = conversation_key or self.conversation_key
        user_api = self.get_user_api(user_account)
        return user_api.get_wrapped_conversation(conversation_key)

    def finish_response(self, request, body, code, status=None):
        request.setResponseCode(code, status)
        request.write(body)
        request.finish()

    def client_error_response(self, request, reason, code=http.BAD_REQUEST):
        msg = json.dumps({
            "success": False,
            "reason": reason,
        })
        self.finish_response(request, msg, code=code, status=reason)

    def success_response(self, request, reason, code=http.OK):
        msg = json.dumps({
            "success": True,
            "reason": reason,
        })
        self.finish_response(request, msg, code=code, status=reason)

    def successful_send_response(self, request, msg, code=http.OK):
        self.finish_response(request, msg.to_json(), code=code)


class InvalidAggregate(errors.VumiError):
    pass


class MsgOptions(object):
    """Helper for sanitizing msg options from clients."""

    WHITELIST = {}

    def __init__(self, payload):
        self.errors = []
        for key, checker in sorted(self.WHITELIST.iteritems()):
            value = payload.get(key)
            if not checker(value):
                self.errors.append(
                    "Invalid or missing value for payload key %r" % (key,))
            else:
                setattr(self, key, value)

    @property
    def is_valid(self):
        return not bool(self.errors)

    @property
    def error_msg(self):
        if not self.errors:
            return None
        elif len(self.errors) == 1:
            return self.errors[0]
        else:
            return "Errors:\n* %s" % ("\n* ".join(self.errors))


class MsgCheckHelpers(object):
    @staticmethod
    def is_unicode_or_none(value):
        return (value is None) or (isinstance(value, unicode))

    @staticmethod
    def is_session_event(value):
        return value in TransportUserMessage.SESSION_EVENTS


class SendToOptions(MsgOptions):
    """Payload options for messages sent with `.send_to(...)`."""

    WHITELIST = {
        'content': MsgCheckHelpers.is_unicode_or_none,
        'to_addr': MsgCheckHelpers.is_unicode_or_none,
    }


class ReplyToOptions(MsgOptions):
    """Payload options for messages sent with `.reply_to(...)`."""

    WHITELIST = {
        'content': MsgCheckHelpers.is_unicode_or_none,
        'session_event': MsgCheckHelpers.is_session_event,
    }


class MessageResource(BaseResource):

    routing_key = '%(transport_name)s.stream.message.%(conversation_key)s'

    def render_PUT(self, request):
        d = Deferred()
        d.addCallback(self.handle_PUT)
        d.callback(request)
        return NOT_DONE_YET

    def get_load_balancer_metadata(self, payload):
        """
        Probe for load_balancer config in the helper metadata
        and return it.

        TODO: Replace with a more generic mechanism for filtering
        helper_metadata. See Go issue #659.
        """
        helper_metadata = payload.get('helper_metadata', {})
        load_balancer = helper_metadata.get('load_balancer')
        if load_balancer is not None:
            return {'load_balancer': copy.deepcopy(load_balancer)}
        return {}

    def get_conversation_tag(self, conversation):
        return (conversation.delivery_tag_pool, conversation.delivery_tag)

    @inlineCallbacks
    def handle_PUT(self, request):
        try:
            payload = json.loads(request.content.read())
        except ValueError:
            self.client_error_response(request, 'Invalid Message')
            return

        in_reply_to = payload.get('in_reply_to')
        if in_reply_to:
            yield self.handle_PUT_in_reply_to(request, payload, in_reply_to)
        else:
            yield self.handle_PUT_send_to(request, payload)

    @inlineCallbacks
    def handle_PUT_in_reply_to(self, request, payload, in_reply_to):
        user_account = request.getUser()
        conversation = yield self.get_conversation(user_account)

        reply_to = yield self.vumi_api.mdb.get_inbound_message(in_reply_to)
        if reply_to is None:
            self.client_error_response(request, 'Invalid in_reply_to value')
            return

        reply_to_mdh = MessageMetadataHelper(self.vumi_api, reply_to)
        try:
            msg_conversation_key = reply_to_mdh.get_conversation_key()
        except KeyError:
            log.warning('Invalid reply to message %r which has no conversation'
                        ' key' % (reply_to,))
            msg_conversation_key = None
        if msg_conversation_key != conversation.key:
            self.client_error_response(request, 'Invalid in_reply_to value')
            return

        msg_options = ReplyToOptions(payload)
        if not msg_options.is_valid:
            self.client_error_response(request, msg_options.error_msg)
            return

        continue_session = (msg_options.session_event
                            != TransportUserMessage.SESSION_CLOSE)
        helper_metadata = conversation.set_go_helper_metadata()
        helper_metadata.update(self.get_load_balancer_metadata(payload))

        msg = yield self.worker.reply_to(
            reply_to, msg_options.content, continue_session,
            helper_metadata=helper_metadata)

        self.successful_send_response(request, msg)

    @inlineCallbacks
    def handle_PUT_send_to(self, request, payload):
        user_account = request.getUser()
        conversation = yield self.get_conversation(user_account)

        msg_options = SendToOptions(payload)
        if not msg_options.is_valid:
            self.client_error_response(request, msg_options.error_msg)
            return

        helper_metadata = conversation.set_go_helper_metadata()

        msg = yield self.worker.send_to(
            msg_options.to_addr, msg_options.content,
            endpoint='default', helper_metadata=helper_metadata)

        self.successful_send_response(request, msg)


class MetricResource(BaseResource):

    def render_PUT(self, request):
        d = Deferred()
        d.addCallback(self.handle_PUT)
        d.callback(request)
        return NOT_DONE_YET

    def find_aggregate(self, name):
        agg_class = getattr(metrics, name, None)
        if agg_class is None:
            raise InvalidAggregate('%s is not a valid aggregate.' % (name,))
        return agg_class

    def parse_metrics(self, data):
        metrics = []
        for name, value, aggregate in data:
            value = float(value)
            agg_class = self.find_aggregate(aggregate)
            metrics.append((name, value, agg_class))
        return metrics

    @inlineCallbacks
    def handle_PUT(self, request):
        data = json.loads(request.content.read())
        user_account = request.getUser()

        try:
            metrics = self.parse_metrics(data)
        except (ValueError, InvalidAggregate, InvalidMessage):
            self.client_error_response(request, 'Invalid Message')
            return

        conversation = yield self.get_conversation(user_account)
        store = self.worker.get_api_config(
            conversation, 'metric_store', DEFAULT_METRIC_STORE)
        for name, value, agg_class in metrics:
            self.worker.publish_account_metric(user_account, store, name,
                                               value, agg_class)

        self.success_response(request, 'Metrics published')


class ConversationResource(resource.Resource):

    def __init__(self, worker, conversation_key):
        resource.Resource.__init__(self)
        self.worker = worker
        self.redis = worker.redis
        self.conversation_key = conversation_key

    def get_worker_config(self, user_account_key):
        ctxt = ConfigContext(user_account=user_account_key)
        return self.worker.get_config(msg=None, ctxt=ctxt)

    def key(self, *args):
        return ':'.join(['concurrency'] + map(unicode, args))

    @inlineCallbacks
    def is_allowed(self, config, user_id):
        if config.concurrency_limit < 0:
            returnValue(True)
        count = int((yield self.redis.get(self.key(user_id))) or 0)
        returnValue(count < config.concurrency_limit)

    def track_request(self, user_id):
        return self.redis.incr(self.key(user_id))

    def release_request(self, err, user_id):
        return self.redis.decr(self.key(user_id))

    def render(self, request):
        return resource.NoResource().render(request)

    def getChild(self, path, request):
        return util.DeferredResource(self.getDeferredChild(path, request))

    @inlineCallbacks
    def getDeferredChild(self, path, request):
        resource_class = self.get_child_resource(path)

        if resource_class is None:
            returnValue(resource.NoResource())

        user_id = request.getUser()
        config = yield self.get_worker_config(user_id)
        if (yield self.is_allowed(config, user_id)):

            # remove track when request is closed
            finished = request.notifyFinish()
            finished.addBoth(self.release_request, user_id)

            yield self.track_request(user_id)
            returnValue(resource_class(self.worker, self.conversation_key))
        returnValue(resource.ErrorPage(http.FORBIDDEN, 'Forbidden',
                                       'Too many concurrent connections'))

    def get_child_resource(self, path):
        return {
            'messages.json': MessageResource,
            'metrics.json': MetricResource,
        }.get(path)
