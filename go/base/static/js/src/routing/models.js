// go.routing (models)
// ===================
// Models for routing screen.

// We use the state machine models as a base to make use of any
// custom/overriden functionality the models provide over Backbone.Model,
// seeing as the models for routing are of a state machine nature.
(function(exports) {
  var stateMachine = go.components.stateMachine,
      EndpointModel = stateMachine.EndpointModel,
      ConnectionModel = stateMachine.ConnectionModel,
      StateModel = stateMachine.StateModel,
      StateMachineModel = stateMachine.StateMachineModel;

  var RoutingEndpointModel = EndpointModel.extend({});

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

  var RoutingStateCollection = Backbone.Collection.extend({
    type: null,

    bindings: {
      'add': function(model) {
        model.set('ordinal', this.localOrdinals.indexOf(model.id));
      }
    },

    initialize: function(models, options) {
      this.routingId = options.routingId;
      this.localOrdinals = go.local.get(this._localOrdinalsKey(), []);
      go.utils.bindEvents(this.bindings, this);
    },

    persistOrdinals: function() {
      go.local.set(this._localOrdinalsKey(), this._getOrdinals());
    },

    _getOrdinals: function() {
      return _.pluck(this.sortBy('ordinal'), 'id');
    },

    _localOrdinalsKey: function() {
      return localOrdinalsKey(this.routingId, this.type);
    }
  });

  var ChannelCollection = RoutingStateCollection.extend({
    type: 'channels'
  });

  var RouterCollection = RoutingStateCollection.extend({
    type: 'routers'
  });

  var ConversationCollection = RoutingStateCollection.extend({
    type: 'conversations'
  });

  var RoutingStateModel = StateModel.extend({
    defaults: {ordinal: -1}
  });

  var ChannelModel = RoutingStateModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'endpoints',
      relatedModel: RoutingEndpointModel
    }],
    viewURL: function(){
      return '/channels/' + encodeURIComponent(this.get('tag').join(':')) + '/';
    }
  });

  var RouterModel = RoutingStateModel.extend({
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

  var ConversationModel = RoutingStateModel.extend({
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
      relatedModel: ChannelModel,
      collectionType: ChannelCollection,
      collectionOptions: stateCollectionOptions
    }, {
      type: Backbone.HasMany,
      key: 'routers',
      relatedModel: RouterModel,
      collectionType: RouterCollection,
      collectionOptions: stateCollectionOptions
    }, {
      type: Backbone.HasMany,
      key: 'conversations',
      relatedModel: ConversationModel,
      collectionType: ConversationCollection,
      collectionOptions: stateCollectionOptions
    }, {
      type: Backbone.HasMany,
      key: 'routing_entries',
      parse: true,
      relatedModel: RoutingEntryModel
    }],

    persistOrdinals: function() {
      this.get('channels').persistOrdinals();
      this.get('routers').persistOrdinals();
      this.get('conversations').persistOrdinals();
      this.trigger('persist:ordinals');
    }
  });


  function stateCollectionOptions(routing) {
    return {routingId: routing.id};
  }


  function localOrdinalsKey(id, type) {
    return [id, type, 'ordinals'].join(':');
  }


  _.extend(exports, {
    RoutingModel: RoutingModel,
    RoutingStateCollection: RoutingStateCollection,

    RoutingStateModel: RoutingStateModel,
    ChannelModel: ChannelModel,
    RouterModel: RouterModel,
    ConversationModel: ConversationModel,

    RoutingEntryModel: RoutingEntryModel,
    RoutingEndpointModel: RoutingEndpointModel,

    localOrdinalsKey: localOrdinalsKey
  });
})(go.routing.models = {});
