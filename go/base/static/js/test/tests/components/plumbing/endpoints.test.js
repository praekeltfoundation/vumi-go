describe("go.components.plumbing (endpoints)", function() {
  var stateMachine = go.components.stateMachine;
      plumbing = go.components.plumbing;

  var testHelpers = plumbing.testHelpers,
      setUp = testHelpers.setUp,
      newSimpleDiagram = testHelpers.newSimpleDiagram,
      tearDown = testHelpers.tearDown;

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

    var x,
        x1;

    beforeEach(function() {
      x = diagram.states.get('x');
      x1 = diagram.endpoints.get('x1');
      diagram.render();
    });
    
    describe(".destroy", function() {
      it("should remove the actual jsPlumb endpoint", function() {
        assert.isDefined(jsPlumb.getEndpoint('x1'));
        x1.destroy();
        assert.isNull(jsPlumb.getEndpoint('x1'));
      });
    });

    describe(".render", function() {
      it("should create the actual jsPlumb endpoint", function() {
        var x4 = new EndpointView({
          state: x,
          collection: x.endpoints.members.get('endpoints'),
          model: new EndpointModel({id: 'x4'})
        });

        assert.isUndefined(jsPlumb.getEndpoint('x4'));

        x4.render();

        assert.isDefined(jsPlumb.getEndpoint('x4'));
        assert.equal(
          jsPlumb
            .getEndpoint('x4')
            .getElement()
            .get(0),
          x.el);
      });
    });
  });

  describe(".StaticEndpoint", function() {
    var EndpointModel = stateMachine.EndpointModel,
        StaticEndpoint = plumbing.StaticEndpoint;

    var endpoint;

    beforeEach(function() {
      var x = diagram.states.get('x');

      endpoint = new StaticEndpoint({
        state: x,
        collection: x.endpoints.members.get('endpoints'),
        model: new EndpointModel({id: 'x4'})
      });
    });

    describe(".anchors", function() {
      var anchors;

      beforeEach(function() {
        anchors = StaticEndpoint.prototype.anchors;
      });
      
      it("should a provide jsPlumb anchor generators for each side of a state",
      function() {
        assert.deepEqual(anchors.left(0.3), [0, 0.3, -1, 0]);
        assert.deepEqual(anchors.right(0.3), [1, 0.3, 1, 0]);
        assert.deepEqual(anchors.top(0.3), [0.3, 0, 0, -1]);
        assert.deepEqual(anchors.bottom(0.3), [0.3, 1, 0, 1]);
      });
    });

    describe(".render", function() {
      var plumbEndpoint;

      beforeEach(function() {
        // ensure the plumb endpoint exists
        diagram.render();
        endpoint.render();

        plumbEndpoint = endpoint.plumbEndpoint;
        sinon.stub(plumbEndpoint, 'setAnchor');
      });

      afterEach(function() {
        plumbEndpoint.setAnchor.restore();
      });

      it("reposition the endpoint according to its anchor position",
      function() {
        endpoint
          .reposition(0.2)
          .render();

        assert(plumbEndpoint.setAnchor.calledWith([0, 0.2, -1, 0]));

        endpoint
          .reposition(0.1)
          .render();

        assert(plumbEndpoint.setAnchor.calledWith([0, 0.1, -1, 0]));
      });
    });
  });

  describe(".AligningEndpointCollection", function() {
    var EndpointModel = stateMachine.EndpointModel,
        StaticEndpoint = plumbing.StaticEndpoint;

    var AligningEndpointCollection
      = plumbing.AligningEndpointCollection;

    var MockAligningEndpointCollection = AligningEndpointCollection.extend({
      render: function() {
        AligningEndpointCollection.prototype.render.call(this);
        this.rendered = true;
        return this;
      }
    });

    var MockStaticEndpoint = StaticEndpoint.extend({
      reposition: function(t) {
        StaticEndpoint.prototype.reposition.call(this, t);
        this.t = t;
        return this;
      },

      render: function() {
        StaticEndpoint.prototype.render.call(this);
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
        type: MockStaticEndpoint,
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
