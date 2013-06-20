describe("go.components.plumbing (endpoints)", function() {
  var stateMachine = go.components.stateMachine;
      plumbing = go.components.plumbing,
      testHelpers = go.testHelpers;

  var oneElExists = testHelpers.oneElExists,
      noElExists = testHelpers.noElExists;

  var setUp = plumbing.testHelpers.setUp,
      newSimpleDiagram = plumbing.testHelpers.newSimpleDiagram,
      tearDown = plumbing.testHelpers.tearDown;

  var diagram;

  beforeEach(function() {
    setUp();
    diagram = newSimpleDiagram();
  });

  afterEach(function() {
    tearDown();
  });

  describe(".EndpointView", function() {
    var EndpointModel = stateMachine.EndpointModel,
        EndpointView = plumbing.EndpointView;

    var ToyEndpointView = EndpointView.extend({labelled: true});

    var x,
        x1;

    beforeEach(function() {
      x = diagram.states.get('x');
      x1 = diagram.endpoints.get('x1');
      diagram.render();
    });

    describe(".destroy", function() {
      it("should remove the element", function() {
        assert(oneElExists('[data-uuid="x1"]'));
        x1.destroy();
        assert(noElExists('[data-uuid="x1"]'));
      });
    });

    describe(".render", function() {
      var x4;

      beforeEach(function() {
        x4 = new ToyEndpointView({
          state: x,
          collection: x.endpoints.members.get('endpoints'),
          model: new EndpointModel({uuid: 'x4'})
        });
      });

      it("should append the endpoint to the state element", function() {
        assert(noElExists('[data-uuid="x4"]'));
        x4.render();
        assert(oneElExists('[data-uuid="x4"]'));
      });

      it("should add a label to the endpoint if labelling is enabled",
      function() {
        x4.render();
        assert(oneElExists('[data-uuid="x4"] .label'));
      });
    });
  });

  describe(".EndpointViewCollection", function() {
    var collectionX,
        collectionY;

    beforeEach(function() {
      collectionX = diagram.states
        .get('x')
        .endpoints
        .members
        .get('endpoints');

      collectionY = diagram.states
        .get('y')
        .endpoints
        .members
        .get('endpoints');
    });

    describe(".remove", function() {
      it("should remove the endpoint", function(done) {
        collectionX.on('remove', function() {
          assert(!collectionX.has('x1'));
          done();
        });

        collectionX.remove('x1');
      });

      it("should remove connections where the endpoint is the source",
      function(done) {
        diagram.connections.on('remove', function() {
          assert(!diagram.connections.has('x3-y2'));
          done();
        });

        collectionX.remove('x3');
      });

      it("should remove connections where the endpoint is the target",
      function(done) {
        diagram.connections.on('remove', function() {
          assert(!diagram.connections.has('x3-y2'));
          done();
        });

        collectionY.remove('y2');
      });
    });
  });

  describe(".PositionableEndpointView", function() {
    var PositionableEndpointView = plumbing.PositionableEndpointView;

    var ToyEndpointView = PositionableEndpointView.extend({
      reposition: function(p) { this.p = p; },
      position: function() { return this.p; }
    });

    var state,
        endpoint;

    beforeEach(function() {
      state = diagram.states.get('x');

      endpoint = new ToyEndpointView({
        state: state,
        collection: state.endpoints.members.get('endpoints'),
        model: new EndpointModel({uuid: 'x4'})
      });

      state
        .render()
        .$el
        .offset({top: 100, left: 200});
    });

    describe(".render", function() {
      it("should position the endpoint relative to the state", function() {
        endpoint.reposition({top: -25, left: -50});
        endpoint.render();

        assert.deepEqual(
          endpoint.$el.offset(),
          {top: 75, left: 150});

        endpoint.reposition({top: -30, left: -50});
        endpoint.render();

        assert.deepEqual(
          endpoint.$el.offset(),
          {top: 70, left: 150});
      });
    });
  });

  describe(".ParametricEndpointView", function() {
    var EndpointModel = stateMachine.EndpointModel,
        ParametricEndpointView = plumbing.ParametricEndpointView;

    var state,
        endpoint;

    beforeEach(function() {
      state = diagram.states.get('x');

      endpoint = new ParametricEndpointView({
        state: state,
        collection: state.endpoints.members.get('endpoints'),
        model: new EndpointModel({uuid: 'x4'})
      });

      state
        .render()
        .$el
        .width(200)
        .height(300)
        .css('padding', 10);

      endpoint
        .$el
        .width(20)
        .height(10);
    });

    describe(".positioners", function() {
      var positioners;

      beforeEach(function() {
        positioners = endpoint.positioners;
      });

      describe(".left", function() {
        it("should return the position on the left corresponding to param t",
        function() {
          assert.deepEqual(
            positioners.left.call(endpoint, 0.5),
            {left: -10, top: 155});
        });
      });

      describe(".right", function() {
        it("should find the position on the right corresponding to param t",
        function() {
          assert.deepEqual(
            positioners.right.call(endpoint, 0.5),
            {left: 210, top: 155});
        });
      });

      describe(".top", function() {
        it("should find the position on the top corresponding to param t",
        function() {
          assert.deepEqual(
            positioners.top.call(endpoint, 0.5),
            {left: 100, top: -5});
        });
      });

      describe(".bottom", function() {
        it("should find the position on the bottom corresponding to param t",
        function() {
          assert.deepEqual(
            positioners.bottom.call(endpoint, 0.5),
            {left: 100, top: 315});
        });
      });
    });

    describe(".render", function() {
      it("should position the endpoint",
      function() {
        endpoint
          .reposition(0.2)
          .render();

        assert.deepEqual(
          endpoint.$el.position(),
          {left: -10, top: 59});

        endpoint
          .reposition(0.1)
          .render();

        assert.deepEqual(
          endpoint.$el.position(),
          {left: -10, top: 27});
      });
    });
  });

  describe(".FollowingEndpointView", function() {
    var FollowingEndpointView = plumbing.FollowingEndpointView;

    var state,
        endpoint,
        $target;

    beforeEach(function() {
      $target = $('<span></span').attr('id', 'target');

      state = diagram.states.get('x');
      state.$el.append($target);

      endpoint = new FollowingEndpointView({
        state: state,
        target: '#target',
        collection: state.endpoints.members.get('endpoints'),
        model: new EndpointModel({uuid: 'x4'})
      });

      state
        .render()
        .$el
        .width(200)
        .height(300)
        .css('position', 'absolute');

      $target
        .width(20)
        .height(40)
        .css({position: 'absolute', top: 10, left: 20});

      endpoint
        .$el
        .width(20)
        .height(10);
    });

    describe(".positioners", function() {
      var positioners;

      beforeEach(function() {
        positioners = endpoint.positioners;
      });

      describe(".left", function() {
        it("should find the position on the left corresponding to the target",
        function() {
          assert.deepEqual(
            positioners.left.call(endpoint),
            {left: -10, top: 25});
        });
      });

      describe(".right", function() {
        it("should find the position on the right corresponding to the target ",
        function() {
          assert.deepEqual(
            positioners.right.call(endpoint),
            {left: 190, top: 25});
        });
      });
    });

    describe(".render", function() {
      it("should follow to its target", function() {
        endpoint.render();

        assert.deepEqual(
          endpoint.$el.position(),
          {top: 25, left: -10});

        $target.css({top: 20, left: 25});
        endpoint.render();

        assert.deepEqual(
          endpoint.$el.position(),
          {top: 35, left: -10});
      });
    });
  });

  describe(".AligningEndpointCollection", function() {
    var EndpointModel = stateMachine.EndpointModel,
        ParametricEndpointView = plumbing.ParametricEndpointView;

    var AligningEndpointCollection
      = plumbing.AligningEndpointCollection;

    var MockAligningEndpointCollection = AligningEndpointCollection.extend({
      margin: 0,
      render: function() {
        AligningEndpointCollection.prototype.render.call(this);
        this.rendered = true;
        return this;
      }
    });

    var MockParametricEndpointView = ParametricEndpointView.extend({
      reposition: function(t) {
        ParametricEndpointView.prototype.reposition.call(this, t);
        this.t = t;
        return this;
      },

      render: function() {
        ParametricEndpointView.prototype.render.call(this);
        this.rendered = true;
        return this;
      }
    });

    var endpoints;

    var assertAlignment = function() {
      var expected = Array.prototype.slice.call(arguments);
      endpoints.each(function(e, i) {
        assert.closeTo(e.t, expected[i], 0.0000001);
      });
    };

    beforeEach(function() {
      var x = diagram.states.get('x');
      x.render();

      endpoints = new MockAligningEndpointCollection({
        view: x,
        attr: 'endpoints',
        type: MockParametricEndpointView,
        margin: 0
      });
    });

    describe("on 'add' events", function() {
      it("should re-render its endpoints", function(done) {
        endpoints.on('add', function() {
          assert(endpoints.rendered);
          done();
        });

        assert(!endpoints.rendered);
        endpoints.add({model: {uuid: 'x4'}});
      });
    });

    describe("on 'remove' events", function() {
      it("should re-render its endpoints", function(done) {
        endpoints.on('remove', function() {
          assert(endpoints.rendered);
          done();
        });

        assert(!endpoints.rendered);
        endpoints.remove('x3');
      });
    });

    describe(".realign", function() {
      beforeEach(function() {
        // Ensure we only render manually
        endpoints.off('add');
        endpoints.off('remove');
      });

      it("should align endpoints to be equally spaced", function() {
        endpoints.realign();
        assertAlignment(1/4, 1/2, 3/4);

        endpoints.add({model: {uuid: 'x4'}});
        endpoints.realign();
        assertAlignment(1/5, 2/5, 3/5, 4/5);

        endpoints.remove('x4');
        endpoints.remove('x3');
        endpoints.remove('x2');
        endpoints.realign();
        assertAlignment(1/2);
      });
    });

    describe(".render", function() {
      beforeEach(function() {
        // Ensure we only render manually
        endpoints.off('remove');
      });

      it("should realign its endpoints", function() {
        endpoints.realign();
        endpoints.remove('x3');

        // check that we haven't realigned yet
        assertAlignment(1/4, 1/2, 3/4);

        endpoints.render();
        assertAlignment(1/3, 2/3);
      });
    });
  });
});
