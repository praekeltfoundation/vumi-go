describe("go.apps.dialogue.models", function() {
  var dialogue = go.apps.dialogue;

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
});
