describe("go.campaign.dialogue.states.freetext", function() {
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
    var state,
        editMode;

    beforeEach(function() {
      state = diagram.states.get('state2');
      editMode = state.modes.edit;
      state.edit();
    });

    describe("when '.text' has changed", function() {
      it("should update the 'text' attribute of the state's model",
      function() {
        assert.equal(
          state.model.get('text'),
          'What is your name?');

        editMode
          .$('.text')
          .text('What is your parrot doing?')
          .change();

        assert.equal(
          state.model.get('text'),
          'What is your parrot doing?');
      });
    });
  });
});
