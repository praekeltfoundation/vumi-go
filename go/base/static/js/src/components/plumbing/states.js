// go.components.plumbing (states)
// ===============================
// Components for states in a state diagram (or 'plumbing view') in Go

(function(exports) {
  var views = go.components.views,
      UniqueView = views.UniqueView;

  var structures = go.components.structures,
      SubviewCollection = structures.SubviewCollection,
      SubviewCollectionGroup = structures.SubviewCollectionGroup;

  var endpoints = go.components.plumbing.endpoints,
      EndpointView = endpoints.EndpointView,
      EndpointViewCollection = endpoints.EndpointViewCollection,
      StateEndpointGroup = endpoints.StateEndpointGroup;

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
    },

    isConnected: function() {
      var endpoints = this.endpoints.values(),
          i = endpoints.length;

      while (i--) { if (endpoints[i].isConnected()) { return true; } }
      return false;
    },

    destroy: function() {
      this.$el.remove();
      return this;
    },

    render: function() {
      this.collection.appendToView(this);
      this.endpoints.render();
      return this;
    },

    connectedEndpoints: function() {
      var results = [];

      // using internal properties here for performance reasons, this method is
      // sometimes used on each 'drag' event for diagrams with draggable states
      var connections = this.diagram.connections._itemList;
      var endpoints = this.endpoints._itemList;
      var connectionsLen = connections.length;
      var endpoint, conn, target, source;
      var i, j;

      i = endpoints.length;

      while (i--) {
        endpoint = endpoints[i].value;
        j = connectionsLen;

        while (j--) {
          conn = connections[j].value;
          source = conn.source;
          target = conn.target;

          if (target === endpoint || source === endpoint) {
            results.push(source);
            results.push(target);
          }
        }
      }

      return results;
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

  // Keeps track of a diagrams's states
  var DiagramStateGroup = SubviewCollectionGroup.extend();

  _.extend(exports, {
    // Components intended to be used and extended
    StateView: StateView,
    StateViewCollection: StateViewCollection,
    DiagramStateGroup: DiagramStateGroup
  });
})(go.components.plumbing.states = {});
