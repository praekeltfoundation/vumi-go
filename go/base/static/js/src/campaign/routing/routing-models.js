// go.components.routing (models)
// ==============================
// Models for campaign routing screen.

var stateMachine = go.components.stateMachine,
    EndpointModel = stateMachine.EndpointModel,
    ConnectionModel = stateMachine.ConnectionModel,
    StateModel = stateMachine.StateModel,
    StateMachineModel = stateMachine.StateMachineModel;

(function(exports) {
  var ChannelModel = StateModel.extend({
    relations: [{
      type: Backbone.HasOne,
      key: 'endpoint',
      relatedModel: EndpointModel
    }]
  });

  var RoutingBlockModel = StateModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'application_endpoints',
      relatedModel: EndpointModel
    }, {
      type: Backbone.HasMany,
      key: 'channel_endpoints',
      relatedModel: EndpointModel
    }]
  });

  var ApplicationModel = StateModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'endpoints',
      relatedModel: EndpointModel
    }]
  });

  var CampaignRoutingModel = StateMachineModel.extend({
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
      key: 'applications',
      relatedModel: ApplicationModel
    }, {
      type: Backbone.HasMany,
      key: 'connections',
      relatedModel: ConnectionModel
    }]
  });

  _.extend(exports, {
    ChannelModel: ChannelModel,
    RoutingBlockModel: RoutingBlockModel,
    ApplicationModel: ApplicationModel,
    CampaignRoutingModel: CampaignRoutingModel
  });
})(go.components.routing);
