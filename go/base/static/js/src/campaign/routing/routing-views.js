// go.campaign.routing (views)
// ===========================
// Views for campaign routing screen.

(function(exports) {
  var plumbing = go.components.plumbing,
      StateView = plumbing.StateView,
      DiagramView = plumbing.DiagramView,
      StaticEndpoint = plumbing.StaticEndpoint,
      StateViewCollection = plumbing.StateViewCollection,
      AligningEndpointCollection = plumbing.AligningEndpointCollection;

  var routing = go.campaign.routing,
      ChannelModel = routing.ChannelModel,
      RoutingBlockModel = routing.RoutingBlockModel,
      ApplicationModel = routing.ApplicationModel,
      CampaignRoutingModel = routing.CampaignRoutingModel;

  // States
  // ------

  var RoutingState = StateView.extend({
    endpointType: StaticEndpoint,
    endpointCollectionType: AligningEndpointCollection,

    initialize: function(options) {
      StateView.prototype.initialize.call(this, options);
      this.$column = options.$column;
    },

    render: function(top, left) {
      jsPlumb.draggable(this.$el);

      this.$el
        .css('top', top)
        .css('left', left);

      this.$column.append(this.$el);
      this.endpoints.render();
      return this;
    }
  });

  var RoutingStateCollection = StateViewCollection.extend({
    opts: function() {
      var opts = StateViewCollection.prototype.opts.call(this);
      return _(opts).extend({$column: this.$column});
    },

    initialize: function(options) {
      this.$column = this.diagram.$(options.columnEl);
    }
  });

  var ChannelState = StateView.extend({
    className: 'channel',
    endpointSchema: [{attr: 'endpoints', side: 'right'}]
  });

  var RoutingBlockState = StateView.extend({
    className: 'routing-block',
    endpointSchema: [
      {attr: 'channel_endpoints', side: 'left'},
      {attr: 'application_endpoints', side: 'right'}
    ]
  });

  var ApplicationState = StateView.extend({
    className: 'application',
    endpointSchema: [{attr: 'endpoints', side: 'left'}]
  });

  // Columns
  // -------

  // A vertical section of the routing screen dedicated to a particular
  // collection of the three state types (Channel, RoutingBlock or
  // Application).
  var RoutingScreenColumn = Backbone.View.extend({
    intialize: function(options) {
      this.diagram = options.diagram;
      this.states = this.diagram.states.members.get(this.collectionName);
      this.ensureElement(this.diagram.$('#' + this.id));
    },

    render: function() {
      var top = 0,
          left = 0;

      this.states.each(function(state) {
        state.render(top, left);
      });

      // TODO render placeholder view
    }
  });

  var ChannelColumn = RoutingScreenColumn.extend({
    id: 'channels',
    collectionName: 'channels'
  });

  var RoutingBlockColumn = RoutingScreenColumn.extend({
    id: 'routing-blocks',
    collectionName: 'routing_blocks'
  });

  var ApplicationColumn = RoutingScreenColumn.extend({
    id: 'applications',
    collectionName: 'applications'
  });

  // Main components
  // ---------------

  var RoutingScreen = DiagramView.extend({
    stateType: RoutingState,
    stateCollectionType: RoutingStateCollection,

    stateSchema: [{
      attr: 'channels',
      type: ChannelState,
      columnEl: '#channels'
    }, {
      attr: 'routing_blocks',
      type: RoutingBlockState,
      columnEl: '#routing-blocks'
    }, {
      attr: 'applications',
      type: ApplicationState,
      columnEl: '#applications'
    }],

    initialize: function(options) {
      DiagramView.prototype.initialize.call(this, options);
      this.channels = new ChannelColumn({diagram: this});
      this.routingBlocks = new RoutingBlockColumn({diagram: this});
      this.applications = new ApplicationColumn({diagram: this});
    },

    render: function() {
      this.channels.render();
      this.routingBlocks.render();
      this.applications.render();
      this.connections.render();
      return this;
    }
  });

  _(exports).extend({
    RoutingScreen: RoutingScreen,

    RoutingState: RoutingState,
    RoutingStateCollection: RoutingStateCollection,
    ChannelState: ChannelState,
    RoutingBlockState: RoutingBlockState,
    ApplicationState: ApplicationState,

    RoutingScreenColumn: RoutingScreenColumn,
    ChannelColumn: ChannelColumn,
    RoutingBlockColumn: RoutingBlockColumn,
    ApplicationColumn: ApplicationColumn
  });
})(go.campaign.routing);
