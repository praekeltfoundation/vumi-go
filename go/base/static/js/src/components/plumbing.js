// go.components.plumbing
// ======================
//
// Components for the plumbing views in Go

(function(exports) {
  var structures = go.components.structures,
      utils = go.utils;

  var Lookup = structures.Lookup,
      ViewCollectionGroup = structures.ViewCollectionGroup,
      ViewCollection = structures.ViewCollection;


  // View for a single endpoint on a state in a state diagram.
  //
  // Options:
  // - state: The view to which this endpoint is to be attached
  var EndpointView = Backbone.View.extend({
    // Default params passed to jsPlumb when creating the jsPlumb endpoint
    plumbDefaults: {isSource: true, isTarget: true},

    initialize: function(options) {
      this.state = options.state;

      // Keep a reference to the actua; jsPlumb endpoint
      this.plumbEndpoint = null;

      this.on('connect', this.onConnect, this);
      this.on('disconnect', this.onDisconnect, this);
      this.model.on('change', this.render, this);
    },

    // Makes the plumb params passed to jsPlumb when creating the endpoint.
    // Override when extending `EndpointView` to specialise what params are
    // passed to jsPlumb
    plumbParams: function() {
      return _.defaults({uuid: this.model.id}, this.plumbDefaults);
    },

    onConnect: function(source, target, plumbEvent) {
      if (this === source) { this.model.set('target', target.model); }
    },

    onDisconnect: function(source, target, plumbEvent) {
      if (this === source) { this.model.unset('target'); }
    },

    destroy: function() {
      if (this.plumbEndpoint) { jsPlumb.deleteEndpoint(this.plumbEndpoint); }
      return this;
    },

    render: function() {
      if (!this.plumbEndpoint) {
        this.plumbEndpoint = jsPlumb.addEndpoint(
          this.state.$el,
          this.plumbParams());
      }
      return this;
    }
  });

  // Options:
  // - state: The state view associated to the group of endpoints
  // - attr: The attr on the state view's model which holds the collection
  // of endpoints or the endpoint model
  // - [type]: The view type to instantiate for each new endpoint view.
  // Defaults to EndpointView.
  var StateEndpointCollection = ViewCollection.extend({
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
  var StateEndpoints = ViewCollectionGroup.extend({
    Collection: StateEndpointCollection,

    constructor: function(state) {
      ViewCollectionGroup.prototype.constructor.call(this);

      this.state = state;
      this.schema = this.state.endpointSchema;
      this.schema.forEach(this.subscribe, this);
    },

    subscribe: function(options) {
      _.extend(options, {state: this.state});
      var endpoints = new this.Collection(options);

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
    Endpoints: StateEndpoints,

    // A list of configuration objects, where each corresponds to a group of
    // endpoints or a single endpoint. Override to change the state schema.
    endpointSchema: [{attr: 'endpoints'}],

    id: function() { return this.model.id; },

    initialize: function(options) {
      this.diagram = options.diagram;
      this.endpoints = new this.Endpoints(this);
      this.model.on('change', this.render, this);
    },

    render: function() {
      this.diagram.$el.append(this.$el);
      return this;
    }
  });

  // Arguments:
  // - diagram: The state diagram view associated to the endpoints
  var StateDiagramEndpoints = ViewCollectionGroup.extend({
    constructor: function(diagram) {
      ViewCollectionGroup.prototype.constructor.call(this);
      this.diagram = diagram;

      jsPlumb.bind(
        'connection',
        _.bind(this.delegateEvent, this, 'connection'));

      jsPlumb.bind(
        'connectionDetached',
        _.bind(this.delegateEvent, this, 'disconnection'));

      // Add the initial states' endpoints
      var states = this.diagram.states;
      states.eachItem(
        function(id, endpoint) { this.addState(id, endpoint); },
        this);

      states.on('add', this.addState, this);
      states.on('remove', this.addRemove, this);
    },

    addState: function(id, state) { this.subscribe(id, state.endpoints); },

    removeState: function(id) { return this.unsubscribe(id); },

    delegateEvent: function(type, plumbEvent) {
      var source = this.get(plumbEvent.sourceEndpoint.getUuid()),
          target = this.get(plumbEvent.targetEndpoint.getUuid());

      if (source && target) { 
        source.trigger(type, source, target, plumbEvent);
        target.trigger(type, source, target, plumbEvent);
      }
    }
  });

  // View for a connection between two endpoints in a state diagram.
  //
  // Options:
  // - source: The source endpoint view
  // - target: The target endpoint view
  var ConnectionView = Backbone.View.extend({
    plumbDefaults: {},

    initialize: function(options) {
      this.source = options.source;
      this.target = options.target;

      // Keep a reference the actual jsPlumb connection
      this.plumbConnection = null;
    },

    // Makes the plumb params passed to jsPlumb when creating the connection.
    // Override when extending `EndpointConnection` to specialise what params
    // are passed to jsPlumb
    plumbParams: function() {
      return _.defaults(
        {source: this.source.plumbEndpoint, target: this.target.plumbEndpoint},         this.plumbDefaults);
    },

    destroy: function() {
      if (this.plumbConnection) { jsPlumb.detach(this.plumbConnection); }
      return this;
    },

    render: function() {
      if (this.plumbConnection) {
        this.plumbConnection = jsPlumb.connect(this.plumbParams());
      }
      return this;
    }
  });


  // Arguments:
  // - diagram: The state diagram view associated to the endpoints
  var StateDiagramConnections = Lookup.extend({
    View: ConnectionView,

    constructor: function(diagram) {
      Lookup.prototype.constructor.call(this);

      this.diagram = diagram;

      var endpoints = this.diagram.endpoints;
      endpoints.each(this.subscribeEndpoint, this);

      endpoints.on('add', this.subscribeEndpoint, this);
      endpoints.on('remove', this.unsubscribeEndpoint, this);

      // Check which endpoint models were connected upon initialisation and add
      // the initial connections accordingly
      endpoints.each(function(e){
        var sourceModel = e.model,
            targetModel = sourceModel.get('target');

        if (targetModel) { this.add(sourceModel.id, targetModel.id); }
      }, this);
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

    add: function(sourceId, targetId) {
      var endpoints = this.diagram.endpoints,
          source = endpoints.source,
          target = endpoints.target,
          connection = new this.View({source: source, target: target});

      return Lookup.prototype.add.call(this, sourceId, connection);
    },

    render: function() { this.each(function(c) { c.render(); }); }
  });

  // Options:
  // - diagram: The diagram view assocModeliated to the state group
  // - attr: The attr on the state view's model which holds the collection
  // of states
  // - [type]: The view type to instantiate for each new state view. Defaults
  // to StateView.
  var StateDiagramStateCollection = ViewCollection.extend({
    View: StateView,

    constructor: function(options) {
      this.diagram = options.diagram;
      this.attr = options.attr;
      this.type = options.type || this.View;

      ViewCollection
        .prototype
        .constructor
        .call(this, this.diagram.model.get(this.attr));
    },

    create: function(model) {
      return new this.type({diagram: this.diagram, model: model});
    }
  });
  
  // Arguments:
  // - diagram: The diagram view associated to the states
  var StateDiagramStates = ViewCollectionGroup.extend({
    StateCollection: StateDiagramStateCollection,

    constructor: function(diagram) {
      ViewCollectionGroup.prototype.constructor.call(this);

      this.diagram = diagram;
      this.schema = this.diagram.stateSchema;
      this.schema.forEach(this.subscribe, this);
    },

    subscribe: function(options) {
      _.extend(options, {diagram: this.diagram});
      var endpoints = new this.StateCollection(options);

      return ViewCollectionGroup
        .prototype
        .subscribe
        .call(this, options.attr, endpoints);
    }
  });

  // The main view for the state diagram. Delegates interactions between
  // the states and their endpoints.
  var StateDiagramView = Backbone.View.extend({
    // Override these if further specialisation is needed
    States: StateDiagramStates,
    Endpoints: StateDiagramEndpoints,
    Connections: StateDiagramConnections,

    // A list of configuration objects, where each corresponds to a group of
    // states. Override to change the state schema.
    stateSchema: [{attr: 'states'}],

    initialize: function() {
      this.states = new this.States(this);
      this.endpoints = new this.Endpoints(this);
      this.connections = new this.Connections(this);
    },

    render: function() {
      this.states.render();
      this.connections.render();
      return this;
    }
  });

  _.extend(exports, {
      // The main components that would typically be used and extended
      EndpointView: EndpointView,
      StateView: StateView,
      StateDiagramView: StateDiagramView,

      // The secondary components that are used by the main components above,
      // but can be extended if need be
      StateEndpointCollection: StateEndpointCollection,
      StateEndpoints: StateEndpoints,
      StateDiagramEndpoints: StateDiagramEndpoints,
      ConnectionView: StateDiagramConnections,
      StateDiagramConnections: StateDiagramConnections,
      StateDiagramStateCollection: StateDiagramStateCollection,
      StateDiagramStates: StateDiagramStates
  });
})(go.components.plumbing = {});
