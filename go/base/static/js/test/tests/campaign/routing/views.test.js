describe("go.campaign.routing (views)", function() {
  var routing = go.campaign.routing;

  var setUp = routing.testHelpers.setUp,
      tearDown = routing.testHelpers.tearDown,
      newRoutingScreen = routing.testHelpers.newRoutingScreen;

  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists,
      oneElExists = testHelpers.oneElExists;

  var screen;

  beforeEach(function() {
    setUp();
    screen = newRoutingScreen();
  });

  afterEach(function() {
    tearDown();
  });

  describe(".RoutingEndpointView", function() {
    var RoutingEndpointModel = routing.RoutingEndpointModel,
        RoutingEndpointView = routing.RoutingEndpointView;

    var state,
        endpoint;

    beforeEach(function() {
      state = screen.states.get('channel1');

      var model = new RoutingEndpointModel({
        uuid: 'endpoint80',
        name: 'default'
      });

      endpoint = new RoutingEndpointView({
        model: model,
        state: state,
        collection: state.endpoints.members.get('endpoints')
      });
    });

    describe(".render", function() {
      beforeEach(function() {
        state.render();
      });

      it("should display a label with the endpoint name", function() {
        var labelEl = '#routing-screen #channels #channel1 #endpoint80 .label';

        assert(noElExists(labelEl));
        endpoint.render();

        assert(oneElExists(labelEl));
        assert.equal($(labelEl).text(), 'default');
      });
    });
  });

  describe(".RoutingStateView", function() {
    var ChannelModel = routing.ChannelModel,
        RoutingStateView = routing.RoutingStateView;

    var state;

    beforeEach(function() {
      var model = new ChannelModel({
        uuid: 'channel4',
        tag: ['invisible_sms', '*181#'],
        name: '*181#',
        description: 'Invisible Sms: *181#',
        endpoints: [
          {uuid: 'endpoint80', name: 'default'},
          {uuid: 'endpoint81', name: 'secondary'}]
      });

      state = new RoutingStateView({
        model: model,
        diagram: screen,
        columnEl: '#channels',
        collection: screen.states.members.get('channels')
      });
    });

    describe(".render", function() {
      beforeEach(function() {
        screen.render();
      });

      it("should append the state to its column", function() {
        var stateEl = '#routing-screen #channels #channel4';

        assert(noElExists(stateEl));
        state.render();
        assert(oneElExists(stateEl));
      });

      it("should render its endpoints", function() {
        assert(noElExists('#routing-screen #channels #channel4 .endpoint'));
        state.render();
        assert(oneElExists('#routing-screen #channels #channel4 #endpoint80'));
        assert(oneElExists('#routing-screen #channels #channel4 #endpoint81'));
      });

      it("should display the state's description", function() {
        var descriptionEl = '#routing-screen #channels #channel4 .description';

        assert(noElExists(descriptionEl));
        state.render();

        assert(oneElExists(descriptionEl));
        assert.equal($(descriptionEl).text(), 'Invisible Sms: *181#');
      });
    });
  });

  describe(".RoutingColumnView", function() {
    var RoutingColumnView = routing.RoutingColumnView;

    var ToyRoutingColumnView = RoutingColumnView.extend({
      // choose one of the state collections to test with
      id: 'channels',
      collectionName: 'channels'
    });

    var column;

    beforeEach(function() {
      column = new ToyRoutingColumnView({screen: screen});
    });

    describe(".render", function() {
      it("should render the states it contains", function() {
        assert(noElExists('#routing-screen #channels .state'));
        column.render();

        assert(oneElExists('#routing-screen #channels #channel1'));
        assert(oneElExists('#routing-screen #channels #channel2'));
        assert(oneElExists('#routing-screen #channels #channel3'));
      });
    });
  });

  describe(".RoutingScreenView", function() {
    describe(".render", function() {
      it("should render the states in its channels column", function() {
        assert(noElExists('#routing-screen #channels .state'));
        screen.render();

        assert(oneElExists('#routing-screen #channels #channel1'));
        assert(oneElExists('#routing-screen #channels #channel2'));
        assert(oneElExists('#routing-screen #channels #channel3'));
      });

      it("should render the states in its routing blocks column", function() {
        assert(noElExists('#routing-screen #routing-blocks .state'));
        screen.render();

        assert(oneElExists('#routing-screen #routing-blocks #routing-block1'));
        assert(oneElExists('#routing-screen #routing-blocks #routing-block2'));
      });

      it("should render the states in its conversations column", function() {
        assert(noElExists('#routing-screen #conversations .state'));
        screen.render();

        assert(oneElExists('#routing-screen #conversations #conversation1'));
        assert(oneElExists('#routing-screen #conversations #conversation2'));
      });

      it("should render the connections between states across columns",
      function() {
        var e1_e4 = screen.connections.get('endpoint1-endpoint4');

        assert(_.isEmpty(jsPlumb.getConnections()));
        screen.render();

        assert.deepEqual(
          jsPlumb.getConnections(),
          [e1_e4.plumbConnection]
        );
      });
    });
  });
});
