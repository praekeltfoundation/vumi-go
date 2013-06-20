// go.components.plumbing (diagrams)
// =================================
// Components for state diagrams (or 'plumbing views') in Go

(function(exports) {
  var structures = go.components.structures,
      Lookup = structures.Lookup,
      SubviewCollectionGroup = structures.SubviewCollectionGroup,
      ViewCollectionGroup = structures.ViewCollectionGroup;

  var plumbing = go.components.plumbing,
      StateView = plumbing.StateView,
      ConnectionView = plumbing.ConnectionView,
      StateViewCollection = plumbing.StateViewCollection,
      ConnectionViewCollection = plumbing.ConnectionViewCollection;

  var stateMachine = go.components.stateMachine,
      idOfConnection = stateMachine.idOfConnection;

  // Keeps track of all the endpoints in the state diagram
  var DiagramViewEndpoints = ViewCollectionGroup.extend({
    constructor: function(diagram) {
      ViewCollectionGroup.prototype.constructor.call(this);
      this.diagram = diagram;

      // Add the initial states' endpoints
      var states = diagram.states;
      states.eachItem(this.addState, this);

      states.on('add', this.addState, this);
      states.on('remove', this.removeState, this);
    },

    addState: function(id, state) { this.subscribe(id, state.endpoints); },

    removeState: function(id) { this.unsubscribe(id); }
  });

  // Keeps connections between connection models in sync with the jsPlumb
  // connections in the UI
  var DiagramViewConnections = SubviewCollectionGroup.extend({
    defaults: function() {
      // Get the default endpoint type for the diagram's default state type
      var endpointType = this.diagram
        .stateType
        .prototype
        .endpointType;

      return {
        type: this.view.connectionType,
        sourceType: endpointType,
        targetType: endpointType
      };
    },

    schema: function() { return _(this.diagram).result('connectionSchema'); },

    constructor: function(diagram) {
      this.diagram = diagram;  // helpful alias
      this.collectionType = this.diagram.connectionCollectionType;
      SubviewCollectionGroup.prototype.constructor.call(this, diagram);

      jsPlumb.bind(
        'connection',
        _.bind(this.onPlumbConnect, this));

      jsPlumb.bind(
        'connectionDetached',
        _.bind(this.onPlumbDisconnect, this));
    },

    // Returns the first connection collection found that accepts a connection
    // based on the type of the given source and target endpoints. We need this
    // to determine which connection collection a new connection made in the ui
    // belongs to.
    determineCollection: function(source, target) {
      var collections = this.members.values(),
          i = collections.length,
          c;

      while (i--) {
        c = collections[i];
        if (c.accepts(source, target)) { return c; }
      }

      return null;
    },

    onPlumbConnect: function(e) {
      var sourceId = e.source.attr('data-uuid'),
          targetId = e.target.attr('data-uuid'),
          connectionId = idOfConnection(sourceId, targetId);

      // Case 1:
      // -------
      // The connection model and its view have been added, but we haven't
      // rendered the view (drawn the jsPlumb connection) yet. We don't
      // need to add the connection since it already exists.
      if (this.has(connectionId)) { return; }

      // Case 2:
      // -------
      // The connection was created in the UI, so no model or view exists yet.
      // We need to create a new connection model and its view.
      var source = this.diagram.endpoints.get(sourceId),
          target = this.diagram.endpoints.get(targetId),
          collection = this.determineCollection(source, target);

      // Case 3:
      // -------
      // This kind of connection is not supported
      if (collection === null) {
        this.trigger('error:unsupported', source, target, e.connection);
        return;
      }

      collection.add({
        model: {source: source.model, target: target.model},
        plumbConnection: e.connection
      });
    },

    onPlumbDisconnect: function(e) {
      var sourceId = e.source.attr('data-uuid'),
          targetId = e.target.attr('data-uuid'),
          connectionId = idOfConnection(sourceId, targetId);

      // Case 1:
      // -------
      // The connection model and its view have been removed from its
      // collection, so its connection view was destroyed (along with the
      // jsPlumb connection). We don't need to remove the connection model
      // and view since they no longer exists.
      if (!this.has(connectionId)) { return; }

      // Case 2:
      // -------
      // The connection was removed in the UI, so the model and view still
      // exist. We need to remove them.
      var collection = this.ownerOf(connectionId);
      collection.remove(connectionId, {removeModel: true});
    }
  });

  // Keeps track of all the states in a state diagram
  var DiagramViewStates = SubviewCollectionGroup.extend({
    defaults: function() { return {type: this.diagram.stateType}; },
    schema: function() { return _(this.diagram).result('stateSchema'); },

    constructor: function(diagram) {
      this.diagram = diagram;  // helpful alias
      this.collectionType = this.diagram.stateCollectionType;
      SubviewCollectionGroup.prototype.constructor.call(this, diagram);
    }
  });

  // The main view for the state diagram. Delegates interactions between
  // the states and their endpoints.
  var DiagramView = Backbone.View.extend({
    // Override to change how the states map to the diagram view's model
    stateSchema: [{attr: 'states'}],

    // Override to change the default state view type
    stateType: StateView,

    // Override to change the default state view collection type
    stateCollectionType: StateViewCollection,

    // Override to change how the connections map to the diagram view's model
    connectionSchema: [{attr: 'connections'}],

    // Override to change the connection view type
    connectionType: ConnectionView,

    // Override to change the default connection view collection type
    connectionCollectionType: ConnectionViewCollection,

    initialize: function() {
      // Lookup/Manager of all the states in the diagram
      this.states = new DiagramViewStates(this);

      // Lookup/Manager of all the endpoints in the diagram
      this.endpoints = new DiagramViewEndpoints(this);

      // Lookup/Manager of all the connections in the diagram
      this.connections = new DiagramViewConnections(this);

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
    // Components intended to be used and extended
    DiagramView: DiagramView,

    // Secondary components
    DiagramViewEndpoints: DiagramViewEndpoints,
    DiagramViewConnections: DiagramViewConnections,
    DiagramViewStates: DiagramViewStates
  });
})(go.components.plumbing);
