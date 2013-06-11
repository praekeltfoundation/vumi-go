// go.campaign.routing (views)
// ===========================
// Views for campaign routing screen.

(function(exports) {
  var plumbing = go.components.plumbing,
      StateView = plumbing.StateView,
      DiagramView = plumbing.DiagramView,
      ParametricEndpointView = plumbing.ParametricEndpointView,
      DirectionalConnectionView = plumbing.DirectionalConnectionView,
      StateViewCollection = plumbing.StateViewCollection,
      AligningEndpointCollection = plumbing.AligningEndpointCollection,
      connectorOverlays = plumbing.connectorOverlays;

  // Endpoints
  // ---------

  var RoutingEndpointView = ParametricEndpointView.extend({
    labelled: true,
    labelText: function() { return this.model.get('name'); },
    labelOptions: function() {
      return {
        my: 'bottom',
        at: 'top',
        text: this.labelText.bind(this)
      };
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
    },

    descriptionTemplate: _.template(
      "<span class='description'><%= description %><span>"),

    render: function() {
      this.$el
        .css('position', 'relative')
        .append(this.descriptionTemplate({
          description: this.model.get('description')
        }));

      this.$column.append(this.$el);
      this.endpoints.render();
      return this;
    }
  });

  var ChannelStateView = RoutingStateView.extend({
    className: 'state channel',
    endpointSchema: [{attr: 'endpoints', side: 'right'}]
  });

  var RoutingBlockStateView = RoutingStateView.extend({
    className: 'state routing-block',
    endpointSchema: [
      {attr: 'channel_endpoints', side: 'left'},
      {attr: 'conversation_endpoints', side: 'right'}
    ]
  });

  var ConversationStateView = RoutingStateView.extend({
    className: 'state conversation',
    endpointSchema: [{attr: 'endpoints', side: 'left'}]
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

  // A vertical section of the routing screen dedicated to a particular
  // collection of the three state types (Channel, RoutingBlock or
  // Conversation).
  var RoutingColumnView = Backbone.View.extend({
    initialize: function(options) {
      this.screen = options.screen;
      this.states = this.screen.states.members.get(this.collectionName);
      this.setElement(this.screen.$('#' + this.id));
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

  var RoutingScreenView = DiagramView.extend({
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
    connectionSchema: [{attr: 'routing_entries'}],

    initialize: function(options) {
      DiagramView.prototype.initialize.call(this, options);
      this.channels = new ChannelColumnView({screen: this});
      this.routingBlocks = new RoutingBlockColumnView({screen: this});
      this.conversations = new ConversationColumnView({screen: this});

      this._initPlumb();
    },

    _initPlumb: function() {
      var defaults = jsPlumb.Defaults;
      defaults.Connector = ['StateMachine'];
      defaults.ConnectionOverlays = [connectorOverlays.headArrow];
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
    RoutingScreenView: RoutingScreenView,

    RoutingColumnView: RoutingColumnView,
    ChannelColumnView: ChannelColumnView,
    RoutingBlockColumnView: RoutingBlockColumnView,
    ConversationColumnView: ConversationColumnView,

    RoutingStateView: RoutingStateView,
    RoutingStateCollection: RoutingStateCollection,
    ChannelStateView: ChannelStateView,
    RoutingBlockStateView: RoutingBlockStateView,
    ConversationStateView: ConversationStateView,

    RoutingEndpointView: RoutingEndpointView
  });
})(go.campaign.routing);
