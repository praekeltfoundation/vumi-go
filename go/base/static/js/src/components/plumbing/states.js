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
      EndpointViewCollection = plumbing.EndpointViewCollection,
      StateEndpointGroup = plumbing.StateEndpointGroup;

  var StateView = UniqueView.extend({
    endpointSchema: [{attr: 'endpoints'}],
    endpointType: EndpointView,
    endpointCollectionType: EndpointViewCollection,
    endpointGroupType: StateEndpointGroup,

    uuid: function() { return this.model.id; },

    initialize: function(options) {
      // The diagram view that this state is part of
      this.diagram = options.diagram;

      // The collection of state views that this state is part of
      this.collection = options.collection;

      // Lookup of all the endpoints in this state
      this.endpoints = new this.endpointGroupType({
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

  // Keeps track of a diagrams's states
  var DiagramStateGroup = SubviewCollectionGroup.extend();

  _.extend(exports, {
    // Components intended to be used and extended
    StateView: StateView,
    StateViewCollection: StateViewCollection,
    DiagramStateGroup: DiagramStateGroup
  });
})(go.components.plumbing);
