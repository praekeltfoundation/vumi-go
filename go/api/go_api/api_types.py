# -*- coding: utf-8 -*-
# -*- test-case-name: go.api.go_api.tests.test_api_types -*-

"""Types for the JSON RPC API for Vumi Go."""

from vumi.rpc import Unicode, List, Dict, Tag

from go.vumitools.account.models import GoConnector


class CampaignType(Dict):
    def __init__(self, *args, **kw):
        kw['required_fields'] = {
            'key': Unicode(),
            'name': Unicode(),
        }
        super(CampaignType, self).__init__(*args, **kw)

    @classmethod
    def format_campaign(cls, campaign):
        return {
            'key': campaign["key"],
            'name': campaign["name"],
        }


class EndpointType(Dict):
    """Description of an endpoint.

    The following fields are required:

    * uuid: Unique identifier for the endpoint. Usually
            `<connector-id>:<endpoint-name>`.
    * name: Name of the endpoint, e.g. 'default'.
    """
    def __init__(self, *args, **kw):
        kw['required_fields'] = {
            'uuid': Unicode(),
            'name': Unicode(),
        }
        super(EndpointType, self).__init__(*args, **kw)

    @classmethod
    def format_endpoint(cls, uuid, name):
        return {'uuid': uuid, 'name': name}


class ConversationType(Dict):
    def __init__(self, *args, **kw):
        """Description of a conversation.

        The following fields are required:

        * uuid: The conversation key.
        * type: The conversation type, e.g. 'bulk-message'.
        * name: The conversation name, e.g. 'My Bulk Sender'.
        * description: The conversation description, e.g.
                       'Some Bulk Message App'.
        * endpoints: A list of `EndpointType` dictionaries, e.g.
                     `[{uuid: 'endpoint-uuid-4', name: 'default'}]`.
        """
        kw['required_fields'] = {
            'uuid': Unicode(),
            'type': Unicode(),
            'name': Unicode(),
            'description': Unicode(),
            'endpoints': List(item_type=EndpointType()),
        }
        super(ConversationType, self).__init__(*args, **kw)

    @classmethod
    def format_conversation(cls, conv):
        conn = GoConnector.for_conversation(conv.conversation_type, conv.key)
        return {
            'uuid': conv.key,
            'type': conv.conversation_type,
            'name': conv.name,
            'description': conv.description,
            'endpoints': [
                # TODO: add additional endpoints once we know how to list them
                EndpointType.format_endpoint(
                    uuid=u"%s:%s" % (conn, endpoint), name=endpoint)
                for endpoint in [u'default'] + list(conv.extra_endpoints)
            ],
        }


class ChannelType(Dict):
    """Description of a channel.

    The following keys are required:

    * uuid: The channel key.
    * tag: A two-element list of the tag pool and tag name, e.g.
           `['apposit_sms', '*121#']`.
    * name: The channel name, often the same as the tag name, e.g. '*121#'.
    * description: The channel description, e.g. 'Apposit Sms: *121#'.
    * endpoints: A list of `EndpointType` dictionaries, e.g.
                 `[{uuid: 'endpoint-uuid-1', name: 'default'}]`.
    """
    def __init__(self, *args, **kw):
        kw['required_fields'] = {
            'uuid': Unicode(),
            'tag': Tag(),
            'name': Unicode(),
            'description': Unicode(),
            'endpoints': List(item_type=EndpointType()),
        }
        super(ChannelType, self).__init__(*args, **kw)

    @classmethod
    def format_channel(cls, tag):
        pool, tagname = tag
        uuid = u":".join(tag)
        conn = GoConnector.for_transport_tag(pool, tagname)
        return {
            'uuid': uuid, 'tag': tag, 'name': tagname,
            'description': u"%s: %s" % (
                pool.replace('_', ' ').title(), tagname),
            'endpoints': [
                EndpointType.format_endpoint(
                    uuid=u"%s:%s" % (conn, u'default'), name=u"default")
            ]
        }


class RouterType(Dict):
    """Description of a router.

    The following keys are required:

    * uuid: The router key.
    * type: The router type, e.g. 'keyword'.
    * name: The router name, e.g. 'My Keyword Router'.
    * description: The router description,
                   e.g.'A description of this router'.
    * channel_endpoints: The endpoints that can be connected to channels
                         (i.e. the endpoints on the left).
                         A list of `EndpointType` dictionaries, e.g.
                         `[{uuid: 'endpoint-uuid-2', name: 'default'}]`.
    * conversation_endpoints: The endpoints that can be connected to
                              conversations (i.e. the endpoints on the right).
                              A list of `EndpointType` dictionaries, e.g.
                              `[{uuid: 'endpoint-uuid-3', name: 'default'}]`.
    """
    def __init__(self, *args, **kw):
        kw['required_fields'] = {
            'uuid': Unicode(),
            'type': Unicode(),
            'name': Unicode(),
            'description': Unicode(),
            'channel_endpoints': List(item_type=EndpointType()),
            'conversation_endpoints': List(item_type=EndpointType()),
        }
        super(RouterType, self).__init__(*args, **kw)

    @classmethod
    def format_router(cls, uuid, rb_type, name, description, channel_endpoints,
                      conversation_endpoints):
        return {
            'uuid': uuid, 'type': rb_type, 'name': name,
            'description': description, 'channel_endpoints': channel_endpoints,
            'conversation_endpoints': conversation_endpoints,
        }


class RoutingEntryType(Dict):
    """Description of an entry in a routing table.

    The following keys are required:

    * source: A dictionary containing the uuid of the source endpoint, e.g.
              `{uuid: 'endpoint-uuid-1'}`.
    * target: A dictionary containing the uuid of the destination endpoint,
              e.g. `{uuid: 'endpoint-uuid-2'}`.
    """
    def __init__(self, *args, **kw):
        uuid_dict = Dict(required_fields={'uuid': Unicode()})
        kw['required_fields'] = {
            'source': uuid_dict,
            'target': uuid_dict,
        }
        super(RoutingEntryType, self).__init__(*args, **kw)

    @classmethod
    def format_entry(cls, source_uuid, target_uuid):
        return {
            'source': {'uuid': source_uuid},
            'target': {'uuid': target_uuid},
        }


class RoutingType(Dict):
    """Description of a campaign routing table.

    The following keys are required:

    * channels: A list of `ChannelType` values.
    * routers: A list of `RouterType` values.
    * conversations: A list of `ConversationType` values.
    * routing_entries: A list of `RoutingEntryType` values.
    """

    def __init__(self, *args, **kw):
        kw['required_fields'] = {
            'channels': List(item_type=ChannelType()),
            'routers': List(item_type=RouterType()),
            'conversations': List(item_type=ConversationType()),
            'routing_entries': List(item_type=RoutingEntryType()),
        }
        super(RoutingType, self).__init__(*args, **kw)

    @classmethod
    def format_routing(cls, channels, routers, conversations,
                       routing_entries):
        return {
            'channels': channels,
            'routers': routers,
            'conversations': conversations,
            'routing_entries': routing_entries,
        }
