// go.campaign.dialogue.states
// ===========================
// Structures for each dialogue state type

(function(exports) {
  var plumbing = go.components.plumbing,
      StateView = plumbing.StateView,
      StateViewCollection = plumbing.StateViewCollection;

  // Base 'mode' for state views. Each mode acts as a 'delegate view',
  // targeting a dialogue view's element and acting according to the mode type
  // (for eg, `edit`) and state type (for eg, `freetext`).
  var DialogueStateModeView = Backbone.View.extend({
    template: _.template(''),

    // The data passed to the template
    templateData: function() { return {model: this.state.model.toJSON()}; },

    initialize: function(options) {
      this.state = options.state;
    },

    destroy: function() {
      this.$el.remove();
      return this;
    },

    render: function() {
      this.state.$el.append(this.$el);

      var data = _(this).result('templateData');
      this.$el.html(this.template(data));
      return this;
    }
  });

  // Mode allowing the user to make changes to the dialogue state. Acts as a
  // base for each state type's `edit` mode
  var DialogueStateEditView = DialogueStateModeView.extend({
    className: 'edit mode'
  });

  // Mode for a 'read-only' preview of the dialogue state. Acts as a base for
  // each state type's `preview` mode
  var DialogueStatePreviewView = DialogueStateModeView.extend({
    className: 'preview mode'
  });

  // Base view for dialogue states. Dynamically switches between modes
  // (`edit`, `preview`).
  var DialogueStateView = StateView.extend({
    className: 'state',

    editorType: DialogueStateEditView,
    previewerType: DialogueStatePreviewView,

    subtypes: {
      choice: 'go.campaign.dialogue.states.choice.ChoiceStateView',
      freetext: 'go.campaign.dialogue.states.freetext.FreeStateView',
      end: 'go.campaign.dialogue.states.end.EndStateView'
    },

    id: function() { return this.model.id; },

    initialize: function(options) {
      StateView.prototype.initialize.call(this, options);

      this.previewer = new this.previewerType({state: this});
      this.editor = new this.editorType({state: this});
      this.mode = this.editor;

      // If we weren't given a position, ask the grid for one. This case
      // happens when new states are fetched from the server.
      this.position = options.position || this.diagram.grid.nextPosition();
    },

    // 'Resets' a state to a new type by removing the current state, and
    // replacing it with a new state in the same position
    reset: function(type) {
      // TODO warn the user of the destruction involved
      this.collection.reset(this, type);
    },

    // Switch to preview mode
    preview: function() {
      this.mode.destroy();
      this.mode = this.previewer;
      this.render();
    },

    // Switch to edit mode
    edit: function() {
      this.mode.destroy();
      this.mode = this.editor;
      this.render();
    },

    render: function() {
      // TODO position the state
      this.diagram.$el.append(this.$el);
      this.mode.render();
      this.endpoints.render();
      return this;
    }
  });

  var DialogueStateCollection = StateViewCollection.extend({
    type: DialogueStateView,

    // Removes a state and creates a new state of a different type in the same
    // position as the old state
    reset: function(state, type) {
      this.remove(state);
      this.add({position: state.position, model: {type: type}});
      return this;
    }
  });

  _(exports).extend({
    DialogueStateModeView: DialogueStateModeView,
    DialogueStatePreviewView: DialogueStatePreviewView,
    DialogueStateEditView: DialogueStateEditView,

    DialogueStateView: DialogueStateView,
    DialogueStateCollection: DialogueStateCollection
  });
})(go.campaign.dialogue.states = {});
