// go.campaign.routing (models)
// ============================
// Models for campaign routing screen.

// We use the state machine models as a base to make use of any
// custom/overriden functionality the models provide over Backbone.Model,
// seeing as the models for campaign routing are of a state machine nature.
var stateMachine = go.components.stateMachine,
    EndpointModel = stateMachine.EndpointModel,
    ConnectionModel = stateMachine.ConnectionModel,
    StateModel = stateMachine.StateModel,
    StateMachineModel = stateMachine.StateMachineModel;

(function(exports) {
  var RoutingEndpointModel = EndpointModel.extend({
  });

  var RoutingEntryModel = ConnectionModel.extend({
    relations: [{
      type: Backbone.HasOne,
      key: 'source',
      includeInJSON: ['uuid'],
      relatedModel: RoutingEndpointModel
    }, {
      type: Backbone.HasOne,
      key: 'target',
      includeInJSON: ['uuid'],
      relatedModel: RoutingEndpointModel
    }]
  });

  var ChannelModel = StateModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'endpoints',
      relatedModel: RoutingEndpointModel
    }]
  });

  var RoutingBlockModel = StateModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'conversation_endpoints',
      relatedModel: RoutingEndpointModel
    }, {
      type: Backbone.HasMany,
      key: 'channel_endpoints',
      relatedModel: RoutingEndpointModel
    }]
  });

  var ConversationModel = StateModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'endpoints',
      relatedModel: RoutingEndpointModel
    }]
  });

  var CampaignRoutingModel = StateMachineModel.extend({
    methods: {
      read: ['routing_table', 'campaign_id'],
      update: ['update_routing_table', 'campaign_id', 'self']
    },

    idAttribute: 'campaign_id',

    relations: [{
      type: Backbone.HasMany,
      key: 'channels',
      relatedModel: ChannelModel
    }, {
      type: Backbone.HasMany,
      key: 'routing_blocks',
      relatedModel: RoutingBlockModel
    }, {
      type: Backbone.HasMany,
      key: 'conversations',
      relatedModel: ConversationModel
    }, {
      type: Backbone.HasMany,
      key: 'routing_entries',
      parse: true,
      relatedModel: RoutingEntryModel
    }]
  });

  _.extend(exports, {
    CampaignRoutingModel: CampaignRoutingModel,

    ChannelModel: ChannelModel,
    RoutingBlockModel: RoutingBlockModel,
    ConversationModel: ConversationModel,

    RoutingEntryModel: RoutingEntryModel,
    RoutingEndpointModel: RoutingEndpointModel
  });
})(go.campaign.routing);
