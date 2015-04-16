describe("go.apps.dialogue.models", function() {
  var dialogue = go.apps.dialogue,
      modelData = dialogue.testHelpers.modelData;

  var testHelpers = go.testHelpers,
      response = testHelpers.rpc.response,
      assertRequest = testHelpers.rpc.assertRequest;

  afterEach(function() {
    go.testHelpers.unregisterModels();
  });

  describe(".ChoiceEndpointModel", function() {
    var ChoiceEndpointModel = dialogue.models.ChoiceEndpointModel;

    var model;

    beforeEach(function() {
      model = new ChoiceEndpointModel();
    });

    afterEach(function() {
      Backbone.Relational.store.unregister(model);
    });

    describe("when its 'label' attr is changed", function() {
      it("should reset the default 'value' attr if it isn't user defined",
      function() {
        assert(!model.has('value'));
        assert.isFalse(model.get('user_defined_value'));

        model.set('label', 'Message 1');
        assert.equal(model.get('value'), 'message-1');

        model.set('value', 'user-defined-value');
        model.set('user_defined_value', true);
        model.set('label', 'User Defined Message');
        assert.equal(model.get('value'), 'user-defined-value');
      });
    });

    describe(".setValue", function() {
      it("should set its 'value' attr to a slug of the input", function() {
        assert(!model.has('value'));
        model.setValue('Some Value');
        assert.equal(model.get('value'), 'some-value');
      });
    });
  });

  describe(".DialogueStateModel", function() {
    var DialogueStateModel = dialogue.models.DialogueStateModel;

    var model;

    beforeEach(function() {
      model = new DialogueStateModel();
    });

    afterEach(function() {
      Backbone.Relational.store.unregister(model);
    });

    describe("when its 'name' attr is changed", function() {
      it("should reset the default 'store_as' attr if it isn't user defined",
      function() {
        assert(!model.has('store_as'));
        assert.isFalse(model.get('user_defined_store_as'));

        model.set('name', 'State 1');
        assert.equal(model.get('store_as'), 'state-1');

        model.set('store_as', 'user-defined-store-as');
        model.set('user_defined_store_as', true);
        model.set('name', 'User Defined Name');
        assert.equal(model.get('store_as'), 'user-defined-store-as');
      });
    });

    describe(".setStoreAs", function() {
      it("should set its 'store_as' attr to a slug of the input", function() {
        assert(!model.has('store_as'));
        model.setStoreAs('Some Value');
        assert.equal(model.get('store_as'), 'some-value');
      });
    });
  });

  describe(".DialogueModel", function() {
    var DialogueModel = dialogue.models.DialogueModel;

    var server;

    beforeEach(function() {
      server = sinon.fakeServer.create();
    });

    afterEach(function() {
      server.restore();
    });

    describe(".fetch", function() {
      it("should issue the correct api request", function(done) {
        var model = new DialogueModel({
          campaign_id: 'campaign-1',
          conversation_key: 'conversation-1',
        });

        server.respondWith(function(req) {
          assertRequest(
            req,
            '/api/v1/go/api',
            'conversation.dialogue.get_poll',
            ['campaign-1', 'conversation-1']);

          done();
        });

        model.fetch();
        server.respond();
      });

      it("should update the model on the client side", function() {
        var model = new DialogueModel();
        server.respondWith(response({poll: modelData()}));

        model.fetch();
        server.respond();

        assert.deepEqual(model.toJSON(), modelData());
      });
    });

    describe(".save", function() {
      it("should issue the correct api request", function(done) {
        var model = new DialogueModel(modelData());

        server.respondWith(function(req) {
          assertRequest(
            req,
            '/api/v1/go/api',
            'conversation.dialogue.save_poll',
            ['campaign-1', 'conversation-1', {poll: modelData()}]);

          done();
        });

        model.save();
        server.respond();
      });
    });
  });
});
