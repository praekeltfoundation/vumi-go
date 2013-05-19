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
  
  exports.EndpointModel = Backbone.Model.extend({
    initialize: function() {
      if (!this.has('targetId')) { this.set('targetId', null); }
    }
  });

  exports.EndpointCollection = Backbone.Collection.extend({
    model: exports.EndpointModel
  });

  // View which wraps a jsPlumb Endpoint to make it work nicer with Backbone
  //
  // Options - host: The view to which this endpoint is to be attached -
  // [jsPlumb Endpoint params]
  exports.EndpointView = Backbone.View.extend({
    initialize: function(options) {
      this.host = options.host;
      this.attr = options.attr;

      var plumbParams = _.extend(
        _.omit(options, 'host'),
        {uuid: this.model.id, isSource: true, isTarget: true});

      // Keep a reference to the 'raw' jsPlumb endpoint
      this.raw = jsPlumb.addEndpoint(this.host.$el, plumbParams);

      // Give the view the actual element jsPlumb uses so we can register UI
      // events and interact with the element directly
      this.setElement(this.raw.canvas);
    }
  });

  // States
  // ------
  // States/nodes/things that host endpoints to connect them to each other

  exports.StateModel = Backbone.Model.extend({
    // Can be overriden when extending `StateModel` to specialise the endpoint
    // model type
    EndpointCollection: exports.EndpointCollection,

    constructor: function(attrs, options) {
      // Force the model to parse when initialized so we the 'endpoints'
      // attribute of the model can be parsed correctly as an endpoint
      // collection
      options = _.extend(options || {}, {parse: true});

      parent(this, 'constructor')(attrs, options);
    },

    parseEndpoints: function(data) {
      var endpoints = new this.EndpointCollection(data || []);

      // Make the model aware of changes to the endpoint collection
      endpoints.on('all', function(event, model, collection, options) {
        this.trigger('change', this, options);
      }.bind(this));

      return endpoints;
    },

    parse: function(response, options) {
      var attrs = parent(this, 'parse')(response, options);
      attrs.endpoints = this.parseEndpoints(attrs.endpoints);
      return attrs;
    }
  });

  // Options:
  //   - endpointOptions: The default options to pass to each newly created
  //   endpoint view
  //   - Backbone options
  exports.StateView = Backbone.View.extend({
    // Can be overriden when extending `StateView` to specialise the endpoint
    // view type
    EndpointView: exports.EndpointView,

    // The default endpoint options given to each endpoint
    endpointOptions: {},

    initialize: function(options) {
      _.bindAll(
        this,
        'addEndpoint',
        'removeEndpoint',
        'render');

      this.endpoints = {};

      this.endpointOptions = _.defaults(
        {host: this},
        options.endpointOptions || {},
        this.endpointOptions);

      this.model.on('change', this.render);
    },

    addEndpoint: function(id) {
      var model = this.model.get('endpoints').get(id),
          options = _.clone(this.endpointOptions);

      if (!model) throw new PlumbError(
        "StateView instance's model has no endpoint with id '" + id + "'");

      options.model = model;
      this.endpoints[id] = new this.EndpointView(options);
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

  // The main view containing `PlumbStateView`s. Acts as a controller for
  // the `PlumbStateView`s and their backing `PlumbStateModel`s.
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

    onConnection: function(e) {
      var sourceId = e.sourceEndpoint.getUuid(),
          targetId = e.targetEndpoint.getUuid(),
          source = this.endpoints[sourceId],
          target = this.endpoints[targetId];

      if (source && target) { 
        this.connections[pairId(sourceId, targetId)] = e.connection;
        source.model.set('targetId', targetId);
      }
    },

    onDisconnection : function(e) {
      var sourceId = e.sourceEndpoint.getUuid(),
          targetId = e.targetEndpoint.getUuid(),
          source = this.endpoints[sourceId],
          target = this.endpoints[targetId];

      if (source && target) { 
        delete this.connections[pairId(sourceId, targetId)];
        source.model.set('targetId', null);
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
         var sourceId = source.model.id,
             targetId = source.model.get('targetId'),
             target;

         if (!targetId) { return; }

         target = endpoints[targetId];
         if (target) {
           connectedEndpoints[pairId(sourceId, targetId)] = [source, target];
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
