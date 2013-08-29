describe("go.routing (views)", function() {
  var routing = go.routing;

  var setUp = routing.testHelpers.setUp,
      tearDown = routing.testHelpers.tearDown,
      modelData = routing.testHelpers.modelData,
      newRoutingDiagram = routing.testHelpers.newRoutingDiagram;

  var plumbing = go.components.plumbing,
      noConnections = plumbing.testHelpers.noConnections;

  var testHelpers = go.testHelpers,
      noElExists = testHelpers.noElExists,
      oneElExists = testHelpers.oneElExists,
      response = testHelpers.rpc.response,
      errorResponse = testHelpers.rpc.errorResponse,
      assertRequest = testHelpers.rpc.assertRequest;

  var diagram;

  beforeEach(function() {
    setUp();
    diagram = newRoutingDiagram();
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
      state = diagram.states.get('channel1');

      var model = new RoutingEndpointModel({
        uuid: 'endpoint80',
        name: 'default'
      });

      endpoint = state.endpoints.add(
        'endpoints',
        {model: model},
        {render: false, silent: true});
    });

    describe(".render", function() {
      it("should display the endpoint name", function() {
        assert(noElExists(state.$('[data-uuid="endpoint80"]')));
        endpoint.render();

        assert(oneElExists(state.$('[data-uuid="endpoint80"]')));
        assert.equal(state.$('[data-uuid="endpoint80"]').text(), 'default');
      });
    });
  });

  describe(".RoutingEntryCollection", function() {
    var RoutingEntryCollection = routing.RoutingEntryCollection;

    var collection;

    beforeEach(function() {
      collection = new RoutingEntryCollection({
        view: diagram,
        attr: 'routing_entries'
      });
    });

    describe(".accepts", function() {
      it("should determine if a source and target match the accepted pairs",
      function() {
        var e1 = diagram.endpoints.get('endpoint1'),
            e4 = diagram.endpoints.get('endpoint4'),
            e5 = diagram.endpoints.get('endpoint5'),
            e6 = diagram.endpoints.get('endpoint6'),
            e8 = diagram.endpoints.get('endpoint8');

        assert(collection.accepts(e1, e4));
        assert(collection.accepts(e4, e1));

        assert(collection.accepts(e5, e8));
        assert(collection.accepts(e8, e5));

        assert(collection.accepts(e1, e8));
        assert(collection.accepts(e8, e1));

        assert.isFalse(collection.accepts(e1, e5));
        assert.isFalse(collection.accepts(e5, e1));

        assert.isFalse(collection.accepts(e4, e5));
        assert.isFalse(collection.accepts(e5, e4));

        assert.isFalse(collection.accepts(e4, e6));
        assert.isFalse(collection.accepts(e6, e4));
      });
    });
  });

  describe(".RoutingStateView", function() {
    var ChannelModel = routing.ChannelModel,
        RoutingStateView = routing.RoutingStateView;

    var state,
        $column;

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

      state = diagram.states.add('channels', new RoutingStateView({
        model: model,
        diagram: diagram,
        collection: diagram.states.members.get('channels')
      }), {render: false, silent: true});
    });

    describe(".render", function() {
      beforeEach(function() {
        $column = $('#routing-diagram #channels');
      });

      it("should append the state to its column", function() {
        assert(noElExists($column.find('[data-uuid="channel4"]')));
        state.render();
        assert(oneElExists($column.find('[data-uuid="channel4"]')));
      });

      it("should render its endpoints", function() {
        assert(noElExists($column.find('[data-uuid="channel4"] .endpoint')));
        state.render();
        assert(oneElExists('[data-uuid="channel4"] [data-uuid="endpoint80"]'));
        assert(oneElExists('[data-uuid="channel4"] [data-uuid="endpoint81"]'));
      });

      it("should display the state's name", function() {
        assert(noElExists('[data-uuid="channel4"] .name'));
        state.render();

        assert(oneElExists('[data-uuid="channel4"] .name'));
        assert.equal(
          $('[data-uuid="channel4"] .name').text(),
          '*181#');
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
      column = new ToyRoutingColumnView({diagram: diagram});
    });

    describe(".render", function() {
      it("should render the states it contains", function() {
        assert(noElExists(column.$('.state')));
        column.render();

        assert(oneElExists(column.$('[data-uuid="channel1"]')));
        assert(oneElExists(column.$('[data-uuid="channel2"]')));
        assert(oneElExists(column.$('[data-uuid="channel3"]')));
      });
    });
  });

  describe(".RoutingDiagramView", function() {
    describe("on 'error:unsupported' connection events", function() {
      beforeEach(function() {
        diagram.render();
      });

      it("should detach the jsPlumb connection", function(done) {
        var e4 = diagram.endpoints.get('endpoint4'),
            e6 = diagram.endpoints.get('endpoint6');

        diagram.connections.on('error:unsupported', function() {
          assert(noConnections(e4, e6));
          done();
        });

        jsPlumb.connect({source: e4.$el, target: e6.$el});
      });
    });

    describe(".render", function() {
      it("should render the states in its channels column", function() {
        var $channels = $('#routing-diagram #channels');

        assert(noElExists($channels.find('.state')));
        diagram.render();

        assert(oneElExists($channels.find('[data-uuid="channel1"]')));
        assert(oneElExists($channels.find('[data-uuid="channel2"]')));
        assert(oneElExists($channels.find('[data-uuid="channel3"]')));
      });

      it("should render the states in its routers column", function() {
        var $blocks = $('#routing-diagram #routers');

        assert(noElExists($blocks.find('.state')));
        diagram.render();

        assert(oneElExists($blocks.find('[data-uuid="router1"]')));
        assert(oneElExists($blocks.find('[data-uuid="router2"]')));
      });

      it("should render the states in its conversations column", function() {
        var $conversations = $('#routing-diagram #conversations');

        assert(noElExists($conversations.find('.state')));
        diagram.render();

        assert(oneElExists($conversations.find('[data-uuid="conversation1"]')));
        assert(oneElExists($conversations.find('[data-uuid="conversation2"]')));
      });

      it("should render the connections between states across columns",
      function() {
        var e1_e4 = diagram.connections.get('endpoint1-endpoint4');

        assert(_.isEmpty(jsPlumb.getConnections()));
        diagram.render();

        assert.deepEqual(
          jsPlumb.getConnections(),
          [e1_e4.plumbConnection]
        );
      });
    });
  });

  describe(".RoutingActionsView", function() {
    var RoutingActionsView = routing.RoutingActionsView;

    var actions,
        server;

    beforeEach(function() {
      server = sinon.fakeServer.create();

      var $el = $('<div>')
        .append($('<button>').attr('data-action', 'save'))
        .append($('<button>').attr('data-action', 'reset'));

      actions = new RoutingActionsView({
        el: $el,
        diagram: diagram,
        sessionId: '123'
      });

      actions.save.notifier.animate = false;
      actions.reset.notifier.animate = false;

      diagram.render();
    });

    afterEach(function() {
      actions.remove();
      server.restore();
    });

    describe("when the save button is clicked", function() {
      it("should issue a save api call with the routing table changes",
      function(done) {
        server.respondWith(function(req) {
          assertRequest(
            req,
            '/api/v1/go/api',
            'update_routing_table',
            ['campaign1', diagram.model.toJSON()]);

          done();
        });

        // modify the diagram
        diagram.connections.remove('endpoint1-endpoint4');
        assert.notDeepEqual(diagram.model.toJSON(), modelData);

        actions.$('[data-action=save]').click();
        server.respond();
      });

      it("should notify the user if the save was successful", function() {
        server.respondWith(response());

        actions.$('[data-action=save]').click();
        server.respond();

        assert.include(actions.save.notifier.$el.text(), "Save successful!");
      });

      it("should notify the user if an error occured", function() {
        server.respondWith(errorResponse('Aaah!'));

        actions.$('[data-action=save]').click();
        server.respond();

        assert.include(actions.save.notifier.$el.text(), "Save failed :/");
      });
    });

    describe("when the reset button is clicked", function() {
      it("should reset the routing table changes", function(done) {
        assert.deepEqual(diagram.model.toJSON(), modelData);

        // modify the diagram
        diagram.connections.remove('endpoint1-endpoint4');
        assert.notDeepEqual(diagram.model.toJSON(), modelData);

        actions.$('[data-action=reset]').click();
        actions.reset.once('success', function() {
          assert.deepEqual(diagram.model.toJSON(), modelData);
          done();
        });
      });

      it("should notify the user", function() {
        actions.$('[data-action=reset]').click();
        actions.reset.once('success', function() {
          assert.include(actions.reset.notifier.$el.text(), "Reset successful!");
        });
      });
    });
  });
});
