// go.campaign.routing (views)
// ===========================
// Views for campaign routing diagram.

(function(exports) {
  var plumbing = go.components.plumbing,
      StateView = plumbing.StateView,
      DiagramView = plumbing.DiagramView,
      ParametricEndpointView = plumbing.ParametricEndpointView,
      DirectionalConnectionView = plumbing.DirectionalConnectionView,
      StateViewCollection = plumbing.StateViewCollection,
      AligningEndpointCollection = plumbing.AligningEndpointCollection,
      ConnectionViewCollection = plumbing.ConnectionViewCollection,
      connectorOverlays = plumbing.connectorOverlays;

  // Endpoints
  // ---------

  var RoutingEndpointView = ParametricEndpointView.extend({
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
      this.$column = this.diagram.$(options.columnEl);
      this.$description = $('<span></span>').attr('class', 'description');
    },

    render: function() {
      this.$column.append(this.$el);

      this.$el
        .css('position', 'relative')
        .append(this.$description);

      this.$description.text(this.model.get('description'));
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
    opts: function() {
      var opts = StateViewCollection.prototype.opts.call(this);
      return _(opts).extend({columnEl: this.columnEl});
    },

    initialize: function(options) {
      this.columnEl = options.columnEl;
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
