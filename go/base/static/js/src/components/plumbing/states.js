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
    View: EndpointView,

    constructor: function(options) {
      this.state = options.state;
      this.attr = options.attr;
      this.type = options.type || this.View;

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
      return new this.type({state: this.state, model: model});
    }
  });

  // Arguments:
  // - state: The state view associated to the endpoints
  var StateViewEndpoints = ViewCollectionGroup.extend({
    constructor: function(state) {
      ViewCollectionGroup.prototype.constructor.call(this);

      this.state = state;
      this.schema = this.state.endpointSchema;
      this.schema.forEach(this.subscribe, this);
    },

    subscribe: function(options) {
      _.extend(options, {state: this.state});
      var endpoints = new this.state.EndpointCollection(options);

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
    EndpointCollection: StateViewEndpointCollection,

    // A list of configuration objects, where each corresponds to a group of
    // endpoints or a single endpoint. Override to change the state schema.
    endpointSchema: [{attr: 'endpoints'}],

    id: function() { return this.model.id; },

    initialize: function(options) {
      this.diagram = options.diagram;
      this.endpoints = new StateViewEndpoints(this);
      this.model.on('change', this.render, this);
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
    StateViewEndpointCollection: StateViewEndpointCollection,

    // Secondary components exposed for testing purposes
    StateViewEndpoints: StateViewEndpoints
  });
})(go.components.plumbing);
