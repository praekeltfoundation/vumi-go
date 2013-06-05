describe("go.components.plumbing (connections)", function() {
  var stateMachine = go.components.stateMachine;
      plumbing = go.components.plumbing;

  var testHelpers = plumbing.testHelpers,
      setUp = testHelpers.setUp,
      newSimpleDiagram = testHelpers.newSimpleDiagram,
      newComplexDiagram = testHelpers.newComplexDiagram,
      tearDown = testHelpers.tearDown;

  var diagram;

  beforeEach(function() {
    setUp();
  });

  afterEach(function() {
    tearDown();
  });

  describe(".ConnectionView", function() {
    beforeEach(function() {
      diagram = new newSimpleDiagram();
    });

    var ConnectionModel = stateMachine.ConnectionModel,
        ConnectionView = plumbing.ConnectionView;

    var x1,
        y1,
        x3_y2;

    beforeEach(function() {
      x1 = diagram.endpoints.get('x1');
      y1 = diagram.endpoints.get('y1');
      x3_y2 = diagram.connections.get('x3-y2');
      diagram.render();
    });

    describe(".destroy", function() {
      it("should remove the actual jsPlumb connection", function(done) {
        var plumbConnection = x3_y2.plumbConnection;

        assert(plumbConnection);

        jsPlumb.bind('connectionDetached', function(e) {
          assert.equal(plumbConnection, e.connection);
          assert.isNull(x3_y2.plumbConnection);
          done();
        });

        x3_y2.destroy();
      });
    });

    describe(".render", function() {
      it("should create the actual jsPlumb connection", function(done) {
        var x1_y1 = new ConnectionView({
          diagram: diagram,
          model: new ConnectionModel({
            id: 'x1-y1',
            source: {id: 'x1'},
            target: {id: 'y1'}
          })
        });

        jsPlumb.bind('connection', function(e) {
          assert.equal(x1_y1.source.plumbEndpoint,
                       e.sourceEndpoint);

          assert.equal(x1_y1.target.plumbEndpoint,
                       e.targetEndpoint);
          done();
        });

        x1_y1.render();
      });
    });
  });

  describe(".ConnectionCollection", function() {
    var connections;

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
});
