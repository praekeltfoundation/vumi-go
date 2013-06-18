describe("go.campaign.dialogue.states", function() {
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

  describe(".DialogueStateModeView", function() {
    var DialogueStateModeView = states.DialogueStateModeView;

    var ToyStateModeView = DialogueStateModeView.extend({
      className: 'toy mode',
      template: _.template("<%= mode %> mode"),
      templateData: {mode: 'toy'}
    });

    var state,
        mode;

    beforeEach(function() {
      state = diagram.states.get('state-4');
      mode = new ToyStateModeView({state: state});
    });

    describe(".render", function() {
      it("should append the mode to the state", function() {
        assert(noElExists(state.$('.mode')));
        mode.render();
        assert(oneElExists(state.$('.mode')));
      });

      it("should render its template", function() {
        assert.equal(mode.$el.html(), '');
        mode.render();
        assert.equal(mode.$el.html(), 'toy mode');
      });
    });
  });

  describe(".DialogueStateView", function() {
    var ToyStateModel = dialogue.testHelpers.ToyStateModel,
        ToyStateView = dialogue.testHelpers.ToyStateView;

    var state;

    beforeEach(function() {
      var model = new ToyStateModel({
        uuid: 'luke-the-state',
        name: 'Toy Message 1',
        type: 'toy',
        entry_endpoint: {uuid: 'lukes-entry-endpoint'},
        exit_endpoint: {uuid: 'lukes-exit-endpoint'}
      });

      state = diagram.states.add('states', {
        model: model,
        position: {top: 0, left: 0}
      }, {render: false});
    });

    describe(".render", function() {
      it("should append the state to the diagram", function() {
        assert(noElExists(diagram.$('#luke-the-state')));
        state.render();
        assert(oneElExists(diagram.$('#luke-the-state')));
      });

      it("should render the currently active mode", function() {
        assert(noElExists(state.$('.mode')));
        state.render();
        assert(oneElExists(diagram.$('.mode')));
      });

      it("should render its endpoints", function() {
        assert(noElExists(state.$('#lukes-entry-endpoint')));
        assert(noElExists(state.$('#lukes-exit-endpoint')));
        state.render();
        assert(oneElExists(state.$('#lukes-entry-endpoint')));
        assert(oneElExists(state.$('#lukes-exit-endpoint')));
      });
    });

    describe(".preview", function() {
      beforeEach(function() {
        state.render();
      });

      it("should destroy the currently active mode view", function() {
        assert(oneElExists(state.$('.edit.mode')));
        state.preview();
        assert(noElExists(state.$('.edit.mode')));
      });

      it("should switch from the currently active mode to the preview mode",
      function() {
        assert.notEqual(state.mode, state.previewMode);
        state.preview();
        assert.equal(state.mode, state.previewMode);
      });

      it("should render the new mode", function() {
        assert(noElExists(state.$('.preview.mode')));
        state.preview();
        assert(oneElExists(diagram.$('.preview.mode')));
      });
    });

    describe(".preview", function() {
      beforeEach(function() {
        state.mode = state.previewMode;
        state.render();
      });

      it("should destroy the currently active mode view", function() {
        assert(oneElExists(state.$('.preview.mode')));
        state.edit();
        assert(noElExists(state.$('.preview.mode')));
      });

      it("should switch from the currently active mode to the edit mode",
      function() {
        assert.notEqual(state.mode, state.editMode);
        state.edit();
        assert.equal(state.mode, state.editMode);
      });

      it("should render the new mode", function() {
        assert(noElExists(state.$('.edit.mode')));
        state.edit();
        assert(oneElExists(diagram.$('.edit.mode')));
      });
    });
  });
});
