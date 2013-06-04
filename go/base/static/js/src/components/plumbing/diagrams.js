// go.components.plumbing (diagrams)
// =================================
// Components for state diagrams (or 'plumbing views') in Go

(function(exports) {
  var structures = go.components.structures,
      Lookup = structures.Lookup,
      SubviewCollection = structures.SubviewCollection,
      SubviewCollectionGroup = structures.SubviewCollectionGroup,
      ViewCollectionGroup = structures.ViewCollectionGroup;

  var plumbing = go.components.plumbing,
      StateView = plumbing.StateView,
      ConnectionView = plumbing.ConnectionView,
      idOfConnection = plumbing.idOfConnection;

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

  var DiagramViewConnectionCollection = SubviewCollection.extend({
    defaults: function() {
      var endpointType = this.view
        .stateType
        .prototype
        .endpointType;

      return {
        type: this.view.connectionType,
        sourceType: endpointType,
        targetType: endpointType
      };
    },

    opts: function() {
      return _.defaults(
        {diagram: this.view, collection: this},
        _(this.view).result('connectionOptions'));
    },

    constructor: function(options) {
      SubviewCollection.prototype.constructor.call(this, options);
      this.sourceType = options.sourceType;
      this.targetType = options.targetType;
    },

    // Returns whether or not this collection accepts a connection based on the
    // types of the given source and target endpoints
    accepts: function(source, target) {
      return source instanceof this.sourceType
          && target instanceof this.targetType;
    }
  });

  // Keeps connections between connection models in sync with the jsPlumb
  // connections in the UI
  var DiagramViewConnections = SubviewCollectionGroup.extend({
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
    },

    onPlumbConnect: function(e) {
      var sourceId = e.sourceEndpoint.getUuid(),
          targetId = e.targetEndpoint.getUuid(),
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

      collection.add({
        id: connectionId,
        source: source.model,
        target: target.model
      }, {
        addModel: true,
        view: {plumbConnection: e.connection}
      });
    },

    onPlumbDisconnect: function(e) {
      var sourceId = e.sourceEndpoint.getUuid(),
          targetId = e.targetEndpoint.getUuid(),
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
      var source = this.diagram.endpoints.get(sourceId),
          target = this.diagram.endpoints.get(targetId),
          collection = this.determineCollection(source, target);

      // If we remove the model, the connection view collection will recognise
      // this and remove the corresponding view.
      collection.remove(connectionId, {removeModel: true});
    }
  });

  var DiagramViewStateCollection = SubviewCollection.extend({
    defaults: function() { return {type: this.view.stateType}; },
    opts: function() {
      return _.defaults(
        {diagram: this.view, collection: this},
        _(this.view).result('stateOptions'));
    }
  });

  // Keeps track of all the states in a state diagram
  var DiagramViewStates = SubviewCollectionGroup.extend({
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

    // Override to change what options are passed to each new state view
    stateOptions: {},

    // Override to change the default state view type
    stateType: StateView,

    // Override to change the default state view collection type
    stateCollectionType: DiagramViewStateCollection,

    // Override to change how the connections map to the diagram view's model
    connectionSchema: [{attr: 'connections'}],

    // Override to change what options are passed to each new connection view
    connectionOptions: {},
 
    // Override to change the connection view type
    connectionType: ConnectionView,

    // Override to change the default connection view collection type
    connectionCollectionType: DiagramViewConnectionCollection,

    initialize: function() {
      // Lookup/Manager of all the states in the diagram
      this.states = new DiagramViewStates(this);

      // Lookup/Manager of all the endpoints in the diagram
      this.endpoints = new DiagramViewEndpoints(this);

      // Lookup/Manager of all the connections in the diagram
      this.connections = new DiagramViewConnections(this);
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
    DiagramViewConnectionCollection: DiagramViewConnectionCollection,
    DiagramViewConnections: DiagramViewConnections,
    DiagramViewStates: DiagramViewStates,
    DiagramViewStateCollection: DiagramViewStateCollection
  });
})(go.components.plumbing);
