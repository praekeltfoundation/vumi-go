describe("go.campaign.dialogue.states.choice", function() {
  var testHelpers = go.testHelpers,
      oneElExists = testHelpers.oneElExists,
      noElExists = testHelpers.noElExists;

  var dialogue = go.campaign.dialogue,
      states = go.campaign.dialogue.states;

  var setUp = dialogue.testHelpers.setUp,
      tearDown = dialogue.testHelpers.tearDown,
      newDialogueDiagram = dialogue.testHelpers.newDialogueDiagram;

  var diagram;

  beforeEach(function() {
    setUp();
    diagram = newDialogueDiagram();
  });

  afterEach(function() {
    tearDown();
  });

  describe(".ChoiceStateEditView", function() {
    var ChoiceStateEditView = states.choice.ChoiceStateEditView;

    var state,
        editMode;

    beforeEach(function() {
      state = diagram.states.get('state1');
      editMode = state.modes.edit;
      state.edit();
    });

    describe(".save", function() {
      it("should update the choice state's model", function() {
        assert.deepEqual(state.model.toJSON(), {
          uuid: "state1",
          name: "Message 1",
          type: "choice",
          text: "What is your favourite colour?",
          ordinal: 0,
          entry_endpoint: {uuid: "endpoint0"},
          choice_endpoints: [
            {value: "value1", label: "Red", uuid: "endpoint1"},
            {value: "value2", label: "Blue", uuid: "endpoint2"}]
        });

        editMode.$('.text').text('What is your favourite dinosaur?');
        editMode.$('.choice input').eq(1).val('Diplodocus');
        editMode.save();

        assert.deepEqual(state.model.toJSON(), {
          uuid: "state1",
          name: "Message 1",
          type: "choice",
          text: "What is your favourite dinosaur?",
          ordinal: 0,
          entry_endpoint: {uuid: "endpoint0"},
          choice_endpoints: [
            {value: "value1", label: "Red", uuid: "endpoint1"},
            {value: "value2", label: "Diplodocus", uuid: "endpoint2"}]
        });
      });
    });

    describe("when the '.save' button is clicked", function() {
      it("should update the choice state's model", function() {
        assert.deepEqual(state.model.toJSON(), {
          uuid: "state1",
          name: "Message 1",
          type: "choice",
          text: "What is your favourite colour?",
          ordinal: 0,
          entry_endpoint: {uuid: "endpoint0"},
          choice_endpoints: [
            {value: "value1", label: "Red", uuid: "endpoint1"},
            {value: "value2", label: "Blue", uuid: "endpoint2"}]
        });

        editMode.$('.text').text('What is your favourite dinosaur?');
        editMode.$('.choice input').eq(1).val('Diplodocus');
        editMode.$('.save').click();

        assert.deepEqual(state.model.toJSON(), {
          uuid: "state1",
          name: "Message 1",
          type: "choice",
          text: "What is your favourite dinosaur?",
          ordinal: 0,
          entry_endpoint: {uuid: "endpoint0"},
          choice_endpoints: [
            {value: "value1", label: "Red", uuid: "endpoint1"},
            {value: "value2", label: "Diplodocus", uuid: "endpoint2"}]
        });
      });

      it("should switch back to the preview view", function() {
        assert.equal(state.modeName, 'edit');
        editMode.$('.save').click();
        assert.equal(state.modeName, 'preview');
      });
    });

    describe("when the '.new-choice' button is clicked", function() {
      beforeEach(function() {
        sinon.stub(uuid, 'v4', function() { return 'new-endpoint'; });
      });

      afterEach(function() {
        uuid.v4.restore();
      });

      it("should add a choice endpoint to the state's model", function() {
        var choiceEndpoints = state.model.get('choice_endpoints');

        assert.isUndefined(choiceEndpoints.get('new-endpoint'));
        editMode.$('.new-choice').click();
        assert.isDefined(choiceEndpoints.get('new-endpoint'));
      });

      it("should display the new choice", function() {
        var choiceEndpoints = state.model.get('choice_endpoints');

        assert(noElExists(
          editMode.$('.choice[data-endpoint-id="new-endpoint"]')));

        editMode.$('.new-choice').click();

        assert(oneElExists(
          editMode.$('.choice[data-endpoint-id="new-endpoint"]')));
      });
    });

    describe("when a '.choice .remove' button is clicked", function() {
      it("should remove the choice endpoint from the state's model",
      function() {
        var choiceEndpoints = state.model.get('choice_endpoints');

        assert.isDefined(choiceEndpoints.get('endpoint1'));
        editMode.$('.choice .remove').eq(0).click();
        assert.isUndefined(choiceEndpoints.get('endpoint1'));
      });

      it("should remove the choice element", function() {
        var choiceEndpoints = state.model.get('choice_endpoints');

        assert(oneElExists(
          editMode.$('.choice[data-endpoint-id="endpoint1"]')));

        editMode.$('.choice .remove').eq(0).click();

        assert(noElExists(
          editMode.$('.choice[data-endpoint-id="endpoint1"]')));
      });
    });
  });
});
