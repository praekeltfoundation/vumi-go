describe("go.components.plumbing (connections)", function() {
  var stateMachine = go.components.stateMachine,
      StateMachineModel = stateMachine.StateMachineModel;

  var plumbing = go.components.plumbing,
      DiagramView = go.components.plumbing.DiagramView;

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
    diagram =  new DiagramView({el: '#diagram', model: smModel});
  });

  afterEach(function() {
    Backbone.Relational.store.reset();
    jsPlumb.unbind();
    jsPlumb.detachEveryConnection();
    $('#diagram').remove();
  });

  describe(".ConnectionView", function() {
    var ConnectionView = plumbing.ConnectionView;

    var a1, b1;

    beforeEach(function() {
      a1 = diagram.endpoints.get('a1');
      b1 = diagram.endpoints.get('b1');
      diagram.render();
    });


    describe(".destroy", function() {
      it("should remove the actual jsPlumb connection", function(done) {
        jsPlumb.bind('connectionDetached', function(e) {
          assert.equal(connection.plumbConnection, e.connection);
          done();
        });

        var connection = diagram.connections.get('a3');
        connection.destroy();
      });
    });

    describe(".render", function() {
      it("should create the actual jsPlumb connection", function(done) {
        var connection = new ConnectionView({source: a1, target: b1});

        jsPlumb.bind('connection', function(e) {
          assert.equal(connection.source.plumbEndpoint,
                       e.sourceEndpoint);

          assert.equal(connection.target.plumbEndpoint,
                       e.targetEndpoint);
          done();
        });

        connection.render();
      });
    });
  });
});
