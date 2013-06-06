describe("go.components.plumbing (endpoints)", function() {
  var stateMachine = go.components.stateMachine;
      plumbing = go.components.plumbing;

  var testHelpers = plumbing.testHelpers,
      setUp = testHelpers.setUp,
      newSimpleDiagram = testHelpers.newSimpleDiagram,
      tearDown = testHelpers.tearDown;

  beforeEach(function() {
    setUp();
  });

  afterEach(function() {
    tearDown();
  });

  describe(".EndpointView", function() {
    var EndpointModel = stateMachine.EndpointModel,
        EndpointView = plumbing.EndpointView;

    var diagram,
        x,
        x1;

    beforeEach(function() {
      diagram = newSimpleDiagram();
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
});
