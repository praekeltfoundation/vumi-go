// go.campaign.routing (views)
// ===========================
// Views for campaign routing screen.

(function(exports) {
  var plumbing = go.components.plumbing,
      StateView = plumbing.StateView,
      DiagramView = plumbing.DiagramView,
      StaticEndpoint = plumbing.StaticEndpoint,
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

    render: function() {
      jsPlumb.draggable(this.$el);
      // TODO append to column
      this.endpoints.render();
      return this;
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
  //
  // Arguments:
  //   - diagram: the diagram view that the column is part of
  var RoutingScreenColumn = Backbone.View.extend({
    intialize: function(diagram) {
      this.diagram = diagram;
      this.states = this.diagram.states.members.get(this.collectionName);
      this.ensureElement(this.diagram.$('#' + this.id));
    },

    render: function() {
      this.states.render();
      // TODO render placeholder view
    }
  });

  var ChannelColumn = RoutingScreenColumn.extend({
    id: 'channels',
    collectionName: 'channels'
  });

  var ApplicationColumn = RoutingScreenColumn.extend({
    id: 'applications',
    collectionName: 'applications'
  });

  var RoutingBlockColumn = RoutingScreenColumn.extend({
    id: 'routing-blocks',
    collectionName: 'routing_blocks'
  });

  // Main components
  // ---------------

  var RoutingScreen = DiagramView.extend({
    stateType: RoutingState,
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
  });
})(go.campaign.routing);
