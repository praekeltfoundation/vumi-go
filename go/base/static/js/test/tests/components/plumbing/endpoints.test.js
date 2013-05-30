describe("go.components.plumbing (endpoints)", function() {
  var states = go.components.states,
      StateMachineModel = states.StateMachineModel,
      EndpointModel = states.EndpointModel;

  var plumbing = go.components.plumbing,
      DiagramView = go.components.plumbing.DiagramView,
      EndpointView = plumbing.EndpointView;

  var diagram;

  beforeEach(function() {
    var smModel = new StateMachineModel({
      states: [{
        id: 'a',
        endpoints: [
          {id: 'a1'},
          {id: 'a2'},
          {id: 'a3', target: {id: 'b3'}}]
      }, {
        id: 'b',
        endpoints: [
          {id: 'b1'},
          {id: 'b2'},
          {id: 'b3'}]
      }]
    });

    $('body').append("<div id='diagram'></div>");
    diagram = new DiagramView({el: '#diagram', model: smModel});
  });

  afterEach(function() {
    Backbone.Relational.store.reset();
    jsPlumb.unbind();
    jsPlumb.detachEveryConnection();
    $('#diagram').remove();
  });

  describe(".EndpointView", function() {
    var a, b,
        a1, a2, a3,
        b1, b2, b3;

    beforeEach(function() {
      a = diagram.states.get('a');
      a1 = diagram.endpoints.get('a1');
      a2 = diagram.endpoints.get('a2');
      a3 = diagram.endpoints.get('a3');

      b = diagram.states.get('b');
      b1 = diagram.endpoints.get('b1');
      b2 = diagram.endpoints.get('b2');
      b3 = diagram.endpoints.get('b3');

      diagram.render();
    });
    
    describe("on 'connect' events", function() {
      it("should set its model's target", function(done) {
        a1.on('connect', function() {
          assert.equal(a1.model.get('target'), b1.model);
          done();
        });

        a1.trigger('connect', a1, b1);
      });
    });

    describe("on 'disconnect' events", function() {
      it("should set its model's target", function(done) {
        a3.on('disconnect', function() {
          assert(!a3.model.has('target'));
          done();
        });

        a3.trigger('disconnect', a3, b3);
      });
    });

    describe(".destroy", function() {
      it("should remove the actual jsPlumb endpoint", function() {
        assert.isDefined(jsPlumb.getEndpoint('a1'));
        a1.destroy();
        assert.isNull(jsPlumb.getEndpoint('a1'));
      });
    });

    describe(".render", function() {
      it("should create the actual jsPlumb endpoint", function() {
        var a4 = new EndpointView({
          state: a,
          model: new EndpointModel({id: 'a4'})
        });

        assert.isUndefined(jsPlumb.getEndpoint('a4'));
        a4.render();
        assert.isDefined(jsPlumb.getEndpoint('a4'));
        assert.equal(
          jsPlumb.getEndpoint('a4').getElement().get(0),
          a.el);
      });
    });
  });
});
