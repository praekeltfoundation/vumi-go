// go.routing (models)
// ===================
// Models for routing screen.

// We use the state machine models as a base to make use of any
// custom/overriden functionality the models provide over Backbone.Model,
// seeing as the models for routing are of a state machine nature.
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
    }],
    viewURL: function(){
      return '/channels/' + encodeURIComponent(this.get('tag').join(':')) + '/';
    }
  });

  var RouterModel = StateModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'conversation_endpoints',
      relatedModel: RoutingEndpointModel
    }, {
      type: Backbone.HasMany,
      key: 'channel_endpoints',
      relatedModel: RoutingEndpointModel
    }],
    viewURL: function(){
      return '/routers/' + encodeURI(this.id) + '/edit/';
    }
  });

  var ConversationModel = StateModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'endpoints',
      relatedModel: RoutingEndpointModel
    }],
    viewURL: function(){
      return '/conversations/' + encodeURI(this.id) + '/edit/';
    }
  });

  var RoutingModel = StateMachineModel.extend({
    methods: {
      read: {
        method: 'routing_table',
        params: ['campaign_id']
      },
      update: {
        method: 'update_routing_table',
        params: function() {
          return [this.get('campaign_id'), this];
        }
      }
    },

    idAttribute: 'campaign_id',

    relations: [{
      type: Backbone.HasMany,
      key: 'channels',
      relatedModel: ChannelModel
    }, {
      type: Backbone.HasMany,
      key: 'routers',
      relatedModel: RouterModel
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
    RoutingModel: RoutingModel,

    ChannelModel: ChannelModel,
    RouterModel: RouterModel,
    ConversationModel: ConversationModel,

    RoutingEntryModel: RoutingEntryModel,
    RoutingEndpointModel: RoutingEndpointModel
  });
})(go.routing.models = {});
