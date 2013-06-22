// go.components.stateMachine
// ==========================
// Models for the state-machine-like parts of the ui.
//
// XXX: The models are intended to be used as abstract structures to be
// extended and specialised. Each model's relations are not intended to remain
// as is when extended, and are more to be used as standard defaults for cases
// where further specialisation isn't required. For example, one could override
// `StateModel`'s relation's like this:
//
// ```
// var InOutStateModel = go.components.stateMachine.StateModel.extend({
//   relations: [{
//       type: Backbone.HasOne,
//       key: 'in-endpoint',
//       relatedModel: 'go.components.stateMachine.EndpointModel'
//     }, {
//       type: Backbone.HasOne,
//       key: 'out-endpoint',
//       relatedModel: 'go.components.stateMachine.EndpointModel'
//     }]
// });
// ```
//
// These models don't necessarily have to serve as the models which are syncing
// with the server side (although they can be), but can be used as intermediate
// structures between non-state-machine-like objects synced with the server,
// and the state-machine-like views. This approach ensures we don't store
// data/attributes in the views (a potential violation of the MV pattern) in
// order to cope with the different nature of the objects we sync with the
// server and the views themselves.

(function(exports) {
  var utils = go.utils,
      idOfModel = utils.idOfModel;

  var models = go.components.models,
      Model = models.Model;

  // Model for a 'placeholder' attached to a state that one end of a connection
  // can be hooked onto.
  var EndpointModel = Model.extend();

  var idOfConnection = function(source, target) {
    return idOfModel(source) + '-' + idOfModel(target);
  };

  // Model for a connection between two endpoint models
  var ConnectionModel = Model.extend({
    relations: [{
      type: Backbone.HasOne,
      key: 'source',
      includeInJSON: ['uuid'],
      relatedModel: 'go.components.stateMachine.EndpointModel'
    }, {
      type: Backbone.HasOne,
      key: 'target',
      includeInJSON: ['uuid'],
      relatedModel: 'go.components.stateMachine.EndpointModel'
    }],

    constructor: function(attrs, options) {
      // Parse by default so we can ensure we set the uuid of the connection
      options = _(options || {}).extend({parse: true});

      Model.prototype.constructor.call(this, attrs, options);
    },

    parse: function(attrs) {
      if (attrs.source && attrs.target) {
        attrs.uuid = idOfConnection(attrs.source, attrs.target);
      }

      return attrs;
    }
  });

  // Model for a single state in a state machine
  var StateModel = Model.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'endpoints',
      relatedModel: 'go.components.stateMachine.EndpointModel'
    }]
  });

  // Model for a state machine. Holds a collection of states and keeps track of
  // the initial state (`state0`).
  var StateMachineModel = Model.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'states',
      relatedModel: 'go.components.stateMachine.StateModel'
    }, {
      type: Backbone.HasOne,
      key: 'state0',
      includeInJSON: ['uuid'],
      relatedModel: 'go.components.stateMachine.StateModel'
    }, {
      type: Backbone.HasMany,
      key: 'connections',
      parse: true,
      relatedModel: 'go.components.stateMachine.ConnectionModel'
    }]
  });

  _.extend(exports, {
    idOfConnection: idOfConnection,
    EndpointModel: EndpointModel,
    ConnectionModel: ConnectionModel,
    StateModel: StateModel,
    StateMachineModel: StateMachineModel
  });
})(go.components.stateMachine = {});
