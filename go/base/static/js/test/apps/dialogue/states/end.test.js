describe("go.apps.dialogue.states.end", function() {
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
          .val('So Long, and Thanks for All the Fish')
          .change();

        assert.equal(
          state.model.get('text'),
          'So Long, and Thanks for All the Fish');
      });
    });
  });

  describe(".EndStateView", function() {
    var state,
        charsLeft;

    beforeEach(function() {
      state = diagram.states.get('state3');
      state.maxChars = 100;
    });

    describe(".calcChars", function(){
      it("should calculate the number of characters used", function(){
        assert.equal(state.model.get('text').length, 31);
      });
    });

    describe(".charsLeft", function(){
      it("should calculate the number of characters left", function(){
        assert.equal(state.charsLeft(), 69);
      });
    });

    describe(".tooManyChars", function(){
      it("should not add a class when character count is in limit", function(){
        assert.equal(state.tooManyChars(),'');
      });

      it("should add a class when character count is not in limit", function(){
        state.maxChars = 5;
        assert.equal(state.tooManyChars(), 'text-danger');
      });
    });
  });
});
