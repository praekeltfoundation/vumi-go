describe("go.components.plumbing", function() {
  var PlumbEndpoint = go.components.plumbing.PlumbEndpoint,
      PlumbError = go.components.plumbing.PlumbError,
      nodeA,
      nodeB,
      hostA,
      hostB,
      endpointA,
      endpointB;

  beforeEach(function() {
    $('body').append("<div class='dummy'></div>");
    $('.dummy').html("<div id='host-a'></div><div id='host-b'></div>");

    nodeA = new Backbone.Model({id: 'node-a'});
    nodeB = new Backbone.Model({id: 'node-b'});

    hostA = new Backbone.View({el: '.dummy #host-a', model: nodeA});
    hostB = new Backbone.View({el: '.dummy #host-b', model: nodeB});

    endpointA = new PlumbEndpoint({id: 'a', host: hostA, attr: 'target'});
    endpointB = new PlumbEndpoint({id: 'b', host: hostB, attr: 'target'});
  });

  afterEach(function() {
    $('.dummy').remove();
    jsPlumb.unbind();
  });

  describe(".PlumbEventDispatcher", function() {
    var PlumbEventDispatcher = go.components.plumbing.PlumbEventDispatcher,
        dispatcher;

    beforeEach(function() {
      dispatcher = new PlumbEventDispatcher();
      dispatcher.subscribe(endpointA);
      dispatcher.subscribe(endpointB);
    });

    it("should dispatch 'plumb:connect' events to the involved endpoints",
       function(done) {
      var aConnected = false,
          bConnected = false,
          maybeDone = function() { aConnected && bConnected && done(); };

      endpointA.on('plumb:connect', function(e) {
        assert.equal(e.sourceEndpoint, endpointA);
        assert.equal(e.targetEndpoint, endpointB);
        aConnected = true;
        maybeDone();
      });

      endpointB.on('plumb:connect', function(e) {
        assert.equal(e.sourceEndpoint, endpointA);
        assert.equal(e.targetEndpoint, endpointB);
        bConnected = true;
        maybeDone();
      });

      endpointA.connect(endpointB);
    });

    it("should allow endpoints to be subscribed", function() {
      var endpointC = new PlumbEndpoint({id: 'c', host: hostA, attr: 'target'});
      dispatcher.subscribe(endpointC);

      assert.deepEqual(dispatcher._endpoints,
                       {a: endpointA, b: endpointB, c: endpointC});
    });

    it("should allow endpoints to be unsubscribed", function() {
      dispatcher.unsubscribe('b');
      assert.deepEqual(dispatcher._endpoints, {a: endpointA});
    });
  });

  describe(".PlumbEndpoint", function() {
    it("should set the endpoint's target correctly on 'plumb:connect' events",
       function(done) {
      endpointA.on('plumb:connect', function(e) {
        assert.equal(endpointA.target, endpointB);
        assert.equal(nodeA.get('target'), nodeB.id);
        done();
      });

      endpointA.trigger(
        'plumb:connect',
        {sourceEndpoint: endpointA, targetEndpoint: endpointB});
    });

    describe(".connect", function() {
      it("should connect one endpoint to another", function(done) {
        jsPlumb.bind('jsPlumbConnection', function(e) {
          assert.equal(e.sourceEndpoint, endpointA.raw);
          assert.equal(e.targetEndpoint, endpointB.raw);
          done();
        });

        endpointA.connect(endpointB);
      });
    });
  });
});
