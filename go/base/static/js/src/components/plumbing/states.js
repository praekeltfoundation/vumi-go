// go.components.plumbing (states)
// ===============================
// Components for states in a state diagram (or 'plumbing view') in Go

(function(exports) {
  var structures = go.components.structures,
      SubviewCollection = structures.SubviewCollection,
      SubviewCollectionGroup = structures.SubviewCollectionGroup;

  var EndpointView = go.components.plumbing.EndpointView;

  var StateViewEndpointCollection = SubviewCollection.extend({
    defaults: function() { return {type: this.view.endpointType}; },
    opts: function() {
      var opts = _(this.view).result('endpointOptions');
      opts.state = this.view;
      return opts;
    }
  });

  // Keeps track of all the endpoints in the state view
  var StateViewEndpoints = SubviewCollectionGroup.extend({
    collectionType: StateViewEndpointCollection,
    schema: function() { return _(this.view).result('endpointSchema'); }
  });

  var StateView = Backbone.View.extend({
    // Override to change the default endpoint view type
    endpointType: EndpointView,

    // A list of configuration objects, where each corresponds to a group of
    // endpoints or a single endpoint. Override to change the state schema.
    endpointSchema: [{attr: 'endpoints'}],

    // Override to change what options are passed to each new endpoint view
    endpointOptions: {},

    id: function() { return this.model.id; },

    initialize: function(options) {
      this.diagram = options.diagram;

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

  _.extend(exports, {
    // Components intended to be used and extended
    StateView: StateView,

    // Secondary components
    StateViewEndpoints: StateViewEndpoints,
    StateViewEndpointCollection: StateViewEndpointCollection
  });
})(go.components.plumbing);
