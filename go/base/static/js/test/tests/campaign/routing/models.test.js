describe("go.campaign.routing (models)", function() {
  var routing = go.campaign.routing,
      modelData = routing.testHelpers.modelData;

  var testHelpers = go.testHelpers,
      fakeServer = testHelpers.rpc.fakeServer;

  afterEach(function() {
    Backbone.Relational.store.reset();
  });

  describe(".CampaignRoutingModel", function() {
    var CampaignRoutingModel = routing.CampaignRoutingModel;

    var server;

    beforeEach(function() {
      server = fakeServer('/api/v1/go/api');
    });

    afterEach(function() {
      server.restore();
    });

    describe(".fetch", function() {
      it("should issue the correct api request", function() {
        var model = new CampaignRoutingModel({campaign_id: 'campaign1'});
        model.fetch();
        server.assertRequest('routing_table', ['campaign1']);
      });

      it("should update the model on the client side", function() {
        var model = new CampaignRoutingModel();
        model.fetch();
        server.respondWith(modelData);

        // Backbone.rpc adds an extra `_rpcId` attribute which isn't part of
        // our test model data. We need to exclude it for the assertion
        assert.deepEqual(modelData, _(model.toJSON()).omit('_rpcId'));
      });
    });

    describe(".save", function() {
      it("should issue the correct api request", function() {
        var model = new CampaignRoutingModel(modelData);
        model.save();
        server.assertRequest('update_routing_table', ['campaign1', modelData]);
      });
    });
  });
});
