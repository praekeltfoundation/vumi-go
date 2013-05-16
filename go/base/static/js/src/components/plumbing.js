// go.components.plumbing
// ======================
//
// Components for the plumbing views in Go

(function(exports) {
  var Extendable = go.utils.Extendable,
      Eventable = go.utils.Eventable,
      delegateEvents = go.utils.delegateEvents,
      pop = go.utils.pop,
      parent = go.utils.parent;

  // Dispatches jsPlumb events to the subscribed `PlumbEndpoint`s
  //
  // Options
  //   - plumb: jsPlumb instance
  //   - endpoints: a list of initial endpoints to add
  exports.PlumbEventDispatcher = Extendable.extend({
    constructor: function(options) {
      var self = this;

      options = _.defaults(options || {}, {endpoints: []});
      this.plumb = options.plumb;

      this._endpoints = {};
      options.endpoints.map(this.subscribe);

      jsPlumb.bind('jsPlumbConnection', function(e) {
        var source = e.sourceHost = self.get(e.sourceEndpoint.getUuid()),
            target = e.targetHost = self.get(e.targetEndpoint.getUuid());

        // Overwrite the jsPlumb endpoint objects with our PlumbEndpoint
        // objects (if we needed access to the jsPlumb objects, they would
        // be accessible from our PlumbEndpoint objects)
        e.sourceEndpoint = source;
        e.targetEndpoint = target;

        source.trigger('plumb:connect', e);
        target.trigger('plumb:connect', e);
      });
    },

    // Get a subscribed endpoint by its id
    get: function(id) { return this._endpoints[id]; },

    // Subscribe an endpoint
    subscribe: function(endpoint) {
      this._endpoints[endpoint.id] = endpoint;
      return this;
    },

    // Unsubscribe an endpoint
    unsubscribe: function(id) {
      delete this._endpoints[id];
      return this;
    }
  });

  // A wrapper for jsPlumb Endpoints to make them work nicer with Backbone
  // Models and Views.
  //
  // Options
  //   - id: The endpoint's id
  //   - host: The view to which this endpoint is to be attached
  //   - attr: The hosts's model attribute associated to this endpoint. This
  //   attribute is set to the id of the target endpoint's host's model once
  //   the target is set
  //   - [jsPlumb Endpoint params]
  var PlumbEndpoint = exports.PlumbEndpoint = Eventable.extend({
    events: {'plumb:connect': 'connected'},

    constructor: function(options) {
      parent(this, 'constructor')();

      this.id = options.id;
      this.host = options.host;
      this.attr = options.attr;
      this.target = null;

      var plumbParams = _.extend(_.omit(options, 'id', 'host', 'attr'), {
        uuid: this.id,
        isSource: true,
        isTarget: true
      });
      
      this.raw = jsPlumb.addEndpoint(this.host.$el, plumbParams);
    },

    setTarget: function(target) {
      this.target = target;
      this.host.model.set(this.attr, target.host.model.id);
    },

    connected: function(e) {
      if (this === e.sourceEndpoint) { this.setTarget(e.targetEndpoint); }
    },

    // connect `this` endpoint to another endpoint
    connect: function(endpoint) {
      return jsPlumb.connect({source: this.raw, target: endpoint.raw});
    }
  });
})(go.components.plumbing = {});
