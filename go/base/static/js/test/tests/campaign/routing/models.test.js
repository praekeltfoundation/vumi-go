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

    var server,
        data;

    beforeEach(function() {
      server = fakeServer('/api/v1/go/api');
      data = _.clone(modelData);
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
        server.respondWith(data);
        assert.deepEqual(model.toJSON(), data);
      });
    });

    describe(".save", function() {
      it("should issue the correct api request", function() {
        var model = new CampaignRoutingModel(data);
        model.save();
        server.assertRequest('update_routing_table', ['campaign1', data]);
      });
    });
  });
});
