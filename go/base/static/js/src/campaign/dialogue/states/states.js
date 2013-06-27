// go.campaign.dialogue.states
// ===========================
// Structures for each dialogue state type

(function(exports) {
  var plumbing = go.components.plumbing;

  var states = plumbing.states,
      StateView = states.StateView,
      StateViewCollection = states.StateViewCollection;

  var endpoints = plumbing.endpoints,
      ParametricEndpointView = endpoints.ParametricEndpointView,
      AligningEndpointCollection = endpoints.AligningEndpointCollection;

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

    editModeType: DialogueStateEditView,
    previewModeType: DialogueStatePreviewView,

    endpointType: ParametricEndpointView,
    endpointCollectionType: AligningEndpointCollection,

    subtypes: {
      choice: 'go.campaign.dialogue.states.choice.ChoiceStateView',
      freetext: 'go.campaign.dialogue.states.freetext.FreeTextStateView',
      end: 'go.campaign.dialogue.states.end.EndStateView'
    },

    id: function() { return this.model.id; },

    initialize: function(options) {
      StateView.prototype.initialize.call(this, options);

      this.editMode = new this.editModeType({state: this});
      this.previewMode = new this.previewModeType({state: this});
      this.mode = this.editMode;
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
      this.mode = this.previewMode;
      this.render();
    },

    // Switch to edit mode
    edit: function() {
      this.mode.destroy();
      this.mode = this.editMode;
      this.render();
    },

    render: function() {
      this.mode.render();
      this.endpoints.render();
      return this;
    }
  });

  var DialogueStateCollection = StateViewCollection.extend({
    type: DialogueStateView,

    ordered: true,
    comparator: function(state) { return state.model.get('ordinal'); },

    arrangeable: true,
    arranger: function(state, ordinal) {
      state.model.set('ordinal', ordinal, {silent: true});
    },

    // Removes a state and creates a new state of a different type in the same
    // position as the old state
    reset: function(state, type) {
      this.remove(state);

      this.add({
        model: {
          type: type,
          ordinal: state.model.get('ordinal')
        }
      });

      return this;
    },

    // TODO We make this a no-op since the diagram's grid appends the states
    // dynamically. This makes it apparent that we should probably be appending
    // plumbing elements in a top down fashion (instead of bottom up). We need
    // to change this when there is time for such things.
    appendToView: function() { console.log('aaaaaaa'); }
  });

  _(exports).extend({
    DialogueStateModeView: DialogueStateModeView,
    DialogueStatePreviewView: DialogueStatePreviewView,
    DialogueStateEditView: DialogueStateEditView,

    DialogueStateView: DialogueStateView,
    DialogueStateCollection: DialogueStateCollection
  });
})(go.campaign.dialogue.states = {});
