describe("go.apps.dialogue.partials", function() {
  var partials = go.apps.dialogue.states.partials;

  var testHelpers = go.testHelpers,
      oneElExists = testHelpers.oneElExists,
      noElExists = testHelpers.noElExists;

  var dialogue = go.apps.dialogue,
      states = go.apps.dialogue.states;

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

  describe(".TextEditView", function() {
    var TextEditView = partials.TextEditView;

    var state,
        mode,
        text;

    beforeEach(function() {
      state = diagram.states.get('state1');
      mode = state.modes.edit;
      text = new TextEditView({mode: mode});
    });

    describe("when its element has changed", function() {
      beforeEach(function() {
        state.render();
        text.render();
      });

      it("should update the 'text' attribute of its state's model",
      function() {
        assert.equal(
          state.model.get('text'),
          'What is your favourite colour?');

        text.$el.val('What is your favourite dinosaur?').change();

        assert.equal(
          state.model.get('text'),
          'What is your favourite dinosaur?');
      });
    });

    describe(".render", function() {
      it("should render its state's text", function() {
        assert.equal(text.$el.val(), '');
        text.render();
        assert.equal(text.$el.val(), 'What is your favourite colour?');
      });
    });
  });
});
