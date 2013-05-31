// go.components.plumbing (states)
// ===============================
// Components for states in a state diagram (or 'plumbing view') in Go

(function(exports) {
  var structures = go.components.structures,
      ViewCollectionGroup = structures.ViewCollectionGroup,
      ViewCollection = structures.ViewCollection;

  var EndpointView = go.components.plumbing.EndpointView;

  // Options:
  // - state: The state view associated to the group of endpoints
  // - attr: The attr on the state view's model which holds the collection
  // of endpoints or the endpoint model
  // - [type]: The view type to instantiate for each new endpoint view.
  // Defaults to EndpointView.
  var StateViewEndpointCollection = ViewCollection.extend({
    constructor: function(options) {
      this.state = options.state;
      this.attr = options.attr;
      this.type = options.type || this.state.EndpointView;

      ViewCollection
        .prototype
        .constructor
        .call(this, this._models());
    },

    _models: function() {
      var modelOrCollection = this.state.model.get(this.attr);

      // If we were given a single model instead of a collection, create a
      // singleton collection with the model so we can work with things
      // uniformally
      return modelOrCollection instanceof Backbone.Model
        ? new Backbone.Collection([modelOrCollection])
        : modelOrCollection;
    },

    create: function(model) {
      return new this.type(_.defaults(
        {state: this.state, model: model},
        this.state.endpointOptions()));
    }
  });

  // Arguments:
  // - state: The state view associated to the endpoints
  var StateViewEndpoints = ViewCollectionGroup.extend({
    constructor: function(state) {
      ViewCollectionGroup
        .prototype
        .constructor
        .call(this);

      this.state = state;
      this.schema = this.state.endpointSchema;
      this.schema.forEach(this.subscribe, this);
    },

    subscribe: function(options) {
      _.extend(options, {state: this.state});
      var endpoints = new StateViewEndpointCollection(options);

      return ViewCollectionGroup
        .prototype
        .subscribe
        .call(this, options.attr, endpoints);
    }
  });

  // View for a single state in a state diagram
  //
  // Options:
  // - diagram: the diagram view that the state view belongs to
  var StateView = Backbone.View.extend({
    // Override to change the default endpoint view type
    EndpointView: EndpointView,

    // A list of configuration objects, where each corresponds to a group of
    // endpoints or a single endpoint. Override to change the state schema.
    endpointSchema: [{attr: 'endpoints'}],

    // Override to change what options are passed to each new endpoint view
    endpointOptions: function () { return {}; },

    id: function() { return this.model.id; },

    initialize: function(options) {
      this.diagram = options.diagram;

      // Lookup of all the endpoints in this state
      this.endpoints = new StateViewEndpoints(this);

      this.model.on('change', this.render, this);
    },

    render: function() {
      this.diagram.$el.append(this.$el);
      this.endpoints.render();
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
