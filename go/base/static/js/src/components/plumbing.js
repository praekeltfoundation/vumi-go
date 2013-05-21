// go.components.plumbing
// ======================
//
// Components for the plumbing views in Go

(function(exports) {
  var GoError = go.errors.GoError,
      merge = go.utils.merge,
      parent = go.utils.parent,
      pairId = go.utils.pairId;

  var PlumbError = exports.PlumbError = GoError.subtype('PlumbError');

  // Endpoints
  // ---------
  // Placeholders attached to a state that allow states to be connected
  
  exports.EndpointModel = Backbone.RelationalModel.extend({
    relations: [{
      type: Backbone.HasOne,
      key: 'target',
      includeInJSON: 'id',
      relatedModel: 'go.components.plumbing.EndpointModel'
    }]
  });

  exports.EndpointCollection = Backbone.Collection.extend({
    model: exports.EndpointModel
  });

  // View which wraps a jsPlumb Endpoint to make it work nicer with Backbone
  //
  // Options:
  // - host: The view to which this endpoint is to be attached
  exports.EndpointView = Backbone.View.extend({
    // Default params passed to jsPlumb when creating the jsPlumb endpoint
    plumbDefaults: {
      isSource: true,
      isTarget: true
    },

    initialize: function(options) {
      _.bindAll(
        this,
        'onConnect',
        'onDisconnect',
        'render');

      this.host = options.host;
      this.attr = options.attr;

      // Keep a reference to the 'raw' jsPlumb endpoint
      this.raw = jsPlumb.addEndpoint(this.host.$el, this.plumbParams(options));

      // Give the view the actual element jsPlumb uses so we can register UI
      // events and interact with the element directly
      this.setElement(this.raw.canvas);

      this.on('connect', this.onConnect);
      this.on('disconnect', this.onDisconnect);
    },

    // Makes the plumb params passed to jsPlumb when creating the endpoint.
    // Override when extending `EndpointView` to specialise what params are
    // passed to jsPlumb
    plumbParams: function(options) {
      return _.defaults({uuid: this.model.id}, this.plumbDefaults);
    },

    onConnect: function(e) {
      if (this === e.source) { this.model.set('target', e.target.model); }
    },

    onDisconnect: function(e) {
      if (this === e.source) { this.model.unset('target'); } }
  });

  // States
  // ------
  // States/nodes/things that host endpoints to connect them to each other

  exports.StateModel = Backbone.RelationalModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'endpoints',
      relatedModel: 'go.components.plumbing.EndpointModel',
      collectionType: 'go.components.plumbing.EndpointCollection'
    }]
  });

  exports.StateView = Backbone.View.extend({
    // Can be overriden when extending `StateView` to specialise the endpoint
    // view type
    EndpointView: exports.EndpointView,

    initialize: function(options) {
      _.bindAll(
        this,
        'addEndpoint',
        'removeEndpoint',
        'render');

      this.endpoints = {};
      this.model.on('change', this.render);
    },

    addEndpoint: function(id) {
      var model = this.model.get('endpoints').get(id);

      if (!model) throw new PlumbError(
        "StateView instance's model has no endpoint with id '" + id + "'");

      this.endpoints[id] = new this.EndpointView({host: this, model: model});
    },

    removeEndpoint: function(id) {
      jsPlumb.deleteEndpoint(this.endpoints.raw);
      delete this.endpoints[id];
    },

    render: function() {
      var modelEndpoints = this.model.get('endpoints'),
          modelEndpointIds = modelEndpoints.map(function(e) { return e.id; }),
          viewEndpointIds = _.keys(this.endpoints);

       // Remove 'dead' endpoints
       // (endpoint views with models that no longer exist)
       _.difference(viewEndpointIds, modelEndpointIds)
        .forEach(this.removeEndpoint);

       // Add 'new' endpoints
       // (endpoint models with no corresponding views)
       _.difference(modelEndpointIds, viewEndpointIds)
        .forEach(this.addEndpoint);
    }
  });

  // Main components
  // ---------------

  // The main view containing state views. Delegates interactions between
  // the states and their endpoints.
  //
  // Options
  //   - [states]: A list of initial state views to add
  //   - Backbone options
  exports.PlumbView = Backbone.View.extend({
    initialize: function(options) {
      _.bindAll(
        this,
        'connect',
        'disconnect',
        'onConnection',
        'onDisconnection',
        'render');

      // The contained state views
      this.states = options.states || [];

      // Lookup that keeps track of all the states' endpoint views
      this.endpoints = {};

      // Lookup that keeps track of the jsPlumb connections in this view
      this.connections = {};

      jsPlumb.bind('connection', this.onConnection);
      jsPlumb.bind('connectionDetached', this.onDisconnection);
    },

    _delegateEvent: function(source, target, type, params) {
        params = _.extend(params || {}, {source: source, target: target});
        source.trigger(type, params);
        target.trigger(type, params);
    },

    onConnection: function(e) {
      var sourceId = e.sourceEndpoint.getUuid(),
          targetId = e.targetEndpoint.getUuid(),
          source = this.endpoints[sourceId],
          target = this.endpoints[targetId],
          event;

      if (source && target) { 
        this.connections[pairId(sourceId, targetId)] = e.connection;
        this._delegateEvent(source, target, 'connection');
      }
    },

    onDisconnection : function(e) {
      var sourceId = e.sourceEndpoint.getUuid(),
          targetId = e.targetEndpoint.getUuid(),
          source = this.endpoints[sourceId],
          target = this.endpoints[targetId],
          event;

      if (source && target) { 
        delete this.connections[pairId(sourceId, targetId)];
        this._delegateEvent(source, target, 'disconnection');
      }
    },

    connect: function(source, target) {
      return jsPlumb.connect({source: source.raw, target: target.raw});
    },

    disconnect: function(connectionId) {
      var connection = this.connections[connectionId];

      if (!connection) throw new PlumbError(
        "PlumbView has no connection with id '" + connectionId + "'");

      jsPlumb.detach(connection);
    },

    addState: function(state) {
      this.states.push(state);
      this.render();
    },

    render: function() {
      var endpoints,
          connectionIds,
          connectedEndpointIds,
          connectedEndpoints;

      this.states.forEach(function(s) { s.render(); });

      // Update the endpoint lookup
      endpoints = this.endpoints = merge.apply(
        this, this.states.map(function(s) { return s.endpoints; }));

      // Get endpoints that are connected according to their models
      connectedEndpoints = {};
      _.values(endpoints).forEach(function(source) {
        var targetModel = source.model.get('target'),
            connectionId,
            target;

        if (!targetModel) { return; }

        target = endpoints[targetModel.id];
        if (target) {
          connectionId = pairId(source.model.id, targetModel.id);
          connectedEndpoints[connectionId] = [source, target];
        }
      });

      connectionIds = _.keys(this.connections);
      connectedEndpointIds = _.keys(connectedEndpoints);

      // Remove 'dead' connections
      // (connections that are still drawn, but aren't connected according to
      // the endpoints models)
      _.difference(connectionIds, connectedEndpointIds)
       .forEach(this.disconnect);

      // Add 'new' connections
      // (connections that haven't yet been drawn, but exist according to the
      // endpoint models)
      _.difference(connectedEndpointIds, connectionIds)
       .forEach(function(id) {
         var endpoints = connectedEndpoints[id];
         this.connect(endpoints[0], endpoints[1]); 
       }.bind(this));
    }
  });
})(go.components.plumbing = {});
