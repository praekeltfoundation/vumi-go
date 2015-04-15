describe("go.components.plumbing.connections", function() {
  var stateMachine = go.components.stateMachine;

  var plumbing = go.components.plumbing;

  var testHelpers = plumbing.testHelpers,
      setUp = testHelpers.setUp,
      newSimpleDiagram = testHelpers.newSimpleDiagram,
      newComplexDiagram = testHelpers.newComplexDiagram,
      tearDown = testHelpers.tearDown;

  beforeEach(function() {
    setUp();
  });

  afterEach(function() {
    tearDown();
  });

  describe(".ConnectionView", function() {
    var ConnectionModel = stateMachine.ConnectionModel,
        ConnectionView = plumbing.connections.ConnectionView;

    var diagram,
        x1,
        y1,
        x3_y2;

    beforeEach(function() {
      diagram = new newSimpleDiagram();
      x1 = diagram.endpoints.get('x1');
      y1 = diagram.endpoints.get('y1');
      x3_y2 = diagram.connections.get('x3-y2');
      diagram.render();
    });

    describe(".destroy", function() {
      it("should detach the connection", function(done) {
        var plumbConnection = x3_y2.plumbConnection;

        jsPlumb.bind('connectionDetached', function(e) {
          assert.equal(plumbConnection, e.connection);
          done();
        });

        x3_y2.destroy({fireDetach: true});
      });

      it("should unset the jsPlumb connection", function() {
        assert.isNotNull(x3_y2.plumbConnection);
        x3_y2.destroy();
        assert.isNull(x3_y2.plumbConnection);
      });

      it("should not detach if told not to", function() {
        var plumbConnection = x3_y2.plumbConnection;
        var detached = false;
        jsPlumb.detach(plumbConnection);
        jsPlumb.bind('connectionDetached', function() { detached = true; });
        x3_y2.destroy({
          detach: false,
          fireDetach: true
        });
        assert(!detached);
      });
    });

    describe(".render", function() {
      var connection;

      beforeEach(function() {
        connection = diagram.connections.add('connections', {
          model: {
            source: {uuid: 'x1'},
            target: {uuid: 'y1'}
          }
        }, {render: false});
      });

      it("should create the actual jsPlumb connection", function(done) {
        jsPlumb.bind('connection', function(e) {
          assert(connection.source.$el.is(e.source));
          assert(connection.target.$el.is(e.target));
          done();
        });

        connection.render();
      });
    });
  });

  describe(".ConnectionCollection", function() {
    var diagram,
        connections;

    beforeEach(function() {
      diagram = newComplexDiagram();
      connections = diagram.connections.members.get('leftToRight');
    });

    describe(".accepts", function() {
      it("should determine whether the source and target belong", function() {
        var a1L1 = diagram.endpoints.get('a1L1'),
            b1R1 = diagram.endpoints.get('b1R1');

        assert(connections.accepts(a1L1, b1R1));
        assert(!connections.accepts(b1R1, a1L1));
      });
    });
  });

  describe(".DiagramConnectionGroup", function() {
    var DiagramConnectionGroup = plumbing.connections.DiagramConnectionGroup;

    var diagram,
        connections,
        leftToRight;

    beforeEach(function() {
      diagram = newComplexDiagram();
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
      var EndpointView = plumbing.endpoints.EndpointView,
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

      it("should ignore the event if the connection has no target", function() {
        var a1L2 = diagram.endpoints.get('a1L2');
        var b2R2 = diagram.endpoints.get('b2R2');
        var a1L2_b2R2 = connections.get('a1L2-b2R2');
        var plumbConnection = a1L2_b2R2.plumbConnection;

        plumbConnection.target = null;
        a1L2_b2R2.plumbConnection.target = null;

        sinon.spy(console, 'log');
        jsPlumb.detach(a1L2_b2R2.plumbConnection);

        // jsPlumb logs errors instead of throwing them
        assert(!console.log.called);
        console.log.restore();
      });
    });
  });
});
