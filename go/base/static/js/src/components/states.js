// go.components.states
// ====================
// Models for the state-machine-like parts of the ui.
//
// XXX: The models are intended to be used as abstract structures to be
// extended and specialised. Each model's relations are not intended to remain
// as is when extended, and are more to be used as standard defaults for cases
// where further specialisation isn't required. For example, one could override
// `StateModel`'s relation's like this:
//
// ```
// var InOutStateModel = go.components.states.StateModel.extend({
//   relations: [{
//       type: Backbone.HasOne,
//       key: 'in-endpoint',
//       relatedModel: 'go.components.states.EndpointModel'
//     }, {
//       type: Backbone.HasOne,
//       key: 'out-endpoint',
//       relatedModel: 'go.components.states.EndpointModel'
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
  // Model for a 'placeholder' attached to a state that one end of a connection
  // can be hooked onto.
  exports.EndpointModel = Backbone.RelationalModel.extend({
    relations: [{
      type: Backbone.HasOne,
      key: 'target',
      includeInJSON: 'id',
      relatedModel: 'go.components.states.EndpointModel'
    }]
  });

  // Model for a single state in a state machine
  exports.StateModel = Backbone.RelationalModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'endpoints',
      relatedModel: 'go.components.states.EndpointModel'
    }]
  });

  // Model for a state machine. Holds a collection of states and keeps track of
  // the initial state (`state0`).
  exports.StateMachineModel = Backbone.RelationalModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'states',
      relatedModel: 'go.components.states.StateModel'
    }, {
      type: Backbone.HasOne,
      key: 'state0',
      includeInJSON: 'id',
      relatedModel: 'go.components.states.StateModel'
    }]
  });
})(go.components.states = {});
