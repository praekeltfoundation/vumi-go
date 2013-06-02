describe("go.components.plumbing (endpoints)", function() {
  var stateMachine = go.components.stateMachine,
      StateMachineModel = stateMachine.StateMachineModel;

  var plumbing = go.components.plumbing,
      DiagramView = plumbing.DiagramView;

  var diagram;

  beforeEach(function() {
    var model = new StateMachineModel({
      states: [{
        id: 'state',
        endpoints: [
          {id: 'endpoint1'},
          {id: 'endpoint2'},
          {id: 'endpoint3'}]
      }]
    });

    $('body').append("<div id='diagram'></div>");
    diagram = new DiagramView({el: '#diagram', model: model});
  });

  afterEach(function() {
    Backbone.Relational.store.reset();
    jsPlumb.unbind();
    jsPlumb.detachEveryConnection();
    $('#diagram').remove();
  });

  describe(".EndpointView", function() {
    var EndpointModel = stateMachine.EndpointModel,
        EndpointView = plumbing.EndpointView;

    var state,
        endpoint1;

    beforeEach(function() {
      state = diagram.states.get('state');
      endpoint1 = diagram.endpoints.get('endpoint1');
      diagram.render();
    });
    
    describe(".destroy", function() {
      it("should remove the actual jsPlumb endpoint", function() {
        assert.isDefined(jsPlumb.getEndpoint('endpoint1'));
        endpoint1.destroy();
        assert.isNull(jsPlumb.getEndpoint('endpoint1'));
      });
    });

    describe(".render", function() {
      it("should create the actual jsPlumb endpoint", function() {
        var endpoint4 = new EndpointView({
          state: state,
          model: new EndpointModel({id: 'endpoint4'})
        });

        assert.isUndefined(jsPlumb.getEndpoint('endpoint4'));

        endpoint4.render();

        assert.isDefined(jsPlumb.getEndpoint('endpoint4'));
        assert.equal(
          jsPlumb.getEndpoint('endpoint4').getElement().get(0),
          state.el);
      });
    });
  });
});
