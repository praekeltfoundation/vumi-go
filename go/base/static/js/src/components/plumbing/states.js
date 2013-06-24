// go.components.plumbing (states)
// ===============================
// Components for states in a state diagram (or 'plumbing view') in Go

(function(exports) {
  var views = go.components.views,
      UniqueView = views.UniqueView;

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

  var StateView = UniqueView.extend({
    // A list of configuration objects, where each corresponds to a group of
    // endpoints or a single endpoint. Override to change the state schema.
    endpointSchema: [{attr: 'endpoints'}],

    // Override to change the default endpoint view type
    endpointType: EndpointView,

    // Override to change the default endpoint view collection type
    endpointCollectionType: EndpointViewCollection,

    uuid: function() { return this.model.id; },

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
      this.collection.appendToView(this);
      this.endpoints.render();
      return this;
    }
  });

  // A collection of state views that form part of a diagram view
  var StateViewCollection = SubviewCollection.extend({
    type: StateView,

    viewOptions: function() { return {diagram: this.view, collection: this}; },

    remove: function(viewOrId, options) {
      var view = this.resolveView(viewOrId),
          endpoints = view.endpoints;

      endpoints.each(function(e) { endpoints.remove(e, options); });
      return SubviewCollection.prototype.remove.call(this, view, options);
    }
  });

  _.extend(exports, {
    // Components intended to be used and extended
    StateView: StateView,
    StateViewCollection: StateViewCollection,

    // Secondary components
    StateViewEndpoints: StateViewEndpoints
  });
})(go.components.plumbing);
