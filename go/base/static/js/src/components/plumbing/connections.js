// go.components.plumbing (connections)
// ====================================
// Components for connections between endpoints in a state diagram (or
// 'plumbing view') in Go

(function(exports) {
  var views = go.components.views,
      UniqueView = views.UniqueView;

  var stateMachine = go.components.stateMachine,
      idOfConnection = stateMachine.idOfConnection;

  var structures = go.components.structures,
      SubviewCollection = structures.SubviewCollection,
      SubviewCollectionGroup = structures.SubviewCollectionGroup;

  var plumbing = go.components.plumbing,
      EndpointView = plumbing.EndpointView;

  // Base components
  // ---------------

  // View for a connection between two endpoints in a state diagram.
  //
  // Options:
  // - diagram: The diagram this connection is part of
  var ConnectionView = UniqueView.extend({
    // Override to change what params are passed to jsPlumb
    plumbOptions: {},

    uuid: function() { return this.model.id; },

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
    type: ConnectionView,
    sourceType: EndpointView,
    targetType: EndpointView,

    viewOptions: function() {
      return {diagram: this.diagram, collection: this};
    },

    constructor: function(options) {
      this.diagram = options.view;

      SubviewCollection.prototype.constructor.call(this, options);
      this.sourceType = options.sourceType || this.sourceType;
      this.targetType = options.targetType || this.targetType;
    },

    // Returns whether or not this collection accepts a connection based on the
    // types of the given source and target endpoints
    accepts: function(source, target) {
      return source instanceof this.sourceType
          && target instanceof this.targetType;
    }
  });

  // Manages the connection collections in a diagram. Keeps connection models
  // in sync with the jsPlumb connections in the UI.
  var DiagramConnectionGroup = SubviewCollectionGroup.extend({
    constructor: function(options) {
      SubviewCollectionGroup.prototype.constructor.call(this, options);
      this.diagram = this.view; // alias for better context

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
    DiagramConnectionGroup: DiagramConnectionGroup,

    connectorOverlays: connectorOverlays,
    DirectionalConnectionView: DirectionalConnectionView
  });
})(go.components.plumbing);
