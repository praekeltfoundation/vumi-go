// go.components.plumbing (states)
// ===============================
// Components for states in a state diagram (or 'plumbing view') in Go

(function(exports) {
  var structures = go.components.structures,
      SubviewCollection = structures.SubviewCollection,
      SubviewCollectionGroup = structures.SubviewCollectionGroup;

  var plumbing = go.components.plumbing,
      EndpointView = plumbing.EndpointView,
      EndpointViewCollection = plumbing.EndpointViewCollection;

  // Keeps track of all the endpoints in the state view
  var StateViewEndpoints = SubviewCollectionGroup.extend({
    defaults: function() { return {type: this.state.endpointType}; },
    schema: function() { return _(this.state).result('endpointSchema'); },

    constructor: function(state) {
      this.state = state;  // helpful alias
      this.collectionType = this.state.endpointCollectionType;
      SubviewCollectionGroup.prototype.constructor.call(this, state);
    }
  });

  var StateView = Backbone.View.extend({
    // A list of configuration objects, where each corresponds to a group of
    // endpoints or a single endpoint. Override to change the state schema.
    endpointSchema: [{attr: 'endpoints'}],

    // Override to change the default endpoint view type
    endpointType: EndpointView,

    // Override to change the default endpoint view collection type
    endpointCollectionType: EndpointViewCollection,

    id: function() { return this.model.id; },

    initialize: function(options) {
      // the diagram view that this state is part of
      this.diagram = options.diagram;

      // the collection of state views that this state is part of
      this.collection = options.collection;

      // Lookup of all the endpoints in this state
      this.endpoints = new StateViewEndpoints(this);

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
  var StateViewCollection = SubviewCollection.extend({
    defaults: {type: StateView},
    opts: function() { return {diagram: this.view, collection: this}; }
  });

  _.extend(exports, {
    // Components intended to be used and extended
    StateView: StateView,
    StateViewCollection: StateViewCollection,

    // Secondary components
    StateViewEndpoints: StateViewEndpoints
  });
})(go.components.plumbing);
