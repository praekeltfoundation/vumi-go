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

  describe(".RoutingEndpointView", function() {
    var RoutingEndpointModel = routing.models.RoutingEndpointModel;

    var diagram,
        state,
        endpoint;

    beforeEach(function() {
      setUp();
      diagram = newRoutingDiagram();

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

    afterEach(function() {
      tearDown();
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
    var RoutingEntryCollection = routing.views.RoutingEntryCollection;

    var diagram,
        collection;

    beforeEach(function() {
      setUp();
      diagram = newRoutingDiagram();

      collection = new RoutingEntryCollection({
        view: diagram,
        attr: 'routing_entries'
      });
    });

    afterEach(function() {
      tearDown();
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
    var RouterStateView = routing.views.RouterStateView,
        RouterModel = routing.models.RouterModel;

    var diagram,
        state,
        $column;

    beforeEach(function() {
      setUp();
      diagram = newRoutingDiagram();

      var model = new RouterModel({
        uuid: 'router3',
        type: 'keyword',
        name: 'keyword-router',
        description: 'Keyword',
        channel_endpoints: [{uuid: 'endpoint12', name: 'default'}],
        conversation_endpoints: [
          {uuid: 'endpoint13', name: 'default'},
          {uuid: 'endpoint14', name: 'default'},
          {uuid: 'endpoint15', name: 'default'},
          {uuid: 'endpoint16', name: 'default'}
        ]
      });

      state = diagram.states.add('routers', new RouterStateView({
        model: model,
        diagram: diagram,
        collection: diagram.states.members.get('routers')
      }), {render: false, silent: true});

    });

    afterEach(function() {
      tearDown();
    });

    describe(".endpointsForSide", function() {
      it("should return the endpoints for a side", function() {
        assert.deepEqual(
          state.endpointsForSide('left'),
          [state.endpoints.get('endpoint12')]
        );
        assert.deepEqual(state.endpointsForSide('right'), [
          state.endpoints.get('endpoint13'),
          state.endpoints.get('endpoint14'),
          state.endpoints.get('endpoint15'),
          state.endpoints.get('endpoint16')
        ]);
      });
    });

    describe(".findMaxEndpoints", function() {
      it("should return the max of two endpoint arrays", function() {
        assert.equal(state.findMaxEndpoints(), 4);
      });
    });

    describe(".tooManyEndpoints", function() {
      it("should check if there are too many endpoints", function() {
        assert(state.tooManyEndpoints());
      });
    });

    describe(".stretchedHeight", function() {
      it("should calculate the new height", function() {
        state.heightPerEndpoint = 15;
        assert.equal(state.stretchedHeight(), 4 * 15);
      });
    });

    describe(".render", function() {
      beforeEach(function() {
        $column = $('#diagram #routers');
      });

      it("should append the state to its column", function() {
        assert(noElExists($column.find('[data-uuid="router3"]')));
        state.render();
        assert(oneElExists($column.find('[data-uuid="router3"]')));
      });

      it("should not set a new height for few endpoints", function(){
        state.maxEndpoints = 5;
        state.$el.height(10);
        state.render();
        assert.equal(state.$el.height(), 10);
      });

      it("should set a new heightfor many endpoints", function(){
        state.maxEndpoints = 3;
        state.heightPerEndpoint = 15;
        state.model.get('conversation_endpoints');
        state.$el.height(10);
        state.render();
        assert.equal(state.$el.height(), 4 * 15);
      });

      it("should render its endpoints", function() {
        assert(noElExists($column.find('[data-uuid="router3"] .endpoint')));
        state.render();
        assert(oneElExists('[data-uuid="router3"] [data-uuid="endpoint12"]'));
        assert(oneElExists('[data-uuid="router3"] [data-uuid="endpoint13"]'));
        assert(oneElExists('[data-uuid="router3"] [data-uuid="endpoint14"]'));
        assert(oneElExists('[data-uuid="router3"] [data-uuid="endpoint15"]'));
        assert(oneElExists('[data-uuid="router3"] [data-uuid="endpoint16"]'));
      });

      it("should display the state's name as a link", function() {
        assert(noElExists('[data-uuid="router3"] a.name'));
        state.render();

        assert(oneElExists('[data-uuid="router3"] a.name'));
        assert.equal(
          $('[data-uuid="router3"] a.name').text(),
          'keyword-router');
      });

      it("should not set state-not-running if their is no status", function() {
        assert(!state.$el.hasClass('state-not-running'));
        assert(noElExists('[data-uuid="router3"] span.label-danger'));
        state.render();
        assert(!state.$el.hasClass('state-not-running'));
        assert(noElExists('[data-uuid="router3"] span.label-danger'));
      });

      it("should not set state-not-running if it is running", function() {
        state.model.set('status', 'running');
        assert(!state.$el.hasClass('state-not-running'));
        assert(noElExists('[data-uuid="router3"] span.label-danger'));
        state.render();
        assert(!state.$el.hasClass('state-not-running'));
        assert(noElExists('[data-uuid="router3"] span.label-danger'));
      });

      it("should set state-not-running if it is not running", function() {
        state.model.set('status', 'stopping');
        assert(!state.$el.hasClass('state-not-running'));
        assert(noElExists('[data-uuid="router3"] span.label-danger'));
        state.render();
        assert(state.$el.hasClass('state-not-running'));
        assert(oneElExists('[data-uuid="router3"] span.label-danger'));
        assert.equal(
          $('[data-uuid="router3"] span.label-danger').text(),
          'not running');
      });
    });
  });

  describe(".RoutingColumnView", function() {
    var RoutingColumnView = routing.views.RoutingColumnView;

    var diagram,
        column;

    var ToyRoutingColumnView = RoutingColumnView.extend({
      // choose one of the state collections to test with
      id: 'channels',
      collectionName: 'channels'
    });

    function $endpointAt(i) {
      return column.states
        .at(i).endpoints
        .at(0).$el;
    }

    beforeEach(function() {
      setUp();
      diagram = newRoutingDiagram();
      column = new ToyRoutingColumnView({diagram: diagram});
    });

    afterEach(function() {
      tearDown();
    });

    describe("when a state is dragged", function() {
      it("should repaint", function() {
        var repainted = false;
        column.on('repaint', function() { repainted = true; });

        assert(!repainted);

        // jquery-simulate doesn't seem to be working with jquery ui here,
        // so we are invoking the callback directly
        column.onDrag();

        assert(repainted);
      });
    });

    describe("when a state is dropped", function() {
      it("should update the ordinals", function() {
        var updated = false;
        column.on('update:ordinals', function() { updated = true; });

        assert(!updated);

        // jquery-simulate doesn't seem to be working with jquery ui here,
        // so we are invoking the callback directly
        column.onStop();

        assert(updated);
      });
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

    describe(".repaint", function() {
      it("should repaint all endpoints in the column", function() {
        diagram.model.set('channels', diagram.model.get('channels').first(3));

        var repaint = sinon.spy(plumbing.utils, 'repaintSortable');
        column.repaint();

        assert(repaint.calledWith($endpointAt(0)));
        assert(repaint.calledWith($endpointAt(1)));
        assert(repaint.calledWith($endpointAt(2)));

        repaint.restore();
      });

      it("should trigger a 'repaint' event", function(done) {
        column
          .on('repaint', function() { done(); })
          .repaint();
      });
    });

    describe(".updateOrdinals", function() {
      it("should update the models' ordinals using the DOM ordering", function() {
        var models = column.states.models;

        models.reset([
          models.get('channel1'),
          models.get('channel2'),
          models.get('channel3')]);

        column.render();

        column.$('[data-uuid="channel1"]')
          .detach()
          .insertAfter(column.$('[data-uuid="channel3"]'));

        models.get('channel1').set('ordinal', 1);
        models.get('channel2').set('ordinal', 0);
        models.get('channel3').set('ordinal', 2);

        column.updateOrdinals();

        assert.strictEqual(models.get('channel1').get('ordinal'), 2);
        assert.strictEqual(models.get('channel2').get('ordinal'), 0);
        assert.strictEqual(models.get('channel3').get('ordinal'), 1);
      });

      it("should trigger an 'update:ordinals' event", function() {
        var triggered = false;
        column.on('update:ordinals', function() { triggered = true; });

        assert(!triggered);
        column.updateOrdinals();
        assert(triggered);
      });
    });
  });

  describe(".RoutingDiagramView", function() {
    var diagram;

    beforeEach(function() {
      setUp();
      diagram = newRoutingDiagram();
    });

    afterEach(function() {
      tearDown();
    });

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
        var $channels = $('#diagram #channels');

        assert(noElExists($channels.find('.state')));
        diagram.render();

        assert(oneElExists($channels.find('[data-uuid="channel1"]')));
        assert(oneElExists($channels.find('[data-uuid="channel2"]')));
        assert(oneElExists($channels.find('[data-uuid="channel3"]')));
      });

      it("should render the states in its routers column", function() {
        var $blocks = $('#diagram #routers');

        assert(noElExists($blocks.find('.state')));
        diagram.render();

        assert(oneElExists($blocks.find('[data-uuid="router1"]')));
        assert(oneElExists($blocks.find('[data-uuid="router2"]')));
      });

      it("should render the states in its conversations column", function() {
        var $conversations = $('#diagram #conversations');

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

  describe(".RoutingView", function() {
    var RoutingView = routing.views.RoutingView,
        RoutingModel = routing.models.RoutingModel;

    var view,
        server;

    beforeEach(function() {
      setUp();
      server = sinon.fakeServer.create();

      view = new RoutingView({
        el: '#routing',
        model: new RoutingModel(modelData()),
        sessionId: '123'
      });

      view.save.notifier.animate = false;
      view.reset.notifier.animate = false;

      view.diagram.render();
    });

    afterEach(function() {
      view.remove();
      server.restore();
      tearDown();
    });

    describe("when the save button is clicked", function() {
      it("should issue a save api call with the routing table changes",
      function(done) {
        server.respondWith(function(req) {
          assertRequest(
            req,
            '/api/v1/go/api',
            'update_routing_table',
            ['campaign1', view.model.toJSON()]);

          done();
        });

        // modify the diagram
        view.diagram.connections.remove('endpoint1-endpoint4');
        assert.notDeepEqual(view.model.toJSON(), modelData());

        view.$('#save').click();
        server.respond();
      });

      it("should persist the ordering of the routing table components", function() {
        server.respondWith(response());

        var triggered = false;
        view.diagram.model.on('persist:ordinals', function() { triggered = true; });

        view.$('#save').click();

        assert(!triggered);
        server.respond();
        assert(triggered);
      });

      it("should notify the user if the save was successful", function() {
        server.respondWith(response());

        view.$('#save').click();
        server.respond();

        assert.include(view.save.notifier.$el.text(), "Save successful.");
      });

      it("should notify the user if an error occured", function() {
        server.respondWith(errorResponse('Aaah!'));

        view.$('#save').click();
        server.respond();

        assert.include(view.save.notifier.$el.text(), "Save failed.");
      });
    });

    describe("when the reset button is clicked", function() {
      it("should reset the routing table changes", function(done) {
        view.model.clear().set(modelData());
        var expected = view.model.toJSON();

        // modify the diagram
        view.diagram.connections.remove('endpoint1-endpoint4');
        assert.notDeepEqual(view.model.toJSON(), expected);

        view.$('#reset').click();
        view.reset.once('success', function() {
          assert.deepEqual(view.model.toJSON(), expected);
          done();
        });
      });

      it("should notify the user", function() {
        view.$('#reset').click();
        view.reset.once('success', function() {
          assert.include(view.reset.notifier.$el.text(), "Reset successful.");
        });
      });
    });
  });
});
