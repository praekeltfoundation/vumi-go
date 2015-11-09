# -*- coding: utf-8 -*-
# -*- test-case-name: go.api.go_api.tests.test_api_types -*-

"""Types for the JSON RPC API for Vumi Go."""

from vumi.rpc import Unicode, List, Dict, Tag


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

    ENDPOINT_SEP = u"::"

    def __init__(self, *args, **kw):
        kw['required_fields'] = {
            'uuid': Unicode(),
            'name': Unicode(),
        }
        super(EndpointType, self).__init__(*args, **kw)

    @classmethod
    def format_uuid(cls, conn, endpoint):
        return "%s%s%s" % (conn, cls.ENDPOINT_SEP, endpoint)

    @classmethod
    def parse_uuid(cls, uuid):
        conn, _, endpoint = uuid.rpartition(cls.ENDPOINT_SEP)
        return conn, endpoint

    @classmethod
    def format_endpoint(cls, conn, endpoint, name):
        uuid = cls.format_uuid(conn, endpoint)
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
        conn = conv.get_connector()
        return {
            'uuid': conv.key,
            'type': conv.conversation_type,
            'name': conv.name,
            'status': conv.status,
            'description': conv.description,
            'endpoints': [
                EndpointType.format_endpoint(
                    conn, endpoint, name=endpoint)
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
    def format_channel(cls, channel):
        # TODO: Clean up the tag-specific stuff in here.
        pool = channel.tagpool
        tagname = channel.tag
        uuid = channel.key
        conn = channel.get_connector()
        return {
            'uuid': uuid, 'tag': (pool, tagname), 'name': tagname,
            'description': u"%s: %s" % (
                pool.replace('_', ' ').title(), tagname),
            'endpoints': [
                EndpointType.format_endpoint(
                    conn, u'default', name=u"default")
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
    def format_router(cls, router):
        in_conn = router.get_inbound_connector()
        out_conn = router.get_outbound_connector()
        channel_endpoints = router.extra_inbound_endpoints
        conversation_endpoints = router.extra_outbound_endpoints
        return {
            'uuid': router.key,
            'type': router.router_type,
            'name': router.name,
            'status': router.status,
            'description': router.description,
            'channel_endpoints': [
                EndpointType.format_endpoint(
                    in_conn, endpoint, name=endpoint)
                for endpoint in [u'default'] + list(channel_endpoints)
            ],
            'conversation_endpoints': [
                EndpointType.format_endpoint(
                    out_conn, endpoint, name=endpoint)
                for endpoint in [u'default'] + list(conversation_endpoints)
            ],
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
    def format_entry(cls, source, target):
        src_conn, src_endp = source
        dst_conn, dst_endp = target
        source_uuid = EndpointType.format_uuid(src_conn, src_endp)
        target_uuid = EndpointType.format_uuid(dst_conn, dst_endp)
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
