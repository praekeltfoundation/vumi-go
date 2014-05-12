describe("go.apps.dialogue.states.group", function() {
  var dialogue = go.apps.dialogue;

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

  describe(".GroupStateEditView", function() {
    var state,
        editMode;

    beforeEach(function() {
      state = diagram.states.get('state5');
      editMode = state.modes.edit;
      state.edit();
    });

    describe("when there are no groups available", function() {
      it("should show there are no groups available", function() {
        diagram.model.set('groups', []);
        state.edit();

        assert.equal(
          editMode.$('.contact-group :selected').text(),
          'No groups available');
      });

      it("should not try change the state's group", function() {
        diagram.model.set('groups', []);
        state.edit();

        assert.equal(
          state.model.get('group').get('key'),
          'group1');

        editMode
          .$('.contact-group')
          .val('none')
          .change();

        assert.equal(
          state.model.get('group').get('key'),
          'group1');
      });
    });

    describe("when the currently assigned group changes", function() {
      it("should update the state's model", function() {
        assert.equal(
          state.model.get('group').get('key'),
          'group1');

        editMode
          .$('.contact-group')
          .val('group2')
          .change();

        assert.equal(
          state.model.get('group').get('key'),
          'group2');
      });
    });

    describe("when the current group is unassigned", function() {
      it("should update the state's model", function() {
        assert.equal(
          state.model.get('group').get('key'),
          'group1');

        editMode
          .$('.contact-group')
          .val('unassigned')
          .change();

        assert.isNull(state.model.get('group'));
      });
    });
  });

  describe(".GroupStatePreviewView", function() {
    var state,
        previewMode;

    beforeEach(function() {
      state = diagram.states.get('state5');
      previewMode = state.modes.preview;
      state.preview();
    });

    it("should show the currently assigned group", function() {
      state.preview();

      assert.equal(
        previewMode.$('.contact-group').text(),
        'Group 1');
    });

    it("should show that no group is assigned if relevant", function() {
      state.model.unset('group');
      state.preview();

      assert.equal(
        previewMode.$('.contact-group').text(),
        'No group assigned');
    });
  });
});
