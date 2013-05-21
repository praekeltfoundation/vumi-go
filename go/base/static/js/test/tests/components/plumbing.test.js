describe("go.components.plumbing", function() {
  var plumbing = go.components.plumbing,
      StateModel = plumbing.StateModel,
      StateView = plumbing.StateView,
      PlumbView = plumbing.PlumbView,
      EndpointModel = plumbing.EndpointModel,
      EndpointCollection = plumbing.EndpointCollection,
      EndpointView = plumbing.EndpointView;

  var stateA,
      stateB,
      plumbView;

  var endpointA1,
      endpointA2,
      endpointA3,
      endpointB1,
      endpointB2,
      endpointB3;

  beforeEach(function() {
    var stateModelA,
        stateModelB;

    $('body').append("<div class='dummy'></div>");
    $('.dummy').html("<div id='state-a'></div><div id='state-b'></div>");

    stateModelA = new StateModel({
      id: 'state-a',
      endpoints: [
        {id: 'endpoint-a1'},
        {id: 'endpoint-a2'},
        {id: 'endpoint-a3'}]
    });
    stateA = new StateView({
      el: '.dummy #state-a',
      model: stateModelA 
    });

    stateModelB = new StateModel({
      id: 'state-b',
      endpoints: [
        {id: 'endpoint-b1'},
        {id: 'endpoint-b2'},
        {id: 'endpoint-b3'}]
    });
    stateB = new StateView({
      el: '.dummy #state-b',
      model: stateModelB
    });

    plumbView = new PlumbView({states: [stateA, stateB]});
    plumbView.render();

    endpointA1 = stateA.endpoints['endpoint-a1'];
    endpointA2 = stateA.endpoints['endpoint-a2'];
    endpointA3 = stateA.endpoints['endpoint-a3'];

    endpointB1 = stateB.endpoints['endpoint-b1'];
    endpointB2 = stateB.endpoints['endpoint-b2'];
    endpointB3 = stateB.endpoints['endpoint-b3'];
  });

  afterEach(function() {
    Backbone.Relational.store.reset();
    $('.dummy').remove();
    jsPlumb.unbind();
  });

  describe(".EndpointView", function() {
    describe("on 'connect'", function() {
      it("should set the model's target", function(done) {
        endpointA1.on('connect', function() {
          assert.equal(
            endpointA1.model.get('targetId'),
            endpointB1.model.id);

          done();
        });

        endpointA1.trigger(
          'connect',
          {source: endpointA1, target: endpointB1});
      });
    });

    describe("on 'disconnect'", function() {
      it("should set the model's target", function(done) {
        endpointA1.on('disconnect', function() {
          assert.equal(endpointA1.model.get('targetId'), null);
          done();
        });

        endpointA1.trigger(
          'disconnect',
          {source: endpointA1, target: endpointB1});
      });
    });
  });

  describe(".StateModel", function() {
    it("should react to endpoint collection changes", function(done) {
      var added = false,
          removed = false,
          maybeDone = function() { added && removed && done(); };

      stateA.model.on('add:endpoints', function(model) {
        added = true;
        maybeDone();
      });

      stateA.model.on('remove:endpoints', function(model) {
        removed = true;
        maybeDone();
      });

      stateA.model.get('endpoints').add({id: 'endpoint-a4'});

      stateA.model.get('endpoints').remove('endpoint-a4');
    });
  });

  describe(".StateView", function() {
    describe(".render", function() {
      it("should remove 'dead' endpoints", function() {
        stateA.model.get('endpoints').remove('endpoint-a2');
        stateA.render();

        // assert that the model that was removed no longer has a view
        assert.notProperty(stateA.endpoints, 'endpoint-a2');
      });

      it("should add 'new' endpoints", function() {
        var endpointA4 = new EndpointModel({id: 'endpoint-a4'});

        stateA.model.get('endpoints').add(endpointA4);
        stateA.render();

        // assert that the new model now has a corresponding view
        assert.property(stateA.endpoints, 'endpoint-a4');
        assert.equal(stateA.endpoints['endpoint-a4'].model, endpointA4);
      });
    });
  });

  describe(".PlumbView", function() {
    var connection,
        disconnection,
        onConnection = function(fn) { connection = fn; };
        onDisconnection = function(fn) { disconnection = fn; };

    var assertConnection = function(assertionFn) {
      onConnection(assertionFn);
      plumbView.connect(endpointA1, endpointB1);
    };

    var assertDisconnection = function(assertionFn) {
      assertConnection(function(e) {
        // first make sure it was connected before doing any assertions of
        // disconnection things
        assert.propertyVal(
          plumbView.connections,
          'endpoint-a1-endpoint-b1',
          e.connection);

        onDisconnection(assertionFn);
        plumbView.disconnect('endpoint-a1-endpoint-b1');
      });
    };

    beforeEach(function() {
      connection = function(){};
      disconnection = function(){};

      jsPlumb.bind('connection', function(e) { connection(e); });
      jsPlumb.bind('connectionDetached', function(e) { disconnection(e); });
    });

    describe("on 'connection' jsPlumb events", function() {
      it("should emit connection events on the involved endpoints",
         function(done) {
        var emissions = {a1: false, b1: false},
            maybeDone = function() { emissions.a1 && emissions.b1 && done(); };

        endpointA1.on('connection', function(e) {
          assert.equal(endpointA1, e.source);
          assert.equal(endpointB1, e.target);
          emissions.a1 = true;
          maybeDone();
        });

        endpointB1.on('connection', function(e) {
          assert.equal(endpointA1, e.source);
          assert.equal(endpointB1, e.target);
          emissions.b1 = true;
          maybeDone();
        });

        plumbView.connect(endpointA1, endpointB1);
      });

      it("should add the new connection to the view's connection lookup",
         function(done) {
        assertConnection(function(e) {
          assert.deepEqual(
            plumbView.connections,
            {'endpoint-a1-endpoint-b1': e.connection});
          done();
        });
      });
    });

    describe("on 'connectionDetached' jsPlumb events", function() {
      it("should remove the connection from the view's connection lookup",
         function(done) {
        assertDisconnection(function() {
          assert.notProperty(
            plumbView.connections,
            'endpoint-a1-endpoint-b1');

          done();
        });
      });
    });

    describe(".connect", function() {
      it("should connect two endpoints together", function(done) {
        assertConnection(function(e) {
          assert.equal(endpointA1.raw, e.sourceEndpoint);
          assert.equal(endpointB1.raw, e.targetEndpoint);

          done();
        });
      });
    });

    describe(".disconnect", function() {
      it("should disconnect two endpoints from each other", function(done) {
        assertDisconnection(function(e) {
          assert.equal(endpointA1.raw, e.sourceEndpoint);
          assert.equal(endpointB1.raw, e.targetEndpoint);

          done();
        });
      });
    });

    describe(".render", function() {
      beforeEach(function(done) {
        var connectionCount = 2;

        // Ensure connections are made from endpointA1 to endpointB1 and endpointB1 to endpointB2 before
        // running render tests
        onConnection(function() { --connectionCount || done(); });

        stateA.model
          .get('endpoints')
          .get('endpoint-a1')
          .set('targetId', 'endpoint-b1');

        stateA.model
          .get('endpoints')
          .get('endpoint-a2')
          .set('targetId', 'endpoint-b2');

        plumbView.connect(endpointA1, endpointB1);
        plumbView.connect(endpointA2, endpointB2);
      });

      afterEach(function() { jsPlumb.detachAllConnections(); });

      it("should remove 'dead' connections", function(done) {
        assert.property(plumbView.connections, 'endpoint-a1-endpoint-b1');
        assert.property(plumbView.connections, 'endpoint-a2-endpoint-b2');

        stateA.model
          .get('endpoints')
          .get('endpoint-a1')
          .set('targetId', null);

        onDisconnection(function(e) {
          assert.equal(endpointA1.raw, e.sourceEndpoint);
          assert.equal(endpointB1.raw, e.targetEndpoint);

          assert.notProperty(plumbView.connections, 'endpoint-a1-endpoint-b1');
          assert.property(plumbView.connections, 'endpoint-a2-endpoint-b2');

          done();
        });

        plumbView.render();
      });

      it("should add 'new' connections", function(done) {
        assert.property(plumbView.connections, 'endpoint-a1-endpoint-b1');
        assert.property(plumbView.connections, 'endpoint-a2-endpoint-b2');

        stateA.model
          .get('endpoints')
          .get('endpoint-a3')
          .set('targetId', 'endpoint-b3');

        onConnection(function(e) {
          assert.equal(endpointA3.raw, e.sourceEndpoint);
          assert.equal(endpointB3.raw, e.targetEndpoint);
          assert.property(plumbView.connections, 'endpoint-a3-endpoint-b3');

          done();
        });

        plumbView.render();
      });
    });
  });
});
