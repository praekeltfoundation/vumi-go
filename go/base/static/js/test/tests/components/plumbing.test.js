describe("go.components.plumbing", function() {
  var plumbing = go.components.plumbing,
      StateModel = plumbing.StateModel,
      StateView = plumbing.StateView,
      PlumbView = plumbing.PlumbView,
      EndpointModel = plumbing.EndpointModel,
      EndpointCollection = plumbing.EndpointCollection,
      EndpointView = plumbing.EndpointView;

  var stateModelA,
      stateModelB,
      stateViewA,
      stateViewB,
      plumbView;

  beforeEach(function() {
    $('body').append("<div class='dummy'></div>");
    $('.dummy').html("<div id='state-a'></div><div id='state-b'></div>");

    stateModelA = new StateModel({
      id: 'state-a',
      endpoints: [
        {id: 'endpoint-a1'},
        {id: 'endpoint-a2'},
        {id: 'endpoint-a3'}]
    });
    stateViewA = new StateView({
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
    stateViewB = new StateView({
      el: '.dummy #state-b',
      model: stateModelB
    });

    plumbView = new PlumbView({states: [stateViewA, stateViewB]});
    plumbView.render();
  });

  afterEach(function() {
    $('.dummy').remove();
    jsPlumb.unbind();
  });

  describe(".StateModel", function() {
    afterEach(function() { stateModelA.off('change'); });

    it("should react to endpoint collection changes", function(done) {
      stateModelA.on('change', function(model, options) {
        assert.propertyVal(options, 'option', 'value');
        done();
      });

      stateModelA.get('endpoints').add({id: 'endpoint-a4'}, {option: 'value'});
    });

    describe(".parse", function() {
      it("should parse 'endpoints' attr as a collection", function() {
        var attrs = stateModelA.parse({
          id: 'state-a',
          endpoints: [
            {id: 'endpoint-a1'},
            {id: 'endpoint-a2'}]
        });

        assert.instanceOf(attrs.endpoints, EndpointCollection);
        assert.equal(attrs.endpoints.at(0).id, 'endpoint-a1');
        assert.equal(attrs.endpoints.at(1).id, 'endpoint-a2');
      });
    });
  });

  describe(".StateView", function() {
    describe(".render", function() {
      it("should remove 'dead' endpoints", function() {
        stateModelA.get('endpoints').remove('endpoint-a2');
        stateViewA.render();

        // assert that the model that was removed no longer has a view
        assert.notProperty(stateViewA.endpoints, 'endpoint-a2');
      });

      it("should add 'new' endpoints", function() {
        var a4 = new EndpointModel({id: 'endpoint-a4'});

        stateModelA.get('endpoints').add(a4);
        stateViewA.render();

        // assert that the new model now has a corresponding view
        assert.property(stateViewA.endpoints, 'endpoint-a4');
        assert.equal(stateViewA.endpoints['endpoint-a4'].model, a4);
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

      plumbView.connect(
        stateViewA.endpoints['endpoint-a1'],
        stateViewB.endpoints['endpoint-b1']);
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

    describe('on connection events', function() {
      it("should link the source and target model", function(done) {
        assertConnection(function() {
          var endpointA = stateModelA.get('endpoints').get('endpoint-a1');
          assert.equal(endpointA.get('targetId'), 'endpoint-b1');

          done();
        });
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

    describe('on disconnection events', function() {
      it("should unlink the source and target model", function(done) {
        assertDisconnection(function() {
          var endpointA = stateModelA
            .get('endpoints')
            .get('endpoint-a1');

          assert.isNull(endpointA.get('targetId'));

          done();
        });
      });

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

    describe('.connect', function() {
      it("should connect two endpoints together", function(done) {
        assertConnection(function(e) {
          assert.equal(
            stateViewA.endpoints['endpoint-a1'].raw,
            e.sourceEndpoint);

          assert.equal(
            stateViewB.endpoints['endpoint-b1'].raw,
            e.targetEndpoint);

          done();
        });
      });
    });

    describe('.disconnect', function() {
      it("should disconnect two endpoints from each other", function(done) {
        assertDisconnection(function(e) {
          assert.equal(
            stateViewA.endpoints['endpoint-a1'].raw,
            e.sourceEndpoint);

          assert.equal(
            stateViewB.endpoints['endpoint-b1'].raw,
            e.targetEndpoint);

          done();
        });
      });
    });

    describe('.render', function() {
      beforeEach(function(done) {
        var connectionCount = 2;

        // Ensure connections are made from a1 to b1 and b1 to b2 before
        // running render tests
        onConnection(function() { --connectionCount || done(); });

        plumbView.connect(
          stateViewA.endpoints['endpoint-a1'],
          stateViewB.endpoints['endpoint-b1']);

        plumbView.connect(
          stateViewA.endpoints['endpoint-a2'],
          stateViewB.endpoints['endpoint-b2']);
      });

      afterEach(function() { jsPlumb.detachAllConnections(); });

      it("should remove 'dead' connections", function(done) {
        assert.property(plumbView.connections, 'endpoint-a1-endpoint-b1');
        assert.property(plumbView.connections, 'endpoint-a2-endpoint-b2');

        stateModelA
          .get('endpoints')
          .get('endpoint-a1')
          .set('targetId', null);

        onDisconnection(function(e) {
          assert.equal(
            stateViewA.endpoints['endpoint-a1'].raw,
            e.sourceEndpoint);

          assert.equal(
            stateViewB.endpoints['endpoint-b1'].raw,
            e.targetEndpoint);

          assert.notProperty(plumbView.connections, 'endpoint-a1-endpoint-b1');
          assert.property(plumbView.connections, 'endpoint-a2-endpoint-b2');

          done();
        });

        plumbView.render();
      });

      it("should add 'new' connections", function(done) {
        assert.property(plumbView.connections, 'endpoint-a1-endpoint-b1');
        assert.property(plumbView.connections, 'endpoint-a2-endpoint-b2');

        stateModelA
          .get('endpoints')
          .get('endpoint-a3')
          .set('targetId', 'endpoint-b3');

        onConnection(function(e) {
          assert.equal(
            stateViewA.endpoints['endpoint-a3'].raw,
            e.sourceEndpoint);

          assert.equal(
            stateViewB.endpoints['endpoint-b3'].raw,
            e.targetEndpoint);

          assert.property(plumbView.connections, 'endpoint-a3-endpoint-b3');

          done();
        });

        plumbView.render();
      });
    });
  });
});
