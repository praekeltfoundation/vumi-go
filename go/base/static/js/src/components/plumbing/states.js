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

  var StateView = UniqueView.extend({
    // A list of configuration objects, where each corresponds to a group of
    // endpoints or a single endpoint. Override to change the state schema.
    endpointSchema: [{attr: 'endpoints'}],

    // Default endpoint view type
    endpointType: EndpointView,

    // Default endpoint view collection type
    endpointCollectionType: EndpointViewCollection,

    uuid: function() { return this.model.id; },

    initialize: function(options) {
      // the diagram view that this state is part of
      this.diagram = options.diagram;

      // the collection of state views that this state is part of
      this.collection = options.collection;

      // Lookup of all the endpoints in this state
      this.endpoints = new SubviewCollectionGroup({
        view: this,
        schema: this.endpointSchema,
        schemaDefaults: {type: this.endpointType},
        collectionType: this.endpointCollectionType
      });

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
    type: StateView,

    viewOptions: function() { return {diagram: this.view, collection: this}; },

    remove: function(viewOrId, options) {
      var view = this.get(this.idOfView(viewOrId)),
          endpoints = view.endpoints;

      endpoints.each(function(e) { endpoints.remove(e, options); });
      return SubviewCollection.prototype.remove.call(this, view, options);
    }
  });

  _.extend(exports, {
    // Components intended to be used and extended
    StateView: StateView,
    StateViewCollection: StateViewCollection
  });
})(go.components.plumbing);
