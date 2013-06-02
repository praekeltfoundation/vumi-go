describe("go.components.plumbing (connections)", function() {
  var stateMachine = go.components.stateMachine,
      StateMachineModel = stateMachine.StateMachineModel;

  var plumbing = go.components.plumbing,
      DiagramView = go.components.plumbing.DiagramView;

  var diagram;

  beforeEach(function() {
    var model = new StateMachineModel({
      states: [{
        id: 'a',
        endpoints: [
          {id: 'a1'},
          {id: 'a2'},
          {id: 'a3'}]
      }, {
        id: 'b',
        endpoints: [
          {id: 'b1'},
          {id: 'b2'},
          {id: 'b3'}]
      }],

      connections: [{
        id: 'a3-b2',
        source: {id: 'a3'},
        target: {id: 'b2'}
      }]
    });

    $('body').append("<div id='diagram'></div>");
    diagram =  new DiagramView({el: '#diagram', model: model});
  });

  afterEach(function() {
    Backbone.Relational.store.reset();
    jsPlumb.unbind();
    jsPlumb.detachEveryConnection();
    $('#diagram').remove();
  });

  describe(".ConnectionView", function() {
    var ConnectionModel = stateMachine.ConnectionModel,
        ConnectionView = plumbing.ConnectionView;

    var a1,
        b1,
        a3B2;

    beforeEach(function() {
      a1 = diagram.endpoints.get('a1');
      b1 = diagram.endpoints.get('b1');
      a3B2 = diagram.connections.get('a3-b2');
      diagram.render();
    });

    describe(".destroy", function() {
      it("should remove the actual jsPlumb connection", function(done) {
        var plumbConnection = a3B2.plumbConnection;

        assert(plumbConnection);

        jsPlumb.bind('connectionDetached', function(e) {
          assert.equal(plumbConnection, e.connection);
          assert.isNull(a3B2.plumbConnection);
          done();
        });

        a3B2.destroy();
      });
    });

    describe(".render", function() {
      it("should create the actual jsPlumb connection", function(done) {
        var connection = new ConnectionView({
          diagram: diagram,
          model: new ConnectionModel({
            id: 'a1-b1',
            source: {id: 'a1'},
            target: {id: 'b1'}
          })
        });

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
