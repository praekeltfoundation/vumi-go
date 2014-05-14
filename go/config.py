"""Vumi Go configuration helpers.

   These are intended to be accessible via both code running under Django
   and Vumi Twisted workers.

   Constants here should only be accessed via helper functions. Constants
   will eventually be replaced by an external configuration store of some
   sort.
   """

import copy

from go.errors import UnknownConversationType, UnknownRouterType


def configured_conversation_types():
    return dict((a['namespace'], a['display_name'])
                for a in _VUMI_INSTALLED_APPS.itervalues())


def configured_conversations():
    return copy.deepcopy(_VUMI_INSTALLED_APPS)


def obsolete_conversation_types():
    return set(_VUMI_OBSOLETE_APPS)


def configured_router_types():
    return dict((a['namespace'], a['display_name'])
                for a in _VUMI_INSTALLED_ROUTERS.itervalues())


def configured_routers():
    return copy.deepcopy(_VUMI_INSTALLED_ROUTERS)


def obsolete_router_types():
    return set(_VUMI_OBSOLETE_ROUTERS)


def get_conversation_pkg(conversation_type, fromlist):
    for module, data in _VUMI_INSTALLED_APPS.iteritems():
        if data['namespace'] == conversation_type:
            app_pkg = __import__(module,
                                 fromlist=fromlist)
            return app_pkg
    raise UnknownConversationType(
        "Can't find python package for conversation type: %r"
        % (conversation_type,))


def get_router_pkg(router_type, fromlist=()):
    for module, data in _VUMI_INSTALLED_ROUTERS.iteritems():
        if data['namespace'] == router_type:
            router_pkg = __import__(module,
                                 fromlist=fromlist)
            return router_pkg
    raise UnknownRouterType(
        "Can't find python package for router type: %r"
        % (router_type,))


def get_conversation_definition(conversation_type, conv=None):
    app_pkg = get_conversation_pkg(conversation_type, ['definition'])
    return app_pkg.definition.ConversationDefinition(conv)


def get_router_definition(router_type, router=None):
    router_pkg = get_router_pkg(router_type, ['definition'])
    return router_pkg.definition.RouterDefinition(router)


_VUMI_INSTALLED_APPS = {
    'go.apps.bulk_message': {
        'namespace': 'bulk_message',
        'display_name': 'Group Message',
    },
    'go.apps.dialogue': {
        'namespace': 'dialogue',
        'display_name': 'Dialogue',
    },
    'go.apps.multi_surveys': {
        'namespace': 'multi_survey',
        'display_name': 'Old Multi Surveys',
    },
    'go.apps.surveys': {
        'namespace': 'survey',
        'display_name': 'Old Surveys',
    },
    'go.apps.opt_out': {
        'namespace': 'opt_out',
        'display_name': 'Opt Out Handler',
    },
    'go.apps.sequential_send': {
        'namespace': 'sequential_send',
        'display_name': 'Sequential Send',
    },
    'go.apps.subscription': {
        'namespace': 'subscription',
        'display_name': 'Subscription Manager',
    },
    'go.apps.wikipedia': {
        'namespace': 'wikipedia',
        'display_name': 'Wikipedia',
    },
    'go.apps.jsbox': {
        'namespace': 'jsbox',
        'display_name': 'Javascript App',
    },
    'go.apps.http_api': {
        'namespace': 'http_api',
        'display_name': 'HTTP API',
    },
    'go.apps.http_api_nostream': {
        'namespace': 'http_api_nostream',
        'display_name': 'HTTP API (No Streaming)',
    },
    'go.apps.rapidsms': {
        'namespace': 'rapidsms',
        'display_name': 'Rapid SMS',
    },
    'go.apps.static_reply': {
        'namespace': 'static_reply',
        'display_name': 'Static Reply',
    },
}

_VUMI_OBSOLETE_APPS = [
    'wikipedia_sms',
    'wikipedia_ussd',
]

_VUMI_INSTALLED_ROUTERS = {
    'go.routers.keyword': {
        'namespace': 'keyword',
        'display_name': 'Keyword',
    },
    'go.routers.group': {
        'namespace': 'group',
        'display_name': 'Group',
    },
    'go.routers.app_multiplexer': {
        'namespace': 'app_multiplexer',
        'display_name': 'Application Multiplexer',
    },
}

_VUMI_OBSOLETE_ROUTERS = [
]


def billing_quantization_exponent():
    # This is currently hardcoded in here to avoid pulling a pile of Django
    # stuff into `go.vumitools.billing_worker` through `go.billing.settings`.
    from decimal import Decimal
    return Decimal('.000001')


GO_METRICS_PREFIX = 'go.'


def get_go_metrics_prefix():
    return GO_METRICS_PREFIX
