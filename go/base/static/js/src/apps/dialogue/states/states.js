// go.apps.dialogue.states
// =======================
// Structures for each dialogue state type

(function(exports) {
  var ConfirmView = go.components.views.ConfirmView,
      PopoverView = go.components.views.PopoverView,
      TemplateView = go.components.views.TemplateView;

  var plumbing = go.components.plumbing;

  var states = plumbing.states,
      StateView = states.StateView,
      StateViewCollection = states.StateViewCollection;

  var endpoints = plumbing.endpoints,
      ParametricEndpointView = endpoints.ParametricEndpointView,
      AligningEndpointCollection = endpoints.AligningEndpointCollection;

  var DialogueEndpointView = ParametricEndpointView.extend();

  var EntryEndpointView = DialogueEndpointView.extend({
    side: 'left',
    isSource: false
  });

  var ExitEndpointView = DialogueEndpointView.extend({
    side: 'right',
    isTarget: false
  });

  var NameEditExtrasView = PopoverView.extend({
    className: 'extras-popover',

    bootstrapOptions: {container: 'body'},

    target: function() { return this.mode.$('.name-extras'); },

    events: {
      'click .ok': 'onOkClick',
      'click .cancel': 'onCancelClick',
      'change .store-as': 'onStoreAsChange'
    },

    initialize: function(options) {
      NameEditExtrasView.__super__.initialize.call(this, options);
      this.mode = options.mode;
      this.model = this.mode.state.model;

      this.template = new TemplateView({
        el: this.$el,
        jst: 'JST.apps_dialogue_states_components_nameExtras',
        data: {model: this.mode.state.model}
      });

      this.storeAsBackup = null;
      go.utils.bindEvents(this.bindings, this);
    },

    onStoreAsChange: function(e) {
      this.model.setStoreAs(this.$('.store-as').val());
      this.model.set('user_defined_store_as', true);
      return this;
    },

    onCancelClick: function(e) {
      e.preventDefault();
      this.model.set('store_as', this.storeAsBackup);
      this.hide();
    },

    onOkClick: function(e) {
      this.hide();
    },

    render: function() {
      this.template.render();
      return this;
    },

    bindings: {
      'show': function() {
        this.storeAsBackup = this.model.get('store_as');
        this.$('.info').tooltip();
      },

      'hide': function() {
        this.$('.info').tooltip('destroy');
      }
    }
  });

  // Base 'mode' for state views. Each mode acts as a 'delegate view',
  // targeting a dialogue view's element and acting according to the mode type
  // (for eg, `edit`) and state type (for eg, `freetext`).
  var DialogueStateModeView = TemplateView.extend({
    data: function() {
      return {
        mode: this,
        state: this.state,
        model: this.model
      };
    },

    bodyOptions: {},

    initialize: function(options) {
      DialogueStateModeView.__super__.initialize.call(this, options);
      this.state = options.state;
      this.model = this.state.model;

      this.partials.body = new TemplateView(
        _({data: this.data.bind(this)}).extend(
        _(this).result('bodyOptions')));
    },

    destroy: function() {
      this.$el.remove();
      return this;
    },

    detach: function() {
      this.$el.detach();
      return this;
    }
  });

  // Mode allowing the user to make changes to the dialogue state. Acts as a
  // base for each state type's `edit` mode
  var DialogueStateEditView = DialogueStateModeView.extend({
    jst: 'JST.apps_dialogue_states_modes_edit',

    className: 'edit mode',

    events: {
      'click .actions .ok': 'onOk',
      'click .actions .cancel': 'onCancel',
      'change .type': 'onTypeChange',
      'change .name': 'onNameChange',
      'click .name-extras': 'onNameExtras',
    },

    resetModal: new ConfirmView({
      optional: true,
      content: "Changing the message's type will break its connections " +
               "and reset its content."
    }),

    initialize: function(options) {
      DialogueStateEditView.__super__.initialize.call(this, options);
      this.backupModel();

      this.on('activate', this.backupModel, this);
      this.nameExtras = new NameEditExtrasView({mode: this});
    },

    onOk: function(e) {
      e.preventDefault();
      this.state.preview();
    },

    onCancel: function(e) {
      e.preventDefault();
      this.cancel();
      this.state.preview();
    },

    onTypeChange: function(e) {
      var $option = $(e.target);

      // Using `on` is okay, since the events are unbound when either of the
      // buttons are clicked. Simply using `once` won't work, since the event
      // for the unclicked button will remain bound.
      this.resetModal
        .on(
          'ok',
          function() { this.state.reset($option.val()); }, this)
        .on(
          'cancel',
          function() { this.$('.type').val(this.state.typeName); }, this)
        .show();
    },

    onNameChange: function(e) {
      this.model.set('name', $(e.target).val());
    },

    onNameExtras: function(e) {
      this.nameExtras.toggle();
    },

    // Keep a backup to restore the model for when the user cancels the edit
    backupModel: function() {
      this.modelBackup = this.model.toJSON();
      return this;
    },

    cancel: function() {
      var model = this.model;
      if (this.modelBackup) { model.set(this.modelBackup); }
      return this;
    },

    render: function() {
      DialogueStateEditView.__super__.render.call(this);
      this.$('.type').val(this.state.typeName);
      return this;
    }
  });

  // Mode for a 'read-only' preview of the dialogue state. Acts as a base for
  // each state type's `preview` mode
  var DialogueStatePreviewView = DialogueStateModeView.extend({
    jst: 'JST.apps_dialogue_states_modes_preview',

    className: 'preview mode',

    events: {
      'click .edit-switch': 'onEditSwitch'
    },

    onEditSwitch: function(e) {
      e.preventDefault();
      this.state.edit();
    }
  });

  // Base view for dialogue states. Dynamically switches between modes
  // (`edit`, `preview`).
  var DialogueStateView = StateView.extend({
    switchModeDefaults: {render: true, silent: false},

    className: function() {
      return ('state box item ' + (this.typeName || '')).trim();
    },

    editModeType: DialogueStateEditView,
    previewModeType: DialogueStatePreviewView,

    endpointType: DialogueEndpointView,
    endpointCollectionType: AligningEndpointCollection,

    subtypes: {
      dummy: 'go.apps.dialogue.states.dummy.DummyStateView',
      choice: 'go.apps.dialogue.states.choice.ChoiceStateView',
      freetext: 'go.apps.dialogue.states.freetext.FreeTextStateView',
      end: 'go.apps.dialogue.states.end.EndStateView',
      group: 'go.apps.dialogue.states.group.GroupStateView',
      send: 'go.apps.dialogue.states.send.SendStateView',
      httpjson: 'go.apps.dialogue.states.httpjson.HttpJsonStateView'
    },

    events: {
      'click .titlebar .remove': 'onRemove'
    },

    initialize: function(options) {
      StateView.prototype.initialize.call(this, options);

      if (!this.model.has('ordinal')) {
        this.model.set('ordinal', this.collection.size(), {silent: true});
      }

      this.modes = {
        edit: new this.editModeType({state: this}),
        preview: new this.previewModeType({state: this})
      };

      this.switchMode(options.mode || 'preview', {render: false});
    },

    onRemove: function(e) {
      e.preventDefault();
      this.collection.remove(this);
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
      if (options.render) {
        this.render();
        jsPlumb.repaintEverything();
      }
      return this;
    },

    preview: function(options) {
      return this.switchMode('preview', options);
    },

    edit: function(options) {
      return this.switchMode('edit', options);
    },

    render: function() {
      this.mode
        .render()
        .$el
        .appendTo(this.$el);

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

    defaultMode: 'preview',

    viewOptions: function() {
      var opts = DialogueStateCollection.__super__.viewOptions.call(this);
      return _({mode: this.defaultMode}).defaults(opts);
    },

    modelDefaults: function() {
      return {
        type: 'choice',
        name: '',
        ordinal: this.size()
      };
    },

    constructor: function(options) {
      DialogueStateCollection.__super__.constructor.call(this, options);

      if (!this.size()) {
        this.add();
        this.resetStartState();
      }

      // Change the default mode to edit once initialisation is done so new
      // states can be rendered in edit mode.
      this.defaultMode = 'edit';

      go.utils.bindEvents(this.bindings, this);
    },

    // Removes a state and creates a new state of a different type in the same
    // position as the old state
    reset: function(state, type) {
      this.remove(state);

      this.add({
        model: {
          type: type,
          name: state.model.get('name'),
          ordinal: state.model.get('ordinal')
        }
      });

      return this;
    },

    render: function() {
      this.each(function(s) {
        this.view.$el.append(s.$el);
        s.render();
      }, this);

      return this;
    },

    resetStartState: function() {
      var model = this.size()
        ? this.at(0).model
        : null;

      this.view.model.set('start_state', model);
      return this;
    },

    bindings: {
      // We need to reset the start state whenever a state is removed or
      // whenever the ordering of the states changes.
      'remove': function() {
        this.resetStartState();
        this.render();
        jsPlumb.repaintEverything();
      },
    }
  });

  _(exports).extend({
    EntryEndpointView: EntryEndpointView,
    ExitEndpointView: ExitEndpointView,

    DialogueStateModeView: DialogueStateModeView,
    DialogueStatePreviewView: DialogueStatePreviewView,
    DialogueStateEditView: DialogueStateEditView,

    DialogueStateView: DialogueStateView,
    DialogueStateCollection: DialogueStateCollection
  });
})(go.apps.dialogue.states = {});
