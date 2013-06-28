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
    headTemplate: _.template(''),
    template: _.template(''),
    tailTemplate: _.template(''),
    templateData: {},

    initialize: function(options) {
      this.state = options.state;
    },

    destroy: function() {
      this.$el.remove();
      return this;
    },

    detach: function() {
      this.$el.detach();
      return this;
    },

    render: function() {
      var data = {model: this.state.model.toJSON()};
      _(data).defaults(_(this).result('templateData'));

      this.state.$el.append(this.$el);

      this.$el.html([
         this.headTemplate(data),
         this.template(data),
         this.tailTemplate(data)
      ].join(''));

      return this;
    }
  });

  // Mode allowing the user to make changes to the dialogue state. Acts as a
  // base for each state type's `edit` mode
  var DialogueStateEditView = DialogueStateModeView.extend({
    className: 'edit mode',

    headTemplate: JST.campaign_dialogue_states_modes_edit_head,
    tailTemplate: JST.campaign_dialogue_states_modes_edit_tail,

    events: {
      'click .save': 'save',
      'click .cancel': 'cancel'
    },

    initialize: function(options) {
      DialogueStateEditView.__super__.initialize.call(this, options);
      this.backupModel();

      this.on('activate', this.backupModel, this);
    },

    // Keep a backup to restore the model for when the user cancels the edit
    backupModel: function() {
      this.modelBackup = this.state.model.toJSON();
    },

    // Override with custom saving functionality
    save: function(e) { e.preventDefault(); },

    cancel: function(e) {
      e.preventDefault();

      var model = this.state.model;
      model.clear();
      model.set(this.modelBackup);

      this.state.preview();
    }
  });

  // Mode for a 'read-only' preview of the dialogue state. Acts as a base for
  // each state type's `preview` mode
  var DialogueStatePreviewView = DialogueStateModeView.extend({
    className: 'preview mode'
  });

  // Base view for dialogue states. Dynamically switches between modes
  // (`edit`, `preview`).
  var DialogueStateView = StateView.extend({
    switchModeDefaults: {render: true, silent: false},

    className: 'state span4',

    editModeType: DialogueStateEditView,
    previewModeType: DialogueStatePreviewView,

    endpointType: ParametricEndpointView,
    endpointCollectionType: AligningEndpointCollection,

    subtypes: {
      dummy: 'go.campaign.dialogue.states.dummy.DummyStateView',
      choice: 'go.campaign.dialogue.states.choice.ChoiceStateView',
      freetext: 'go.campaign.dialogue.states.freetext.FreeTextStateView',
      end: 'go.campaign.dialogue.states.end.EndStateView'
    },

    headerTemplate: JST.campaign_dialogue_states_header,

    events: {
      'click .edit-switch': function(e) {
        e.preventDefault();
        this.edit();
      }
    },

    initialize: function(options) {
      StateView.prototype.initialize.call(this, options);

      this.$header = $('<div><div>').addClass('header');
      this.modes = {
        edit: new this.editModeType({state: this}),
        preview: new this.previewModeType({state: this})
      };

      this.switchMode(options.mode || 'preview', {render: false});
    },

    // 'Resets' a state to a new type by removing the current state, and
    // replacing it with a new state in the same position
    reset: function(type) {
      // TODO warn the user of the destruction involved
      this.collection.reset(this, type);
    },

    switchMode: function(modeName, options) {
      options = _(options || {}).defaults(this.switchModeDefaults);
      var mode = this.modes[modeName] || this.modes.preview;

      if (this.mode) {
        if (!options.silent) { this.mode.trigger('deactivate'); }
        this.mode.detach();
      }

      this.mode = mode;
      this.modeName = modeName;

      if (!options.silent) { this.mode.trigger('activate'); }
      if (options.render) { this.render(); }
      return this;
    },

    preview: function(options) {
      return this.switchMode('preview', options);
    },

    edit: function(options) {
      return this.switchMode('edit', options);
    },

    render: function() {
      this.$header.html(this.headerTemplate({
        name: this.model.get('name'),
        mode: this.modeName
      }));
      this.$el.append(this.$header);

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

    viewOptions: function() {
      var opts = DialogueStateCollection.__super__.viewOptions.call(this);
      return _({mode: 'preview'}).defaults(opts);
    },

    // Removes a state and creates a new state of a different type in the same
    // position as the old state
    reset: function(state, type) {
      this.remove(state);

      this.add({
        mode: 'edit',
        model: {
          type: type,
          ordinal: state.model.get('ordinal')
        }
      });

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
