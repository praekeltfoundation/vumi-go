// go.components.plumbing (diagrams)
// =================================
// Components for state diagrams (or 'plumbing views') in Go

(function(exports) {
  var plumbing = go.components.plumbing,
      StateView = plumbing.StateView,
      ConnectionView = plumbing.ConnectionView,
      StateViewCollection = plumbing.StateViewCollection,
      ConnectionViewCollection = plumbing.ConnectionViewCollection,
      DiagramStateGroup = plumbing.DiagramStateGroup,
      DiagramConnectionGroup = plumbing.DiagramConnectionGroup,
      DiagramEndpointGroup = plumbing.DiagramEndpointGroup;

  // The main view for the state diagram. Delegates interactions between
  // the states and their endpoints.
  var DiagramView = Backbone.View.extend({
    stateSchema: [{attr: 'states'}],
    stateType: StateView,
    stateCollectionType: StateViewCollection,

    connectionSchema: [{attr: 'connections'}],
    connectionType: ConnectionView,
    connectionCollectionType: ConnectionViewCollection,

    initialize: function() {
      // Lookup/Manager of all the states in the diagram
      this.states = new DiagramStateGroup({
        view: this,
        schema: this.stateSchema,
        schemaDefaults: {type: this.stateType},
        collectionType: this.stateCollectionType
      });

      // Lookup/Manager of all the endpoints in the diagram
      this.endpoints = new DiagramEndpointGroup(this);

      // Lookup/Manager of all the connections in the diagram
      this.connections = new DiagramConnectionGroup({
        view: this,
        schema: this.connectionSchema,
        schemaDefaults: {type: this.connectionType},
        collectionType: this.connectionCollectionType
      });

      // Set the view as the default container so jsPlumb connects endpoint
      // elements properly.
      //
      // https://github.com/sporritt/jsPlumb/wiki/setup
      // #overriding-the-default-behaviour
      jsPlumb.Defaults.Container = this.$el;
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
})(go.components.plumbing);
