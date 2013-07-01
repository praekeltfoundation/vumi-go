describe("go.campaign.dialogue.states", function() {
  var testHelpers = go.testHelpers,
      oneElExists = testHelpers.oneElExists,
      noElExists = testHelpers.noElExists,
      unregisterModels = testHelpers.unregisterModels;

  var dialogue = go.campaign.dialogue;

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
    var DialogueStateModeView = dialogue.states.DialogueStateModeView;

    var ToyStateModeView = DialogueStateModeView.extend({
      className: 'toy mode',

      titlebarTemplate: _.template('<%= mode %>'),
      headTemplate: _.template("head "),
      bodyTemplate: _.template("body "),
      tailTemplate: _.template("tail"),
      templateData: {mode: 'toy'}
    });

    var state,
        mode;

    beforeEach(function() {
      state = diagram.states.get('state4');
      mode = new ToyStateModeView({state: state});
    });

    describe(".render", function() {
      it("should append the mode to the state", function() {
        assert(noElExists(state.$('.mode')));
        mode.render();
        assert(oneElExists(state.$('.mode')));
      });

      it("should render its templates", function() {
        assert.equal(mode.$el.html(), '');
        mode.render();
        assert.equal(
          mode.$el.html(),
          ['<div class="titlebar">toy</div>',
           '<div class="main">head body tail</div>'].join(''));
      });
    });
  });

  describe(".DialogueStateEditView", function() {
    var DialogueStateEditView = dialogue.states.DialogueStateEditView;

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
        editMode.on('activate', function() {
          assert.deepEqual(editMode.modelBackup, {
            uuid: 'state4',
            name: 'New Dummy',
            type: 'dummy',
            entry_endpoint: {'uuid':'endpoint6'},
            exit_endpoint: {'uuid':'endpoint7'},
            ordinal: 3
          });

          done();
        });

        assert.deepEqual(editMode.modelBackup, {
          uuid: 'state4',
          name: 'Dummy Message 1',
          type: 'dummy',
          entry_endpoint: {'uuid':'endpoint6'},
          exit_endpoint: {'uuid':'endpoint7'},
          ordinal: 3
        });

        state.model.set('name', 'New Dummy');
        editMode.trigger('activate');
      });
    });

    describe(".cancel", function() {
      it("should change the model back to its old state", function() {
        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state4',
          name: 'Dummy Message 1',
          type: 'dummy',
          entry_endpoint: {'uuid':'endpoint6'},
          exit_endpoint: {'uuid':'endpoint7'},
          ordinal: 3
        });

        state.model.set('name', 'New Dummy');
        editMode.cancel();

        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state4',
          name: 'Dummy Message 1',
          type: 'dummy',
          entry_endpoint: {'uuid':'endpoint6'},
          exit_endpoint: {'uuid':'endpoint7'},
          ordinal: 3
        });
      });
    });

    describe("when the the state's '.type' is changed", function() {
      var i;

      beforeEach(function() {
        i = 0;
        sinon.stub(uuid, 'v4', function() { return i++ || 'new-state'; });
      });

      afterEach(function() {
        uuid.v4.restore();
        $('.bootbox')
          .modal('hide')
          .remove();
      });

      it("should display a modal to confirm the user's decision", function() {
        bootbox.animate(false);

        assert(noElExists('.modal'));
        editMode.$('.type')
          .val('freetext')
          .change();
        assert(oneElExists('.modal'));
      });

      it("should replace the state with another if the user confirms the reset",
      function() {
        assert(diagram.states.has('state4'));
        assert.isDefined(diagram.model.get('states').get('state4'));

        assert(!diagram.states.has('new-state'));
        assert.isUndefined(diagram.model.get('states').get('new-state'));

        editMode.$('.type').val('freetext').change();
        $('.modal [data-handler=1]').click();

        assert(diagram.states.has('new-state'));
        assert.isDefined(diagram.model.get('states').get('new-state'));

        assert(!diagram.states.has('state4'));
        assert.isUndefined(diagram.model.get('states').get('state4'));
      });

      it("should revert '.type's selection if the user cancels the reset",
      function() {
        assert.equal(editMode.$('.type').val(), 'dummy');
        editMode.$('.type').val('freetext').change();
        $('.modal [data-handler=0]').click();
        assert.equal(editMode.$('.type').val(), 'dummy');
      });

      it("should keep the current state if the user cancels the reset",
      function() {
        assert(diagram.states.has('state4'));
        assert.isDefined(diagram.model.get('states').get('state4'));

        assert(!diagram.states.has('new-state'));
        assert.isUndefined(diagram.model.get('states').get('new-state'));

        editMode.$('.type').val('freetext').change();
        $('.modal [data-handler=0]').click();

        assert(diagram.states.has('state4'));
        assert.isDefined(diagram.model.get('states').get('state4'));

        assert(!diagram.states.has('new-state'));
        assert.isUndefined(diagram.model.get('states').get('new-state'));
      });
    });

    describe("when the '.save' button is clicked", function() {
      it("should update the 'name' attribute of the state's model",
      function() {
        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state4',
          name: 'Dummy Message 1',
          type: 'dummy',
          entry_endpoint: {'uuid':'endpoint6'},
          exit_endpoint: {'uuid':'endpoint7'},
          ordinal: 3
        });

        state.model.set('name', 'New Dummy');
        editMode.$('.save').click();

        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state4',
          name: 'New Dummy',
          type: 'dummy',
          entry_endpoint: {'uuid':'endpoint6'},
          exit_endpoint: {'uuid':'endpoint7'},
          ordinal: 3
        });
      });
    });

    describe("when the '.cancel' button is clicked", function() {
      it("should change the model back to its old state", function() {
        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state4',
          name: 'Dummy Message 1',
          type: 'dummy',
          entry_endpoint: {'uuid':'endpoint6'},
          exit_endpoint: {'uuid':'endpoint7'},
          ordinal: 3
        });

        state.model.set('name', 'New Dummy');
        editMode.$('.cancel').click();

        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state4',
          name: 'Dummy Message 1',
          type: 'dummy',
          entry_endpoint: {'uuid':'endpoint6'},
          exit_endpoint: {'uuid':'endpoint7'},
          ordinal: 3
        });
      });

      it("should switch back to the preview view", function() {
        assert.equal(state.modeName, 'edit');
        editMode.$('.cancel').click();
        assert.equal(state.modeName, 'preview');
      });
    });
  });

  describe(".DialogueStatePreviewView", function() {
    var DialogueStatePreviewView = dialogue.states.DialogueStatePreviewView;

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
    var DummyStateModel = dialogue.models.DummyStateModel;

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
    var DummyStateView = dialogue.states.dummy.DummyStateView,
        DialogueStateCollection = dialogue.states.DialogueStateCollection;

    var states;

    beforeEach(function() {
      states = diagram.states.members.get('states');
    });

    describe("when the user tries to drag a state", function() {
      beforeEach(function() {
        diagram.render();

        $('.bootbox')
          .modal('hide')
          .remove();

        $('.item').css({
          width: '100px',
          height: '100px',
          margin: '5px'
        });
      });

      it("should allow the state to be sorted if it isn't connected",
      function() {
        assert.deepEqual(
          states.keys(),
          ['state1','state2','state3','state4']);


        $('[data-uuid="state3"] .titlebar')
          .simulate('mousedown')
          .simulate('drag', {dx: 150});

        assert.deepEqual(
          states.keys(),
          ['state1','state2','state4','state3']);
      });

      it("should not let the state be sorted if it is connected", function() {
        assert.deepEqual(
          states.keys(),
          ['state1','state2','state3','state4']);

        $('[data-uuid="state1"] .titlebar').simulate('drag', {dx: 150});

        assert.deepEqual(
          states.keys(),
          ['state1','state2','state3','state4']);
      });

      it("should notify the user if they try move a connected state",
      function() {
        assert(noElExists('.modal'));
        $('[data-uuid="state1"] .titlebar').simulate('drag', {dx: 150});
        assert(oneElExists('.modal'));
      });
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

        states.on('add', function(id, state) {
          assert(state instanceof DummyStateView);
          assert.equal(state.model.get('ordinal'), 3);
          done();
        });

        old.model.set('ordinal', 3);
        states.reset(old, 'dummy');
      });
    });
  });
});
