describe("go.campaign.routing (models)", function() {
  var routing = go.campaign.routing,
      modelData = routing.testHelpers.modelData;

  var testHelpers = go.testHelpers,
      fakeServer = testHelpers.rpc.fakeServer;

  afterEach(function() {
    go.testHelpers.unregisterModels();
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

      it("should ensure duplicate routing entries aren't made", function() {
        var model = new CampaignRoutingModel({campaign_id: 'campaign1'});

        var assertEntries = function() {
          var entries = model.get('routing_entries');
          assert.equal(entries.size(), 1);
          assert.deepEqual(
            entries.map(function(e) { return e.id; }),
            ['endpoint1-endpoint4']);
        };

        model.fetch();
        server.respondWith(modelData);
        assertEntries();

        model.fetch();
        server.respondWith(modelData);
        assertEntries();
      });

      it("should update the model on the client side", function() {
        var model = new CampaignRoutingModel();
        model.fetch();
        server.respondWith(modelData);

        // Backbone.rpc adds an extra `_rpcId` attribute which isn't part of
        // our test model data. We need to exclude it for the assertion
        assert.deepEqual(_(model.toJSON()).omit('_rpcId'), {
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
          routing_blocks: [{
            uuid: 'routing-block1',
            type: 'keyword',
            name: 'keyword-routing-block',
            description: 'Keyword',
            channel_endpoints: [{uuid: 'endpoint4', name: 'default'}],
            conversation_endpoints: [{uuid: 'endpoint5', name: 'default'}]
          }, {
            uuid: 'routing-block2',
            type: 'keyword',
            name: 'keyword-routing-block',
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
      it("should issue the correct api request", function() {
        var model = new CampaignRoutingModel(modelData);
        model.save();
        server.assertRequest('update_routing_table', ['campaign1', modelData]);
      });
    });
  });
});
