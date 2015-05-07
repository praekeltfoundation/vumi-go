describe("go.routing (models)", function() {
  var routing = go.routing,
      modelData = routing.testHelpers.modelData;

  var testHelpers = go.testHelpers,
      response = testHelpers.rpc.response,
      assertRequest = testHelpers.rpc.assertRequest;

  afterEach(function() {
    go.testHelpers.unregisterModels();
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

  describe(".RoutingModel", function() {
    var RoutingModel = routing.models.RoutingModel;

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
});
