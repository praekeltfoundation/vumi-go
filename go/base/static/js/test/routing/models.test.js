describe("go.routing (models)", function() {
  var routing = go.routing,
      modelData = routing.testHelpers.modelData;

  var testHelpers = go.testHelpers,
      response = testHelpers.rpc.response,
      assertRequest = testHelpers.rpc.assertRequest;

  afterEach(function() {
    go.testHelpers.unregisterModels();
    localStorage.clear();
  });

  describe(".ChannelModel", function() {
    var ChannelModel = routing.models.ChannelModel;
    var model;

    beforeEach(function() {
      model = new ChannelModel({
        uuid: 'channel1',
        tag: ['apposit_sms', '*121#']
      });  
    });

    describe(".viewURL", function() {
      it("should return the channel's view url", function() {
        assert.equal(model.viewURL(), '/channels/apposit_sms%3A*121%23/');
      });
    });

  });

  describe(".RoutingStateCollection", function() {
    var localOrdinalsKey = routing.models.localOrdinalsKey,
        RoutingStateModel = routing.models.RoutingStateModel,
        RoutingStateCollection = routing.models.RoutingStateCollection;

    var ToyRoutingStateCollection = RoutingStateCollection.extend({
      type: 'jedis'
    });

    describe("when a model is added", function() {
      it("should set the model's ordinal using the cached ordinals", function() {
        go.local.set(localOrdinalsKey('campaign1', 'jedis'), ['c', 'a', 'b']);
        var models = new ToyRoutingStateCollection([], {routingId: 'campaign1'});

        models.add(new RoutingStateModel({uuid: 'a'}));
        assert.strictEqual(models.get('a').get('ordinal'), 1);

        models.add(new RoutingStateModel({uuid: 'b'}));
        assert.strictEqual(models.get('b').get('ordinal'), 2);

        models.add(new RoutingStateModel({uuid: 'c'}));
        assert.strictEqual(models.get('c').get('ordinal'), 0);
      });

      it("should set the model's ordinal to -1 if it is not cached", function() {
        go.local.set(localOrdinalsKey('campaign1', 'jedis'), []);
        var models = new ToyRoutingStateCollection([], {routingId: 'campaign1'});
        models.add(new RoutingStateModel({uuid: 'a'}));
        assert.strictEqual(models.get('a').get('ordinal'), -1);
      });
    });

    describe(".persistOrdinals", function() {
      it("should update local storage with the new ordinals", function() {
        go.local.set(localOrdinalsKey('campaign1', 'jedis'), ['c', 'a', 'b']);
        var models = new ToyRoutingStateCollection([], {routingId: 'campaign1'});

        models.add(new RoutingStateModel({uuid: 'a'}));
        models.add(new RoutingStateModel({uuid: 'b'}));
        models.add(new RoutingStateModel({uuid: 'c'}));

        models.get('a').set('ordinal', 0);
        models.get('b').set('ordinal', 2);
        models.get('c').set('ordinal', 1);

        assert.deepEqual(
          go.local.get(localOrdinalsKey('campaign1', 'jedis')),
          ['c', 'a', 'b']);

        models.persistOrdinals();

        assert.deepEqual(
          go.local.get(localOrdinalsKey('campaign1', 'jedis')),
          ['a', 'c', 'b']);
      });
    });
  });

  describe(".RoutingModel", function() {
    var RoutingModel = routing.models.RoutingModel,
        localOrdinalsKey = routing.models.localOrdinalsKey;

    var server;

    beforeEach(function() {
      server = sinon.fakeServer.create();
    });

    afterEach(function() {
      server.restore();
    });

    describe(".fetch", function() {
      it("should issue the correct api request", function(done) {
        var model = new RoutingModel({campaign_id: 'campaign1'});

        server.respondWith(function(req) {
          assertRequest(req, '/api/v1/go/api', 'routing_table', ['campaign1']);
          done();
        });

        model.fetch();
        server.respond();
      });

      it("should ensure duplicate routing entries aren't made", function() {
        var model = new RoutingModel({campaign_id: 'campaign1'});
        server.respondWith(response(modelData()));

        var assertEntries = function() {
          var entries = model.get('routing_entries');
          assert.equal(entries.size(), 1);
          assert.deepEqual(
            entries.map(function(e) { return e.id; }),
            ['endpoint1-endpoint4']);
        };

        model.fetch();
        server.respond();
        assertEntries();

        model.fetch();
        server.respond();
        assertEntries();
      });

      it("should update the model on the client side", function() {
        var model = new RoutingModel(modelData());
        var expected = model.toJSON();

        model.clear();
        server.respondWith(response(modelData()));

        model.fetch();
        server.respond();

        assert.deepEqual(model.toJSON(), expected);
      });
    });

    describe(".save", function() {
      it("should issue the correct api request", function(done) {
        var model = new RoutingModel(modelData());

        server.respondWith(function(req) {
          model.clear().set(modelData());

          assertRequest(
            req,
            '/api/v1/go/api',
            'update_routing_table',
            ['campaign1', model.toJSON()]);

          done();
        });

        model.save();
        server.respond();
      });
    });

    describe(".persistOrdinals", function() {
      it("should update local storage with the new ordinals", function() {
        var model = new RoutingModel(modelData());

        model.get('channels').reset([
          {uuid: 'channel-a'},
          {uuid: 'channel-b'},
          {uuid: 'channel-c'}]);

        model.get('routers').reset([
          {uuid: 'router-a'},
          {uuid: 'router-b'},
          {uuid: 'router-c'}]);

        model.get('conversations').reset([
          {uuid: 'conversation-a'},
          {uuid: 'conversation-b'},
          {uuid: 'conversation-c'}]);

        model.get('channels').get('channel-a').set('ordinal', 1);
        model.get('channels').get('channel-b').set('ordinal', 0);
        model.get('channels').get('channel-c').set('ordinal', 2);

        model.get('routers').get('router-a').set('ordinal', 2);
        model.get('routers').get('router-b').set('ordinal', 0);
        model.get('routers').get('router-c').set('ordinal', 1);

        model.get('conversations').get('conversation-a').set('ordinal', 0);
        model.get('conversations').get('conversation-b').set('ordinal', 2);
        model.get('conversations').get('conversation-c').set('ordinal', 1);

        assert.notDeepEqual(
          go.local.get(localOrdinalsKey(model.id, 'channels')),
          ['channel-b', 'channel-a', 'channel-c']);

        assert.notDeepEqual(
          go.local.get(localOrdinalsKey(model.id, 'routers')),
          ['router-b', 'router-c', 'router-a']);

        assert.notDeepEqual(
          go.local.get(localOrdinalsKey(model.id, 'conversations')),
          ['conversation-a', 'conversation-c', 'conversation-b']);

        model.persistOrdinals();

        assert.deepEqual(
          go.local.get(localOrdinalsKey(model.id, 'channels')),
          ['channel-b', 'channel-a', 'channel-c']);

        assert.deepEqual(
          go.local.get(localOrdinalsKey(model.id, 'routers')),
          ['router-b', 'router-c', 'router-a']);

        assert.deepEqual(
          go.local.get(localOrdinalsKey(model.id, 'conversations')),
          ['conversation-a', 'conversation-c', 'conversation-b']);
      });

      it("should trigger a 'persist:ordinals' event", function() {
        var model = new RoutingModel(modelData());
        var triggered = false;
        model.on('persist:ordinals', function() { triggered = true; });

        assert(!triggered);
        model.persistOrdinals();
        assert(triggered);
      });
    });
  });

  describe(".RouterModel", function() {
    var RouterModel = routing.models.RouterModel;
    var model;

    beforeEach(function() {
      model = new RouterModel({
        uuid: 'router1'
      });
    });

    describe(".viewURL", function() {
      it("should return the router's view url", function(){
        assert.equal(model.viewURL(), '/routers/router1/edit/');
      });
    });
  });

  describe(".ConversationModel", function() {
    var ConversationModel = routing.models.ConversationModel;
    var model;

    beforeEach(function() {
      model = new ConversationModel({
        uuid: 'conversation1'
      });
    });

    describe(".viewURL", function() {
      it("should return the conversation's view url", function() {
        assert.equal(model.viewURL(), '/conversations/conversation1/edit/');
      });
    });
  });

  describe(".localOrdinalsKey", function() {
    var localOrdinalsKey = routing.models.localOrdinalsKey;

    it("should return the corresponding local storage key", function() {
      assert.equal(
        localOrdinalsKey('campaign1', 'channels'),
        'campaign1:channels:ordinals');
    });
  });
});
