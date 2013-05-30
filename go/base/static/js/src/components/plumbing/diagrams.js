// go.components.plumbing (diagrams)
// =================================
// Components for state diagrams (or 'plumbing views') in Go

(function(exports) {
  var structures = go.components.structures,
      Lookup = structures.Lookup,
      ViewCollectionGroup = structures.ViewCollectionGroup,
      ViewCollection = structures.ViewCollection;
      
  var plumbing = go.components.plumbing,
      StateView = plumbing.StateView,
      ConnectionView = plumbing.ConnectionView;

  // Arguments:
  // - diagram: The state diagram view associated to the endpoints
  var DiagramViewEndpoints = ViewCollectionGroup.extend({
    constructor: function(diagram) {
      ViewCollectionGroup
        .prototype
        .constructor
        .call(this);

      this.diagram = diagram;

      // Add the initial states' endpoints
      var states = diagram.states;
      states.eachItem(
        function(id, endpoint) { this.addState(id, endpoint); },
        this);

      states.on('add', this.addState, this);
      states.on('remove', this.addRemove, this);
    },

    addState: function(id, state) { this.subscribe(id, state.endpoints); },
    removeState: function(id) { return this.unsubscribe(id); }
  });

  // Keeps connections between endpoint models in sync with the jsPlumb
  // connections in the UI
  //
  // Arguments:
  // - diagram: The state diagram view associated to the endpoints
  var DiagramViewConnections = Lookup.extend({
    addDefaults: {render: true},

    constructor: function(diagram) {
      Lookup.prototype.constructor.call(this);
      this.diagram = diagram;

      var endpoints = this.diagram.endpoints;
      endpoints.each(this.subscribeEndpoint, this);
      endpoints.on('add', this.subscribeEndpoint, this);
      endpoints.on('remove', this.unsubscribeEndpoint, this);

      // Check which endpoint models were connected upon initialisation and add
      // the initial connections accordingly
      endpoints.each(this._initConnection, this);

      jsPlumb.bind(
        'connection',
        _.bind(this.onPlumbConnect, this));

      jsPlumb.bind(
        'connectionDetached',
        _.bind(this.onPlumbDisconnect, this));
    },

    _initConnection: function(endpoint) {
      var sourceModel = endpoint.model,
          targetModel = sourceModel.get('target');

      if (targetModel) {
        this.add(
          sourceModel.id,
          targetModel.id,
          {render: false});
      }
    },

    subscribeEndpoint: function(endpoint) {
      endpoint.model.on('change:target', this.onTargetChange, this);
      return this;
    },

    unsubscribeEndpoint: function(endpoint) {
      endpoint.model.off('change:target', this.onTargetChange, this);
      return this;
    },

    onTargetChange: function(sourceModel, targetModel) {
      // If the target has been set, connect.
      // Otherwise, the target has been unset, so disconnect.
      if (targetModel) { this.add(sourceModel.id, targetModel.id); }
      else { this.remove(sourceModel.id); }
    },

    onPlumbConnect: function(e) {
      var connection = this.add(
        e.sourceEndpoint.getUuid(),
        e.targetEndpoint.getUuid(),
        {render: false});

      connection.trigger('connect', e);
    },

    onPlumbDisconnect: function(e) {
      var connection = this.get(e.sourceEndpoint.getUuid());
      connection.trigger('disconnect', e);
    },

    add: function(sourceId, targetId, options) {
      _.defaults(options, this.addDefaults);
      var connection = this.get(sourceId);

      // return connection if it already exists
      if (connection) { return connection; }

      var endpoints = this.diagram.endpoints,
          source = endpoints.get(sourceId),
          target = endpoints.get(targetId);

      connection = new this.diagram.ConnectionView({
        source: source,
        target: target
      });

      // add the connection, keyed by the sourceId
      Lookup
        .prototype
        .add
        .call(this, sourceId, connection);

      if (options.render) { connection.render(); }
      return connection;
    },

    remove: function(sourceId) {
      var connection = this.get(sourceId);
      connection.destroy();

      return Lookup
        .prototype
        .remove
        .call(this, sourceId);
    },

    render: function() { this.each(function(c) { c.render(); }); }
  });

  // Options:
  // - diagram: The diagram view associated to the state group
  // - attr: The attr on the state view's model which holds the collection
  // of states
  // - [type]: The view type to instantiate for each new state view. Defaults
  // to StateView.
  var DiagramViewStateCollection = ViewCollection.extend({
    constructor: function(options) {
      this.diagram = options.diagram;
      this.attr = options.attr;
      this.type = options.type || this.diagram.StateView;

      ViewCollection
        .prototype
        .constructor
        .call(this, this.diagram.model.get(this.attr));
    },

    create: function(model) {
      return new this.type(_.defaults(
        {diagram: this.diagram, model: model},
        this.diagram.stateOptions()));
    }
  });
  
  // Arguments:
  // - diagram: The diagram view associated to the states
  var DiagramViewStates = ViewCollectionGroup.extend({
    constructor: function(diagram) {
      ViewCollectionGroup.prototype.constructor.call(this);

      this.diagram = diagram;
      this.schema = this.diagram.stateSchema;
      this.schema.forEach(this.subscribe, this);
    },

    subscribe: function(options) {
      _.extend(options, {diagram: this.diagram});
      var endpoints = new DiagramViewStateCollection(options);

      return ViewCollectionGroup
        .prototype
        .subscribe
        .call(this, options.attr, endpoints);
    }
  });

  // The main view for the state diagram. Delegates interactions between
  // the states and their endpoints.
  var DiagramView = Backbone.View.extend({
    // Override to change the default state view type
    StateView: StateView,

    // Override to change the connection view type
    ConnectionView: ConnectionView,

    // A list of configuration objects, where each corresponds to a group of
    // states. Override to change the state schema.
    stateSchema: [{attr: 'states'}],

    // Override to change what options are passed to each new state view
    stateOptions: function() { return {}; },

    initialize: function() {
      // Lookup of all the states in the diagram
      this.states = new DiagramViewStates(this);

      // Lookup of all the endpoints in the diagram
      this.endpoints = new DiagramViewEndpoints(this);

      // Lookup of all the connections in the diagram
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
    DiagramViewStates: DiagramViewStates,
    DiagramViewEndpoints: DiagramViewEndpoints,
    DiagramViewConnections: DiagramViewConnections,
    DiagramViewStateCollection: DiagramViewStateCollection
  });
})(go.components.plumbing);
