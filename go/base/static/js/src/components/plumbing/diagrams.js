// go.components.plumbing (diagrams)
// =================================
// Components for state diagrams (or 'plumbing views') in Go

(function(exports) {
  var plumbing = go.components.plumbing;

  var states = plumbing.states,
      StateView = states.StateView,
      StateViewCollection = states.StateViewCollection,
      DiagramStateGroup = states.DiagramStateGroup;

  var endpoints = plumbing.endpoints,
      DiagramEndpointGroup = endpoints.DiagramEndpointGroup;

  var connections = plumbing.connections,
      ConnectionView = connections.ConnectionView,
      ConnectionViewCollection = connections.ConnectionViewCollection,
      DiagramConnectionGroup = connections.DiagramConnectionGroup;

  // The main view for the state diagram. Delegates interactions between
  // the states and their endpoints.
  var DiagramView = Backbone.View.extend({
    stateSchema: [{attr: 'states'}],
    stateType: StateView,
    stateCollectionType: StateViewCollection,
    stateGroupType: DiagramStateGroup,

    connectionSchema: [{attr: 'connections'}],
    connectionType: ConnectionView,
    connectionCollectionType: ConnectionViewCollection,
    connectionGroupType: DiagramConnectionGroup,

    endpointGroupType: DiagramEndpointGroup,

    initialize: function() {
      // Set the view as the default container so jsPlumb connects endpoint
      // elements properly.
      jsPlumb.setContainer(this.$el);

      // Lookup/manager of all the states in the diagram
      this.states = new this.stateGroupType({
        view: this,
        schema: this.stateSchema,
        schemaDefaults: {type: this.stateType},
        collectionType: this.stateCollectionType
      });

      // Lookup/manager of all the endpoints in the diagram
      this.endpoints = new this.endpointGroupType(this);

      // Lookup/manager of all the connections in the diagram
      this.connections = new this.connectionGroupType({
        view: this,
        schema: this.connectionSchema,
        schemaDefaults: {type: this.connectionType},
        collectionType: this.connectionCollectionType
      });
    },

    render: function() {
      this.states.render();
      this.connections.render();
      return this;
    }
  });

  _.extend(exports, {
    DiagramView: DiagramView
  });
})(go.components.plumbing.diagrams = {});
