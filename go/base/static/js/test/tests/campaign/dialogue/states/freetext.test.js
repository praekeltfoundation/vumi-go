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

  describe(".FreeTextStateEditView", function() {
    var FreeTextStateEditView = states.choice.FreeTextStateEditView;

    var state,
        editMode;

    beforeEach(function() {
      state = diagram.states.get('state2');
      editMode = state.modes.edit;
      state.edit();
    });

    describe(".save", function() {
      it("should update the choice state's model", function() {
        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state2',
          name: 'Message 2',
          type: 'freetext',
          text: 'What is your name?',
          ordinal: 1,
          entry_endpoint: {uuid: 'endpoint3'},
          exit_endpoint: {uuid: 'endpoint4'}
        });

        editMode.$('.text').text('What is your parrot doing?');
        editMode.save();

        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state2',
          name: 'Message 2',
          type: 'freetext',
          ordinal: 1,
          text: 'What is your parrot doing?',
          entry_endpoint: {uuid: 'endpoint3'},
          exit_endpoint: {uuid: 'endpoint4'}
        });
      });
    });

    describe("when the '.save' button is clicked", function() {
      it("should update the choice state's model", function() {
        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state2',
          name: 'Message 2',
          type: 'freetext',
          text: 'What is your name?',
          ordinal: 1,
          entry_endpoint: {uuid: 'endpoint3'},
          exit_endpoint: {uuid: 'endpoint4'}
        });

        editMode.$('.text').text('What is your parrot doing?');
        editMode.$('.save').click();

        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state2',
          name: 'Message 2',
          type: 'freetext',
          ordinal: 1,
          text: 'What is your parrot doing?',
          entry_endpoint: {uuid: 'endpoint3'},
          exit_endpoint: {uuid: 'endpoint4'}
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
