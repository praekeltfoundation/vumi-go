describe("go.campaign.dialogue.states.end", function() {
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

    describe("when '.text' has changed", function() {
      it("should update the 'text' attribute of the state's model",
      function() {
        assert.equal(
          state.model.get('text'),
          'Thank you for taking our survey');

        editMode
          .$('.text')
          .text('So Long, and Thanks for All the Fish')
          .change();

        assert.equal(
          state.model.get('text'),
          'So Long, and Thanks for All the Fish');
      });
    });
  });
});
