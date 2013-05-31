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
    diagram =  new DiagramView({el: '#diagram', model: model});
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

    describe("on 'plumb:connect' events", function() {
      var connection,
          plumbEvent;
          
      beforeEach(function() {
        connection = new ConnectionView({source: a1, target: b1});
        plumbEvent = {connection: {}}; // stubbed plumb event
      });

      it("should use the connection given by the event as its own",
      function(done) {
        connection.on('plumb:connect', function() {
          assert.equal(connection.plumbConnection, plumbEvent.connection);
          done();
        });

        connection.trigger('plumb:connect', plumbEvent);
      });

      it("should trigger a 'connect' event on its endpoints",
      function(done) {
        var a1Connect,
            b1Connect;

        a1.on('connect', function(eventConnection) {
          assert.equal(connection, eventConnection);
          (a1Connect = true) && b1Connect && done();
        });

        b1.on('connect', function(eventConnection) {
          assert.equal(connection, eventConnection);
          a1Connect && (b1Connect = true) && done();
        });

        connection.trigger('plumb:connect', plumbEvent);
      });
    });


    describe("on 'plumb:disconnect' events", function() {
      var a3, b3,
          connection;
          
      beforeEach(function() {
        a3 = diagram.endpoints.get('a3');
        b3 = diagram.endpoints.get('b3');
        connection = diagram.connections.get('a3');
      });

      it("should destroy itself", function(done) {
        connection.on('plumb:disconnect', function() {
          assert.isNull(connection.plumbConnection);
          done();
        });

        connection.trigger('plumb:disconnect');
      });

      it("should trigger a 'disconnect' event on its endpoints",
      function(done) {
        var a1Disconnect,
            b1Disconnect;

        a3.on('disconnect', function(eventConnection) {
          assert.equal(connection, eventConnection);
          (a1Disconnect = true) && b1Disconnect && done();
        });

        b3.on('disconnect', function(eventConnection) {
          assert.equal(connection, eventConnection);
          a1Disconnect && (b1Disconnect = true) && done();
        });

        connection.trigger('plumb:disconnect');
      });
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
