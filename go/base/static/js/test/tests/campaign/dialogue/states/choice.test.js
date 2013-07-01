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
          .text('What is your favourite dinosaur?')
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

    describe("when a '.choice input' has changed", function() {
      it("should update the corresponding endpoint model's label attribute",
      function() {
        var endpoint = state.model
          .get('choice_endpoints')
          .get('endpoint2');

        assert.equal(endpoint.get('label'), 'Blue');

        editMode.$('.choice input')
          .eq(1)
          .val('Diplodocus')
          .change();

        assert.equal(endpoint.get('label'), 'Diplodocus');
      });
    });
  });
});
