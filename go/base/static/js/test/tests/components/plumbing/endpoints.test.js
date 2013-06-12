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
        assert(oneElExists('#x #x1'));
        x1.destroy();
        assert(noElExists('#x #x1'));
      });
    });

    describe(".render", function() {
      var x4;

      beforeEach(function() {
        x4 = new ToyEndpointView({
          state: x,
          collection: x.endpoints.members.get('endpoints'),
          model: new EndpointModel({id: 'x4'})
        });
      });

      it("should append the endpoint to the state element", function() {
        assert(noElExists('#x #x4'));
        x4.render();
        assert(oneElExists('#x #x4'));
      });

      it("should add a label to the endpoint if labelling is enabled",
      function() {
        x4.render();
        assert(oneElExists('#x #x4 .label'));
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

      state
        .render()
        .$el
        .width(200)
        .height(300)
        .css('padding', 10);

      endpoint = new ParametricEndpointView({
        state: state,
        collection: state.endpoints.members.get('endpoints'),
        model: new EndpointModel({id: 'x4'})
      });

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

  describe(".AligningEndpointCollection", function() {
    var EndpointModel = stateMachine.EndpointModel,
        ParametricEndpointView = plumbing.ParametricEndpointView;

    var AligningEndpointCollection
      = plumbing.AligningEndpointCollection;

    var MockAligningEndpointCollection = AligningEndpointCollection.extend({
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
        endpoints.add({id: 'x4'}, {addModel: true});
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

        endpoints.add({id: 'x4'}, {addModel: true});
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
