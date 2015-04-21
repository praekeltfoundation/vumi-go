describe("go.apps.dialogue.states", function() {
  var testHelpers = go.testHelpers,
      oneElExists = testHelpers.oneElExists,
      noElExists = testHelpers.noElExists;

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

  describe(".NameEditExtrasView", function() {
    var state,
        extras;

    beforeEach(function() {
      state = diagram.states.get('state1');
      state.edit();

     extras = state.modes.edit.nameExtras;
     extras.show();
    });

    describe("when '.store-as' has changed", function() {
      it("should update the state model's 'store_as' attribute", function() {
        assert.equal(state.model.get('store_as'), 'message-1');

        extras.$('.store-as')
          .val("I'm a computer")
          .change();

        assert.equal(state.model.get('store_as'), "im-a-computer");
      });
    });

    describe("when '.ok' is clicked", function() {
      it("should hide the popover", function(done) {
        extras.on('hide', function() { done(); });
        extras.$('.ok').click();
      });
    });

    describe("when '.cancel' is clicked", function() {
      it("should hide the popover", function(done) {
        extras.on('hide', function() { done(); });
        extras.$('.cancel').click();
      });

      it("reset the state's 'store_as' attribute to its original value",
      function() {
        state.model.set('store_as', 'A computer');
        extras.$('.cancel').click();
        assert.equal(state.model.get('store_as'), 'message-1');
      });
    });
  });

  describe(".DialogueStateModeView", function() {
    var DialogueStateModeView = dialogue.states.DialogueStateModeView;

    var ToyStateModeView = DialogueStateModeView.extend({
      className: 'toy mode',

      jst: _.template('<%= partials.body %>'),
      bodyOptions: {
        jst: _.template("toy mode: <%= model.get('name') %>")
      }
    });

    var state,
        mode;

    beforeEach(function() {
      state = diagram.states.get('state4');
      mode = new ToyStateModeView({state: state});
    });

    describe(".render", function() {
      it("should render its templates", function() {
        assert.equal(mode.$el.html(), '');
        mode.render();

        assert.equal(
          mode.$el.html(),
          '<div>toy mode: Dummy Message 1</div>');
      });
    });
  });

  describe(".DialogueStateEditView", function() {
    var state,
        editMode;

    beforeEach(function() {
      state = diagram.states.get('state4');
      editMode = state.modes.edit;
      state.edit();
    });

    describe("on 'activate'", function() {
      it("should keep a backup of the state's model's attributes",
      function(done) {
        var newData;
        var oldData;

        editMode.on('activate', function() {
          assert.deepEqual(editMode.modelBackup, newData);
          assert.notDeepEqual(editMode.modelBackup, oldData);
          done();
        });

        oldData = state.model.toJSON();
        state.model.set('name', 'New Dummy');
        newData = state.model.toJSON();
        editMode.trigger('activate');
      });
    });

    describe(".cancel", function() {
      it("should change the model back to its old state", function() {
        var newData;
        var oldData;

        oldData = state.model.toJSON();
        state.model.set('name', 'New Dummy');
        newData = state.model.toJSON();

        editMode.cancel();
        assert.deepEqual(state.model.toJSON(), oldData);
        assert.notDeepEqual(state.model.toJSON(), newData);
      });
    });

    describe("when the the state's '.type' is changed", function() {
      var i;

      beforeEach(function() {
        // Use 'state1' (the choice state), since the dummy state isn't an
        // option in '.type'
        state = diagram.states.get('state1');
        editMode = state.modes.edit;
        state.edit();

        i = 0;
        sinon.stub(uuid, 'v4', function() { return i++ || 'new-state'; });

        editMode.resetModal.animate(false);
      });

      afterEach(function() {
        uuid.v4.restore();
        editMode.resetModal.remove();
      });

      it("should display a modal to confirm the user's decision", function() {
        assert(noElExists('.modal'));
        editMode.$('.type')
          .val('freetext')
          .change();
        assert(oneElExists('.modal'));
      });

      it("should replace the state with another if the user confirms the reset",
      function() {
        assert(diagram.states.has('state1'));
        assert.isDefined(diagram.model.get('states').get('state1'));

        assert(!diagram.states.has('new-state'));
        assert.isUndefined(diagram.model.get('states').get('new-state'));

        editMode.$('.type').val('freetext').change();
        $('.modal .ok').click();

        assert(diagram.states.has('new-state'));
        assert.isDefined(diagram.model.get('states').get('new-state'));

        assert(!diagram.states.has('state1'));
        assert.isUndefined(diagram.model.get('states').get('state1'));
      });

      it("should revert '.type's selection if the user cancels the reset",
      function() {
        assert.equal(editMode.$('.type').val(), 'choice');
        editMode.$('.type').val('freetext').change();
        $('.modal .cancel').click();
        assert.equal(editMode.$('.type').val(), 'choice');
      });

      it("should keep the current state if the user cancels the reset",
      function() {
        assert(diagram.states.has('state1'));
        assert.isDefined(diagram.model.get('states').get('state1'));

        assert(!diagram.states.has('new-state'));
        assert.isUndefined(diagram.model.get('states').get('new-state'));

        editMode.$('.type').val('freetext').change();
        $('.modal .cancel').click();

        assert(diagram.states.has('state1'));
        assert.isDefined(diagram.model.get('states').get('state1'));

        assert(!diagram.states.has('new-state'));
        assert.isUndefined(diagram.model.get('states').get('new-state'));
      });
    });

    describe("when '.name' has changed", function() {
      it("should update the 'name' attribute of the state's model",
      function() {
        assert.equal(state.model.get('name'), 'Dummy Message 1');
        state.$('.name').val('New Dummy').change();
        assert.equal(state.model.get('name'), 'New Dummy');
      });
    });

    describe("when the '.cancel' button is clicked", function() {
      it("should change the model back to its old state", function() {
        var newData;
        var oldData;

        oldData = state.model.toJSON();
        state.model.set('name', 'New Dummy');
        newData = state.model.toJSON();
        editMode.$('.cancel').click();

        editMode.cancel();
        assert.deepEqual(state.model.toJSON(), oldData);
        assert.notDeepEqual(state.model.toJSON(), newData);
      });

      it("should switch back to the preview view", function() {
        assert.equal(state.modeName, 'edit');
        editMode.$('.cancel').click();
        assert.equal(state.modeName, 'preview');
      });
    });

    describe("when the '.ok' button is clicked", function() {
      it("should switch back to the preview view", function() {
        assert.equal(state.modeName, 'edit');
        editMode.$('.ok').click();
        assert.equal(state.modeName, 'preview');
      });
    });
  });

  describe(".DialogueStatePreviewView", function() {
    var state,
        previewMode;

    beforeEach(function() {
      state = diagram.states.get('state4');
      previewMode = state.modes.preview;
      state.preview();
    });

    describe("when the '.edit-switch' button is clicked", function() {
      it("should update switch the state to edit mode", function() {
        assert.equal(state.modeName, 'preview');
        previewMode.$('.edit-switch').click();
        assert.equal(state.modeName, 'edit');
      });
    });
  });

  describe(".DialogueStateView", function() {
    var state;

    beforeEach(function() {
      state = diagram.states.get('state4');
    });

    describe(".render", function() {
      it("should render the currently active mode", function() {
        assert(noElExists(state.$('.mode')));
        state.render();
        assert(oneElExists(state.$('.mode')));
      });

      it("should render its endpoints", function() {
        assert(noElExists(state.$('[data-uuid="endpoint6"]')));
        assert(noElExists(state.$('[data-uuid="endpoint7"]')));
        state.render();
        assert(oneElExists(state.$('[data-uuid="endpoint6"]')));
        assert(oneElExists(state.$('[data-uuid="endpoint7"]')));
      });
    });

    describe(".preview", function() {
      beforeEach(function() {
        state.mode = state.modes.edit;
        state.render();
      });

      it("should destroy the currently active mode view", function() {
        assert(oneElExists(state.$('.edit.mode')));
        state.preview();
        assert(noElExists(state.$('.edit.mode')));
      });

      it("should switch from the currently active mode to the preview mode",
      function() {
        assert.notEqual(state.mode, state.modes.preview);
        state.preview();
        assert.equal(state.mode, state.modes.preview);
      });

      it("should render the new mode", function() {
        assert(noElExists(state.$('.preview.mode')));
        state.preview();
        assert(oneElExists(state.$('.preview.mode')));
      });
    });

    describe(".edit", function() {
      beforeEach(function() {
        state.mode = state.modes.preview;
        state.render();
      });

      it("should destroy the currently active mode view", function() {
        assert(oneElExists(state.$('.preview.mode')));
        state.edit();
        assert(noElExists(state.$('.preview.mode')));
      });

      it("should switch from the currently active mode to the edit mode",
      function() {
        assert.notEqual(state.mode, state.modes.edit);
        state.edit();
        assert.equal(state.mode, state.modes.edit);
      });

      it("should render the new mode", function() {
        assert(noElExists(state.$('.edit.mode')));
        state.edit();
        assert(oneElExists(state.$('.edit.mode')));
      });
    });

    describe("when the '.titlebar .remove' button is clicked", function() {
      beforeEach(function() {
        state.render();
      });

      it("should remove the state", function() {
        assert(diagram.states.has('state4'));
        state.$('.titlebar .remove').click();
        assert(!diagram.states.has('state4'));
      });

      it("should remove the state's model", function() {
        assert.isDefined(diagram.model.get('states').get('state4'));
        state.$('.titlebar .remove').click();
        assert.isUndefined(diagram.model.get('states').get('state4'));
      });
    });
  });

  describe(".DialogueStateCollection", function() {
    var DummyStateView = dialogue.states.dummy.DummyStateView;

    var states;

    beforeEach(function() {
      states = diagram.states.members.get('states');
    });

    describe(".reset", function() {
      it("should remove the old state", function(){
        assert(states.has('state3'));
        states.reset(states.get('state3'), 'dummy');
        assert(!states.has('state3'));
      });

      it("should add a new state at the same position as the old state",
      function(done){
        var old = states.get('state3');

        old.model.get('layout').set({
          x: 23,
          y: 21
        });

        states.on('add', function(id, state) {
          assert(state instanceof DummyStateView);
          assert.deepEqual(state.model.get('layout').coords(), {
            x: 23,
            y: 21
          });

          done();
        });

        states.reset(old, 'dummy');
      });
    });

    describe(".render", function() {
      it("should render its states", function() {
        var state = states.get('state4');
        assert.equal(state.$('.main').text().trim(), '');

        states.render();

        assert.equal(
          state.$('.main').text().trim(),
          'dummy preview mode: Dummy Message 1');
      });

      it("should append its state elements to the diagram element", function() {
        assert(noElExists(diagram.$('[data-uuid="state4"]')));
        states.render();
        assert(oneElExists(diagram.$('[data-uuid="state4"]')));
      });

      it("should render the layout", function() {
        var state = states.get('state4');

        state.model.get('layout').set({
          x: 40,
          y: 40
        });

        assert.notDeepEqual(state.$el.offset(), states.layout.offsetOf({
          x: 40,
          y: 40
        }));

        states.render();

        assert.deepEqual(state.$el.offset(), states.layout.offsetOf({
          x: 40,
          y: 40
        }));
      });
    });
  });
});
