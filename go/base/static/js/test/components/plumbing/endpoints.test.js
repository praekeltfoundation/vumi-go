describe("go.components.plumbing.endpoints", function() {
  var testHelpers = go.testHelpers,
      oneElExists = testHelpers.oneElExists,
      noElExists = testHelpers.noElExists;

  var stateMachine = go.components.stateMachine;

  var plumbing = go.components.plumbing;

  var setUp = plumbing.testHelpers.setUp,
      newSimpleDiagram = plumbing.testHelpers.newSimpleDiagram,
      newComplexDiagram = plumbing.testHelpers.newComplexDiagram,
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
        EndpointView = plumbing.endpoints.EndpointView;

    var ToyEndpointView = EndpointView.extend();

    var x,
        x1;

    beforeEach(function() {
      x = diagram.states.get('x');
      x1 = diagram.endpoints.get('x1');
      diagram.render();
    });

    describe(".isConnected", function() {
      it("should determine whether the endpoint is connected", function() {
        assert(diagram.endpoints.get('x3').isConnected());
        assert(diagram.endpoints.get('y2').isConnected());
        assert(!diagram.endpoints.get('x1').isConnected());
      });
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
        x4 = x.endpoints.add('endpoints', new ToyEndpointView({
          state: x,
          collection: x.endpoints.members.get('endpoints'),
          model: new EndpointModel({uuid: 'x4'})
        }), {render: false});
      });

      it("should append the endpoint to the state element", function() {
        assert(noElExists('[data-uuid="x4"]'));
        x4.render();
        assert(oneElExists('[data-uuid="x4"]'));
      });

      it("should add a source endpoint class if is is a source", function() {
        x4.isSource = false;
        x4.render();
        assert(!x4.$el.hasClass('endpoint-source'));

        x4.isSource = true;
        x4.render();
        assert(x4.$el.hasClass('endpoint-source'));
      });

      it("should add a target endpoint class if is is a target", function() {
        x4.isTarget = false;
        x4.render();
        assert(!x4.$el.hasClass('endpoint-target'));

        x4.isTarget = true;
        x4.render();
        assert(x4.$el.hasClass('endpoint-target'));
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

  describe(".DiagramEndpointGroup", function() {
    var StateModel = stateMachine.StateModel,
        StateView = plumbing.states.StateView,
        DiagramEndpointGroup = plumbing.endpoints.DiagramEndpointGroup;

    var endpoints,
        a3,
        a1;

    var assertSubscribed = function(id, subscriber) {
      assert(endpoints.members.has(id));
      assert.includeMembers(endpoints.keys(), subscriber.keys());
    };

    var assertUnsubscribed = function(id, subscriber) {
      assert(!endpoints.members.has(id));
      subscriber.eachItem(function(id) { assert(!endpoints.has(id)); });
    };

    beforeEach(function() {
      diagram = newComplexDiagram();
      endpoints = new DiagramEndpointGroup(diagram);

      var modelA3 = new StateModel({
        uuid: 'a3',
        left: [{uuid: 'a3L1'}, {uuid: 'a3L2'}],
        right: [{uuid: 'a3R1'}, {uuid: 'a3R2'}]
      });

      a3 = new StateView({
        diagram: diagram,
        collection: diagram.states.members.get('apples'),
        model: modelA3
      });

      a1 = diagram.states.get('a1');
    });

    describe("on 'add' state events", function() {
      it("should subscribe the new state's endpoints to the group",
      function(done) {
        diagram.states.on('add', function() {
          assertSubscribed('a3', a3.endpoints);
          done();
        });

        diagram.states.add('apples', a3);
      });
    });

    describe("on 'remove' state events", function() {
      it("should unsubscribe the state's endpoints from the group",
      function(done) {
        diagram.states.on('remove', function() {
          assertUnsubscribed('a1', a1.endpoints);
          done();
        });

        diagram.states.members.get('apples').remove('a1');
      });
    });

    describe(".addState", function() {
      it("should subscribe the state's endpoints to the group", function() {
        endpoints.addState('a3', a3);
        assertSubscribed('a3', a3.endpoints);
      });
    });

    describe(".removeState", function() {
      it("should unsubscribe the state's endpoints from the group",
      function() {
        endpoints.removeState('a1');
        assertUnsubscribed('a1', a1.endpoints);
      });
    });
  });


  describe(".PositionableEndpointView", function() {
    var PositionableEndpointView = plumbing.endpoints.PositionableEndpointView;

    var ToyEndpointView = PositionableEndpointView.extend({
      reposition: function(p) { this.p = p; },
      position: function() { return this.p || {top: 0, left: 0}; }
    });

    var state,
        endpoint;

    beforeEach(function() {
      state = diagram.states.get('x');

      endpoint = state.endpoints.add('endpoints', new ToyEndpointView({
        state: state,
        collection: state.endpoints.members.get('endpoints'),
        model: new EndpointModel({uuid: 'x4'})
      }), {render: false});

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
        ParametricEndpointView = plumbing.endpoints.ParametricEndpointView;

    var state,
        endpoint;

    beforeEach(function() {
      state = diagram.states.get('x');

      endpoint = state.endpoints.add('endpoints', new ParametricEndpointView({
        state: state,
        collection: state.endpoints.members.get('endpoints'),
        model: new EndpointModel({uuid: 'x4'})
      }), {render: false});

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
            {left: -10, top: 145});
        });
      });

      describe(".right", function() {
        it("should find the position on the right corresponding to param t",
        function() {
          assert.deepEqual(
            positioners.right.call(endpoint, 0.5),
            {left: 190, top: 145});
        });
      });

      describe(".top", function() {
        it("should find the position on the top corresponding to param t",
        function() {
          assert.deepEqual(
            positioners.top.call(endpoint, 0.5),
            {left: 90, top: -5});
        });
      });

      describe(".bottom", function() {
        it("should find the position on the bottom corresponding to param t",
        function() {
          assert.deepEqual(
            positioners.bottom.call(endpoint, 0.5),
            {left: 90, top: 295});
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
          {left: -10, top: 55});

        endpoint
          .reposition(0.1)
          .render();

        assert.deepEqual(
          endpoint.$el.position(),
          {left: -10, top: 25});
      });
    });
  });

  describe(".FollowingEndpointView", function() {
    var FollowingEndpointView = plumbing.endpoints.FollowingEndpointView;

    var state,
        endpoint,
        $target;

    beforeEach(function() {
      $target = $('<span></span').attr('id', 'target');

      state = diagram.states.get('x');
      state.$el.append($target);

      endpoint = state.endpoints.add('endpoints', new FollowingEndpointView({
        state: state,
        target: '#target',
        collection: state.endpoints.members.get('endpoints'),
        model: new EndpointModel({uuid: 'x4'})
      }));

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
        ParametricEndpointView = plumbing.endpoints.ParametricEndpointView;

    var AligningEndpointCollection
      = plumbing.endpoints.AligningEndpointCollection;

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
