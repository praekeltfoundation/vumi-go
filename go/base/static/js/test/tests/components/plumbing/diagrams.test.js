describe("go.components.plumbing (diagrams)", function() {
  var stateMachine = go.components.stateMachine;
      plumbing = go.components.plumbing;

  var testHelpers = plumbing.testHelpers,
      setUp = testHelpers.setUp,
      newComplexDiagram = testHelpers.newComplexDiagram,
      tearDown = testHelpers.tearDown;

  var diagram;

  beforeEach(function() {
    setUp();
    diagram = newComplexDiagram();
  });

  afterEach(function() {
    tearDown();
  });

  describe(".DiagramViewConnections", function() {
    var DiagramViewConnections = plumbing.DiagramViewConnections;

    var connections,
        leftToRight;

    beforeEach(function() {
      connections = diagram.connections;
      leftToRight = connections.members.get('leftToRight');
    });

    describe(".determineCollection", function() {
      it("should determine which collection a source and target belong to",
      function() {
        assert.equal(
          connections.members.get('leftToRight'),
          connections.determineCollection(
            diagram.endpoints.get('a1L1'),
            diagram.endpoints.get('b2R1')));

        assert.equal(
          connections.members.get('rightToLeft'),
          connections.determineCollection(
            diagram.endpoints.get('b1R1'),
            diagram.endpoints.get('a2L1')));
      });
    });

    describe("on 'connection' jsPlumb events", function() {
      var EndpointView = plumbing.EndpointView,
          EndpointModel = stateMachine.EndpointModel;

      var UnknownEndpointView = EndpointView.extend();

      beforeEach(function() {
        // render the diagram to ensure the jsPlumb endpoints are drawn
        diagram.render();
      });

      it("should add a connection model and its view if they do not yet exist",
      function(done) {
        var a1L1 = diagram.endpoints.get('a1L1'),
            b2R1 = diagram.endpoints.get('b2R1');

        connections.on('add', function(id, connection) {
          // check that the model was added
          assert.equal(connection.model.get('source'), a1L1.model);
          assert.equal(connection.model.get('target'), b2R1.model);
          assert.equal(
            connection.model,
            leftToRight.models.get('a1L1-b2R1'));

          // check that the view was added
          assert.equal(connection.source, a1L1);
          assert.equal(connection.target, b2R1);
          assert.equal(connection, connections.get('a1L1-b2R1'));

          done();
        });

        jsPlumb.connect({source: a1L1.$el, target: b2R1.$el});
      });

      it("should fire an event when unsupported connections are encountered",
      function(done) {
        var a1L1 = diagram.endpoints.get('a1L1'),
            a1L2 = diagram.endpoints.get('a1L2');

        diagram.connections.on(
          'error:unsupported',
          function(source, target, plumbConnection) {
            assert.equal(source, a1L1);
            assert.equal(target, a1L2);
            assert(a1L1.$el.is(plumbConnection.source));
            assert(a1L2.$el.is(plumbConnection.target));
            done();
          });

        jsPlumb.connect({source: a1L1.$el, target: a1L2.$el});
      });
    });

    describe("on 'connectionDetached' jsPlumb events", function() {
      beforeEach(function() {
        // render the diagram and connections to ensure the jsPlumb endpoints
        // and connections are drawn
        diagram.render();
      });

      it("should remove the connection model and its view if they still exist",
      function(done) {
        var a1L2 = diagram.endpoints.get('a1L2'),
            b2R2 = diagram.endpoints.get('b2R2'),
            a1L2_b2R2 = connections.get('a1L2-b2R2');

        // make sure that the connection did initially exist
        assert(a1L2_b2R2);

        connections.on('remove', function(id, connection) {

          // check that the model was removed
          assert(!leftToRight.models.get('a1L2-b2R2'));
          assert.equal(connection.model.get('source'), a1L2.model);
          assert.equal(connection.model.get('target'), b2R2.model);

          // check that the view was removed
          assert(!connections.has('a1L2-b2R2'));
          assert.equal(a1L2_b2R2, connection);

          done();
        });

        jsPlumb.detach(a1L2_b2R2.plumbConnection);
      });
    });
  });

  describe(".Diagram", function() {
    var AppleStateView = testHelpers.AppleStateView,
        BananaStateView = testHelpers.BananaStateView;

    var LeftToRightView = testHelpers.LeftToRightView,
        RightToLeftView = testHelpers.RightToLeftView;

    it("should keep track of all endpoints in the diagram", function() {
      assert.deepEqual(
        diagram.endpoints.keys(),
        ['a1L1', 'a1L2', 'a1R1', 'a1R2',
         'a2L1', 'a2L2', 'a2R1', 'a2R2',
         'b1L1', 'b1L2', 'b1R1', 'b1R2',
         'b2L1', 'b2L2', 'b2R1', 'b2R2']);
    });

    it("should set up the connections according to the schema", function() {
      var leftToRight = diagram.connections.members.get('leftToRight'),
          rightToLeft = diagram.connections.members.get('rightToLeft');

      assert.deepEqual(leftToRight.keys(), ['a1L2-b2R2']);
      assert.deepEqual(rightToLeft.keys(), ['b1R2-a2L2']);

      leftToRight.each(
        function(e) { assert.instanceOf(e, LeftToRightView); });

      rightToLeft.each(
        function(e) { assert.instanceOf(e, RightToLeftView); });

      assert.deepEqual(
        diagram.connections.keys(),
        ['a1L2-b2R2', 'b1R2-a2L2']);
    });

    it("should set up the states according to the schema", function() {
      var apples = diagram.states.members.get('apples'),
          bananas = diagram.states.members.get('bananas');

      assert.deepEqual(apples.keys(), ['a1', 'a2']);
      assert.deepEqual(bananas.keys(), ['b1', 'b2']);

      apples.each(function(e) { assert.instanceOf(e, AppleStateView); });
      bananas.each(function(e) { assert.instanceOf(e, BananaStateView); });

      assert.deepEqual(diagram.states.keys(), ['a1', 'a2', 'b1', 'b2']);
    });

    describe(".render", function() {
      it("should render its states", function() {
        diagram.states.each(function(s) { assert(!s.rendered); });
        diagram.render();
        diagram.states.each(function(s) { assert(s.rendered); });
      });

      it("should render its connections", function() {
        diagram.connections.each(function(s) { assert(!s.rendered); });
        diagram.render();
        diagram.connections.each(function(s) { assert(s.rendered); });
      });
    });
  });
});
