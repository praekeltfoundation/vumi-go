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

    * uuid: 'endpoint-uuid-1'
    * name: 'default'
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

        * uuid: 'routing-block-uuid-2',
        * type: 'bulk-message',
        * name: 'bulk-message-1',
        * description: 'Some Bulk Message App',
        * endpoints: [{uuid: 'endpoint-uuid-4', name: 'default'}]
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
        return {
            'uuid': conv.key,
            'type': conv.conversation_type,
            'name': conv.name,
            'description': conv.description,
            'endpoints': [
                # TODO: add additional endpoints once we know how to list them
                EndpointType.format_endpoint(
                    uuid=u"%s:%s" % (conv.key, u'default'), name=u"default")
            ],
        }


class ChannelType(Dict):
    """Description of a channel.

    The following keys are required:

    * uuid: 'channel-uuid-1',
    * tag: ['apposit_sms', '*121#'],
    * name: '*121#',
    * description: 'Apposit Sms: *121#',
    * endpoints: [{uuid: 'endpoint-uuid-1', name: 'default'}]
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
        return {
            'uuid': uuid, 'tag': tag, 'name': tagname,
            'description': u"%s: %s" % (
                pool.replace('_', ' ').title(), tagname),
            'endpoints': [
                EndpointType.format_endpoint(
                    uuid=u"%s:%s" % (uuid, u'default'), name=u"default")
            ]
        }


class RoutingBlockType(Dict):
    """Description of a routing block.

    The following keys are required:

    * uuid: 'routing-block-uuid-1',
    * type: 'keyword',
    * name: 'keyword-routing-block',
    * description: 'Keyword',
    * channel_endpoints: [{uuid: 'endpoint-uuid-2', name: 'default'}],
    * conversation_endpoints: [{uuid: 'endpoint-uuid-3', name: 'default'}]
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
        super(RoutingBlockType, self).__init__(*args, **kw)

    @classmethod
    def format_routing_block(cls, uuid, rb_type, name, description,
                             channel_endpoints, conversation_endpoints):
        return {
            'uuid': uuid, 'type': rb_type, 'name': name,
            'description': description, 'channel_endpoints': channel_endpoints,
            'conversation_endpoints': conversation_endpoints,
        }


class RoutingEntryType(Dict):
    """Description of an entry in a routing table.

    The following keys are required:

    * source: {uuid: 'endpoint-uuid-1'},
    * target: {uuid: 'endpoint-uuid-2'}
    """
    def __init__(self, *args, **kw):
        uuid_dict = Dict(required_fields={'uuid': Unicode()})
        kw['required_fields'] = {
            'source': uuid_dict,
            'target': uuid_dict,
        }
        super(RoutingEntryType, self).__init__(*args, **kw)

    def format_entry(self, source_uuid, target_uuid):
        return {
            'source': {'uuid': source_uuid},
            'target': {'uuid': target_uuid},
        }


class RoutingType(Dict):
    """Description of a campaign routing table.

    The following keys are required:

    * channels: A list of `ChannelType` values.
    * routing_blocks: A list of `RoutingBlockType` values.
    * conversations: A list of `ConversationType` values.
    * routing_entries: A list of `RoutingEntryType` values.
    """

    def __init__(self, *args, **kw):
        kw['required_fields'] = {
            'channels': List(item_type=ChannelType()),
            'routing_blocks': List(item_type=RoutingBlockType()),
            'conversations': List(item_type=ConversationType()),
            'routing_entries': List(item_type=RoutingEntryType()),
        }
        super(RoutingType, self).__init__(*args, **kw)

    @classmethod
    def format_routing(cls, channels, routing_blocks, conversations,
                       routing_entries):
        return {
            'channels': channels,
            'routing_blocks': routing_blocks,
            'conversations': conversations,
            'routing_entries': routing_entries,
        }
