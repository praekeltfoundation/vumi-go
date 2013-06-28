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
           '<div class="box">head body tail</div>'].join(''));
      });
    });
  });

  describe(".DialogueStateEditView", function() {
    var DialogueStateEditView = states.DialogueStateEditView;

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
            ordinal: 0
          });

          done();
        });

        assert.deepEqual(editMode.modelBackup, {
          uuid: 'state4',
          name: 'Dummy Message 1',
          type: 'dummy',
          entry_endpoint: {'uuid':'endpoint6'},
          exit_endpoint: {'uuid':'endpoint7'},
          ordinal: 0
        });

        state.model.set('name', 'New Dummy');
        editMode.trigger('activate');
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
          ordinal: 0
        });

        state.model.set('name', 'New Dummy');
        editMode.$('.cancel').click();

        assert.deepEqual(state.model.toJSON(), {
          uuid: 'state4',
          name: 'Dummy Message 1',
          type: 'dummy',
          entry_endpoint: {'uuid':'endpoint6'},
          exit_endpoint: {'uuid':'endpoint7'},
          ordinal: 0
        });
      });
    });
  });

  describe(".DialogueStateView", function() {
    var DummyStateModel = dialogue.models.DummyStateModel;

    var state;

    beforeEach(function() {
      var model = new DummyStateModel({
        uuid: 'luke-the-state',
        name: 'Dummy Message 1',
        type: 'dummy',
        entry_endpoint: {uuid: 'lukes-entry-endpoint'},
        exit_endpoint: {uuid: 'lukes-exit-endpoint'}
      });

      state = diagram.states.add('states', {
        model: model,
        position: {top: 0, left: 0}
      }, {render: false, silent: true});
    });

    describe(".render", function() {
      it("should render the currently active mode", function() {
        assert(noElExists(state.$('.mode')));
        state.render();
        assert(oneElExists(state.$('.mode')));
      });

      it("should render its endpoints", function() {
        assert(noElExists(state.$('[data-uuid="lukes-entry-endpoint"]')));
        assert(noElExists(state.$('[data-uuid="lukes-exit-endpoint"]')));
        state.render();
        assert(oneElExists(state.$('[data-uuid="lukes-entry-endpoint"]')));
        assert(oneElExists(state.$('[data-uuid="lukes-exit-endpoint"]')));
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
  });

  describe(".DialogueStateCollection", function() {
    var DummyStateView = dialogue.states.dummy.DummyStateView,
        DialogueStateCollection = states.DialogueStateCollection;

    var collection;

    beforeEach(function() {
      collection = new DialogueStateCollection({
        view: diagram,
        attr: 'states'
      });
    });

    describe(".reset", function() {
      it("should remove the old state", function(){
        assert(collection.has('state3'));
        collection.reset(collection.get('state3'), 'dummy');
        assert(!collection.has('state3'));
      });

      it("should add a new state at the same position as the old state",
      function(done){
        var old = collection.get('state3');

        collection.on('add', function(id, state) {
          assert(state instanceof DummyStateView);
          assert.equal(state.model.get('ordinal'), 3);
          done();
        });

        old.model.set('ordinal', 3);
        collection.reset(old, 'dummy');
      });
    });
  });
});
