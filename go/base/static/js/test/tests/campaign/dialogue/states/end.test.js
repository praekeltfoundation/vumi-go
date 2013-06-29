describe("go.campaign.dialogue.states.choice", function() {
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

  describe(".EndStateEditView", function() {
    var state,
        editMode;

    beforeEach(function() {
      state = diagram.states.get('state3');
      editMode = state.modes.edit;
      state.edit();
    });

    describe(".save", function() {
      it("should update the choice state's model", function() {
        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state3',
          name: 'Ending 1',
          type: 'end',
          ordinal: 2,
          text: 'Thank you for taking our survey',
          entry_endpoint: {uuid: 'endpoint5'}
        });

        editMode.$('.text').text('So Long, and Thanks for All the Fish');
        editMode.save();

        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state3',
          name: 'Ending 1',
          type: 'end',
          ordinal: 2,
          text: 'So Long, and Thanks for All the Fish',
          entry_endpoint: {uuid: 'endpoint5'}
        });
      });
    });

    describe("when the '.save' button is clicked", function() {
      it("should update the choice state's model", function() {
        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state3',
          name: 'Ending 1',
          type: 'end',
          ordinal: 2,
          text: 'Thank you for taking our survey',
          entry_endpoint: {uuid: 'endpoint5'}
        });

        editMode.$('.text').text('So Long, and Thanks for All the Fish');
        editMode.$('.save').click();

        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state3',
          name: 'Ending 1',
          type: 'end',
          ordinal: 2,
          text: 'So Long, and Thanks for All the Fish',
          entry_endpoint: {uuid: 'endpoint5'}
        });
      });

      it("should switch back to the preview view", function() {
        assert.equal(state.modeName, 'edit');
        editMode.$('.save').click();
        assert.equal(state.modeName, 'preview');
      });
    });
  });
});
