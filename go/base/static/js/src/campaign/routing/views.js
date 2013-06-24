// go.campaign.routing (views)
// ===========================
// Views for campaign routing diagram.

(function(exports) {
  var plumbing = go.components.plumbing;

  var states = plumbing.states,
      StateView = states.StateView,
      StateViewCollection = states.StateViewCollection;

  var endpoints = plumbing.endpoints,
      ParametricEndpointView = endpoints.ParametricEndpointView,
      AligningEndpointCollection = endpoints.AligningEndpointCollection;

  var connections = plumbing.connections,
      DirectionalConnectionView = connections.DirectionalConnectionView,
      ConnectionViewCollection = connections.ConnectionViewCollection,
      connectorOverlays = connections.connectorOverlays;

  var diagrams = plumbing.diagrams,
      DiagramView = diagrams.DiagramView;

  // Endpoints
  // ---------

  var RoutingEndpointView = ParametricEndpointView.extend({
    className: 'endpoint label',
    render: function() {
      this.$el.text(this.model.get('name'));
      return ParametricEndpointView.prototype.render.call(this);
    }
  });

  var ChannelEndpointView = RoutingEndpointView.extend(),
      RoutingBlockChannelEndpointView = RoutingEndpointView.extend(),
      RoutingBlockConversationEndpointView = RoutingEndpointView.extend(),
      ConversationEndpointView = RoutingEndpointView.extend();

  // Routing entries (connections)
  // -----------------------------

  var RoutingEntryCollection = ConnectionViewCollection.extend({
    acceptedPairs: [
      [ChannelEndpointView, RoutingBlockChannelEndpointView],
      [ConversationEndpointView, RoutingBlockConversationEndpointView],
      [ChannelEndpointView, ConversationEndpointView]],

    accepts: function(source, target) {
      var pairs = this.acceptedPairs,
          i = pairs.length,
          pair, a, b;

      while (i--) {
        pair = pairs[i], a = pair[0], b = pair[1];
        if (source instanceof a && target instanceof b) { return true; }
        if (target instanceof a && source instanceof b) { return true; }
      }

      return false;
    }
  });

  // States
  // ------

  var RoutingStateView = StateView.extend({
    endpointType: RoutingEndpointView,
    endpointCollectionType: AligningEndpointCollection,

    initialize: function(options) {
      StateView.prototype.initialize.call(this, options);
      this.$name = $('<span></span>').attr('class', 'name');
    },

    render: function() {
      this.collection.appendToView(this);

      this.$el
        .css('position', 'relative')
        .append(this.$name);

      this.$name.text(this.model.get('name'));
      this.endpoints.render();

      return this;
    }
  });

  var ChannelStateView = RoutingStateView.extend({
    className: 'state channel',
    endpointSchema: [{
      attr: 'endpoints',
      side: 'right',
      type: ChannelEndpointView
    }]
  });

  var RoutingBlockStateView = RoutingStateView.extend({
    className: 'state routing-block',
    endpointSchema: [{
      attr: 'channel_endpoints',
      side: 'left',
      type: RoutingBlockChannelEndpointView
    }, {
      attr: 'conversation_endpoints',
      side: 'right',
      type: RoutingBlockConversationEndpointView
    }]
  });

  var ConversationStateView = RoutingStateView.extend({
    className: 'state conversation',
    endpointSchema: [{
      attr: 'endpoints',
      side: 'left',
      type: ConversationEndpointView
    }]
  });

  var RoutingStateCollection = StateViewCollection.extend({
    initialize: function(options) {
      this.$column = this.view.$(options.columnEl);
    },

    appendToView: function(viewOrId) {
      var subview = this.resolveView(viewOrId);
      this.$column.append(subview.$el);
    }
  });

  // Columns
  // -------

  // A vertical section of the routing diagram dedicated to a particular
  // collection of the three state types (Channel, RoutingBlock or
  // Conversation).
  var RoutingColumnView = Backbone.View.extend({
    initialize: function(options) {
      this.diagram = options.diagram;
      this.states = this.diagram.states.members.get(this.collectionName);
      this.setElement(this.diagram.$('#' + this.id));
    },

    repaint: function() { jsPlumb.repaintEverything(); },

    render: function() {
      this.states.each(function(s) { s.render(); });

      // Allow the user to 'shuffle' the states in the column, repainting the
      // jsPlumb connections and endpoints on each update hook
      this.$el.sortable({
        start: this.repaint,
        sort: this.repaint,
        stop: this.repaint
      });
    }
  });

  var ChannelColumnView = RoutingColumnView.extend({
    id: 'channels',
    collectionName: 'channels'
  });

  var RoutingBlockColumnView = RoutingColumnView.extend({
    id: 'routing-blocks',
    collectionName: 'routing_blocks'
  });

  var ConversationColumnView = RoutingColumnView.extend({
    id: 'conversations',
    collectionName: 'conversations'
  });

  // Main components
  // ---------------

  var RoutingDiagramView = DiagramView.extend({
    stateCollectionType: RoutingStateCollection,
    stateSchema: [{
      attr: 'channels',
      type: ChannelStateView,
      columnEl: '#channels'
    }, {
      attr: 'routing_blocks',
      type: RoutingBlockStateView,
      columnEl: '#routing-blocks'
    }, {
      attr: 'conversations',
      type: ConversationStateView,
      columnEl: '#conversations'
    }],

    connectionType: DirectionalConnectionView,
    connectionCollectionType: RoutingEntryCollection,
    connectionSchema: [{attr: 'routing_entries'}],

    initialize: function(options) {
      DiagramView.prototype.initialize.call(this, options);
      this.channels = new ChannelColumnView({diagram: this});
      this.routingBlocks = new RoutingBlockColumnView({diagram: this});
      this.conversations = new ConversationColumnView({diagram: this});

      // Give the jsPlumb connectors arrow overlays
      jsPlumb.Defaults.ConnectionOverlays = [connectorOverlays.headArrow];

      this.connections.on('error:unsupported', this.onUnsupportedConnection);
    },

    onUnsupportedConnection: function(source, target, plumbConnection) {
      // TODO handle better in future (Response in UI or something?)
      jsPlumb.detach(plumbConnection, {fireEvent: false});
    },

    render: function() {
      this.channels.render();
      this.routingBlocks.render();
      this.conversations.render();
      this.connections.render();
      return this;
    }
  });

  _(exports).extend({
    RoutingDiagramView: RoutingDiagramView,

    RoutingColumnView: RoutingColumnView,
    ChannelColumnView: ChannelColumnView,
    RoutingBlockColumnView: RoutingBlockColumnView,
    ConversationColumnView: ConversationColumnView,

    RoutingStateView: RoutingStateView,
    RoutingStateCollection: RoutingStateCollection,
    ChannelStateView: ChannelStateView,
    RoutingBlockStateView: RoutingBlockStateView,
    ConversationStateView: ConversationStateView,

    RoutingEndpointView: RoutingEndpointView,
    RoutingEntryCollection: RoutingEntryCollection
  });
})(go.campaign.routing);
