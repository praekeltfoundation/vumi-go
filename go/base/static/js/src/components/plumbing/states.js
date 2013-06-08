// go.components.plumbing (states)
// ===============================
// Components for states in a state diagram (or 'plumbing view') in Go

(function(exports) {
  var structures = go.components.structures,
      SubviewCollection = structures.SubviewCollection,
      SubviewCollectionGroup = structures.SubviewCollectionGroup;

  var plumbing = go.components.plumbing,
      Endpoint = plumbing.Endpoint,
      EndpointCollection = plumbing.EndpointCollection;

  // Keeps track of all the endpoints in the state view
  var StateEndpoints = SubviewCollectionGroup.extend({
    defaults: function() { return {type: this.state.endpointType}; },
    schema: function() { return _(this.state).result('endpointSchema'); },

    constructor: function(state) {
      this.state = state;  // helpful alias
      this.collectionType = this.state.endpointCollectionType;
      SubviewCollectionGroup.prototype.constructor.call(this, state);
    }
  });

  var State = Backbone.View.extend({
    // A list of configuration objects, where each corresponds to a group of
    // endpoints or a single endpoint. Override to change the state schema.
    endpointSchema: [{attr: 'endpoints'}],

    // Override to change the default endpoint view type
    endpointType: Endpoint,

    // Override to change the default endpoint view collection type
    endpointCollectionType: EndpointCollection,

    id: function() { return this.model.id; },

    initialize: function(options) {
      // the diagram view that this state is part of
      this.diagram = options.diagram;

      // the collection of state views that this state is part of
      this.collection = options.collection;

      // Lookup of all the endpoints in this state
      this.endpoints = new StateEndpoints(this);

      this.model.on('change', this.render, this);
    },

    destroy: function() {
      this.$el.remove();
      return this;
    },

    render: function() {
      this.diagram.$el.append(this.$el);
      this.endpoints.render();
      return this;
    }
  });

  // A collection of state views that form part of a diagram view
  var StateCollection = SubviewCollection.extend({
    defaults: {type: State},
    opts: function() { return {diagram: this.view, collection: this}; }
  });

  _.extend(exports, {
    // Components intended to be used and extended
    State: State,
    StateCollection: StateCollection,

    // Secondary components
    StateEndpoints: StateEndpoints
  });
})(go.components.plumbing);
