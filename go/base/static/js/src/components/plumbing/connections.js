// go.components.plumbing (connections)
// ====================================
// Components for connections between endpoints in a state diagram (or
// 'plumbing view') in Go

(function(exports) {
  var structures = go.components.structures,
      SubviewCollection = structures.SubviewCollection;

  var plumbing = go.components.plumbing,
      EndpointView = plumbing.EndpointView;

  // Base components
  // ---------------

  // View for a connection between two endpoints in a state diagram.
  //
  // Options:
  // - diagram: The diagram this connection is part of
  var ConnectionView = Backbone.View.extend({
    // Override to change what params are passed to jsPlumb
    plumbOptions: {},

    id: function() { return this.model.id; },

    initialize: function(options) {
      // the diagram view that this connection is part of
      this.diagram = options.diagram;

      // the collection of connection views that this connection is part of
      this.collection = options.collection;

      // get the source and target endpoint views from the diagram
      var endpoints = this.diagram.endpoints;
      this.source = endpoints.get(this.model.get('source').id),
      this.target = endpoints.get(this.model.get('target').id);

      // Keep a reference the actual jsPlumb connection
      this.plumbConnection = options.plumbConnection || null;
    },

    _plumbOptions: function() {
      return _.defaults({
        source: this.source.$el,
        target: this.target.$el,
        container: this.diagram.$el
      }, _(this).result('plumbOptions'));
    },

    destroy: function() {
      var plumbConnection = this.plumbConnection;

      if (plumbConnection) {
        this.plumbConnection = null;
        jsPlumb.detach(plumbConnection);
      }

      return this;
    },

    render: function() {
      if (!this.plumbConnection) {
        this.plumbConnection = jsPlumb.connect(this._plumbOptions());
      }

      return this;
    }
  });

  // A collection of connections views that form part of a diagram view
  var ConnectionViewCollection = SubviewCollection.extend({
    defaults: {
      type: ConnectionView,
      sourceType: EndpointView,
      targetType: EndpointView
    },

    opts: function() { return {diagram: this.diagram, collection: this}; },

    constructor: function(options) {
      this.diagram = options.view;

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

  // Derived components
  // ------------------

  // A lookup of overlays for jsPlumb connectors (connections)
  var connectorOverlays = {
    headArrow: [
      'Arrow', {
      width: 12,
      height: 12,
      location: 1,
      id: 'head-arrow'
    }],

    midArrow: [
      'Arrow', {
      width: 12,
      height: 12,
      location: 0.5,
      id: 'mid-arrow'
    }]
  };

  var DirectionalConnectionView = ConnectionView.extend({
    plumbOptions: function() {
      return {overlays: [connectorOverlays.headArrow]};
    }
  });

  _.extend(exports, {
    ConnectionView: ConnectionView,
    ConnectionViewCollection: ConnectionViewCollection,

    connectorOverlays: connectorOverlays,
    DirectionalConnectionView: DirectionalConnectionView
  });
})(go.components.plumbing);
