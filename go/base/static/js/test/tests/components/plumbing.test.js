describe("go.components.plumbing", function() {
  var states = go.components.states,
      plumbing = go.components.plumbing;

  var StateMachineModel = states.StateMachineModel;

  var StateDiagramView = plumbing.StateDiagramView;

  var stateMachineModel,
      diagram;

  beforeEach(function() {
    $('body').append("<div id='diagram'></div>");

    stateMachineModel = new StateMachineModel({
      states: [{
        id: 'a',
        endpoints: [
          {id: 'a1'},
          {id: 'a2'},
          {id: 'a3', target: {id: 'b2'}}]
      }, {
        id: 'b',
        endpoints: [
          {id: 'b1'},
          {id: 'b2'},
          {id: 'b3'}]
      }]
    });

    diagram = new StateDiagramView({
      el: '#diagram',
      model: stateMachineModel
    });

    diagram.render();
  });

  describe(".EndpointView", function() {
    var a1, a2, a3,
        b1, b2, b3;
    
    beforeEach(function() {
      a1 = diagram.endpoints.get('a1');
      a2 = diagram.endpoints.get('a2');
      a3 = diagram.endpoints.get('a3');

      b1 = diagram.endpoints.get('b1');
      b2 = diagram.endpoints.get('b2');
      b3 = diagram.endpoints.get('b3');
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
  });
});
