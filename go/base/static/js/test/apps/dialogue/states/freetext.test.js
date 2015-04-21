describe("go.apps.dialogue.states.freetext", function() {
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
          .val('What is your parrot doing?')
          .change();

        assert.equal(
          state.model.get('text'),
          'What is your parrot doing?');
      });
    });

    describe(".render", function() {
      it("should display the char count", function() {
        assert.equal(state.$('.char-count').text().trim(), '18 characters used.');

        state.model.set('text', 'Some text for testing char count');
        state.render();
        assert.equal(state.$('.char-count').text().trim(), '32 characters used.');
      });
    });
  });

  describe(".FreeTextStatePreviewView", function() {
    var state;

    beforeEach(function() {
      state = diagram.states.get('state2');
      state.preview();
    });

    describe(".render", function() {
      it("should display the char count", function() {
        assert.equal(state.$('.char-count').text().trim(), '18 characters used.');

        state.model.set('text', 'Some text for testing char count');
        state.render();
        assert.equal(state.$('.char-count').text().trim(), '32 characters used.');
      });
    });
  });

  describe(".FreeStateView", function() {
    var state;

    beforeEach(function() {
      state = diagram.states.get('state2');
      state.maxChars = 100;
    });

    describe(".calcChars", function(){
      it("should calculate the number of characters used", function(){
        assert.equal(state.calcChars(), 18);
      });
    });

    describe(".charsLeft", function(){
      it("should calculate the number of characters left", function(){
        assert.equal(state.charsLeft(), 82);
      });
    });

    describe(".tooManyChars", function(){
      it("should not add a class when maxChars exceeds calcChars", function(){
        assert.equal(state.tooManyChars(),'');
      });

      it("should add a class when calcChars exceeds maxChars", function(){
        state.maxChars = 5;
        assert.equal(state.tooManyChars(), 'text-danger');
      });
    });
  });
});
