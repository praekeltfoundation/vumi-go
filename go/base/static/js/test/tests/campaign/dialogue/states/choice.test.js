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

  describe(".ChoiceEditView", function() {
    var state,
        editMode,
        choice;

    beforeEach(function() {
      state = diagram.states.get('state1');
      editMode = state.modes.edit;
      state.edit();

      choice = editMode
        .partials
        .body
        .partials
        .choices
        .get('choice:endpoint1');
    });

    describe("when its input has changed", function() {
      it("should update its model's label attribute",
      function() {
        assert.equal(choice.model.get('label'), 'Red');

        choice.$('input')
          .val('Diplodocus')
          .change();

        assert.equal(choice.model.get('label'), 'Diplodocus');
      });
    });

    describe("when '.remove' is clicked", function() {
      it("should remove the choice endpoint from the state's model",
      function() {
        var choiceEndpoints = state.model.get('choice_endpoints');

        assert.isDefined(choiceEndpoints.get('endpoint1'));
        choice.$('.remove').click();
        assert.isUndefined(choiceEndpoints.get('endpoint1'));
      });

      it("should remove the choice element", function() {
        assert(oneElExists(editMode.$('[data-uuid="choice:endpoint1"]')));
        choice.$('.remove').click();
        assert(noElExists(editMode.$('[data-uuid="choice:endpoint1"]')));
      });
    });
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

    describe("on 'activate' events", function() {
      it("should add a new choice if the state's model has no choice endpoints",
      function(done) {
        // Set the state up to not have any endpoints
        var choices = state.endpoints.members.get('choice_endpoints');
        choices.each(function(c) { choices.remove(c); });
        state.render();

        assert.equal(choices.size(), 0);
        assert(noElExists(editMode.$('.choice')));
        assert(noElExists(state.$('.choice.endpoint')));

        editMode.on('activate', function() {
          assert.equal(choices.size(), 1);
          assert(oneElExists(editMode.$('.choice')));
          assert(oneElExists(state.$('.choice.endpoint')));
          done();
        });

        editMode.trigger('activate');
      });
    });

    describe("when '.text' has changed", function() {
      it("should update the 'text' attribute of the state's model",
      function() {
        assert.equal(
          state.model.get('text'),
          'What is your favourite colour?');

        editMode
          .$('.text')
          .val('What is your favourite dinosaur?')
          .change();

        assert.equal(
          state.model.get('text'),
          'What is your favourite dinosaur?');
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
          editMode.$('[data-uuid="choice:new-endpoint"]')));

        editMode.$('.new-choice').click();

        assert(oneElExists(
          editMode.$('[data-uuid="choice:new-endpoint"]')));
      });
    });
  });
});
