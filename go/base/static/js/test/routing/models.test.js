describe("go.routing (models)", function() {
  var routing = go.routing,
      modelData = routing.testHelpers.modelData;

  var testHelpers = go.testHelpers,
      response = testHelpers.rpc.response,
      errorResponse = testHelpers.rpc.errorResponse,
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
        server.respondWith(response(modelData));

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
        var model = new RoutingModel();
        server.respondWith(response(modelData));

        model.fetch();
        server.respond();

        assert.deepEqual(model.toJSON(), {
          campaign_id: 'campaign1',
          channels: [{
            uuid: 'channel1',
            tag: ['apposit_sms', '*121#'],
            name: '*121#',
            description: 'Apposit Sms: *121#',
            endpoints: [{uuid: 'endpoint1', name: 'default'}]
          }, {
            uuid: 'channel2',
            tag: ['sigh_sms', '*131#'],
            name: '*131#',
            description: 'Sigh Sms: *131#',
            endpoints: [{uuid: 'endpoint2', name: 'default'}]
          }, {
            uuid: 'channel3',
            tag: ['larp_sms', '*141#'],
            name: '*141#',
            description: 'Larp Sms: *141#',
            endpoints: [{uuid: 'endpoint3', name: 'default'}]
          }],
          routers: [{
            uuid: 'router1',
            type: 'keyword',
            name: 'keyword-router',
            description: 'Keyword',
            channel_endpoints: [{uuid: 'endpoint4', name: 'default'}],
            conversation_endpoints: [{uuid: 'endpoint5', name: 'default'}]
          }, {
            uuid: 'router2',
            type: 'keyword',
            name: 'keyword-router',
            description: 'Keyword',
            channel_endpoints: [{uuid: 'endpoint6', name: 'default'}],
            conversation_endpoints: [{uuid: 'endpoint7', name: 'default'}]
          }],
          conversations: [{
            uuid: 'conversation1',
            type: 'bulk-message',
            name: 'bulk-message1',
            description: 'Some Bulk Message App',
            endpoints: [{uuid: 'endpoint8', name: 'default'}]
          }, {
            uuid: 'conversation2',
            type: 'bulk-message',
            name: 'bulk-message2',
            description: 'Some Other Bulk Message App',
            endpoints: [{uuid: 'endpoint9', name: 'default'}]
          }, {
            uuid: 'conversation3',
            type: 'js-app',
            name: 'js-app1',
            description: 'Some JS App',
            endpoints: [
              {uuid: 'endpoint10', name: 'default'},
              {uuid: 'endpoint11', name: 'sms'}]
          }],
          routing_entries: [{
            uuid: 'endpoint1-endpoint4',
            source: {uuid: 'endpoint1'},
            target: {uuid: 'endpoint4'}
          }]
        });
      });
    });

    describe(".save", function() {
      it("should issue the correct api request", function(done) {
        var model = new RoutingModel(modelData);

        server.respondWith(function(req) {
          assertRequest(
            req,
            '/api/v1/go/api',
            'update_routing_table',
            ['campaign1', modelData]);

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
