// go.campaign.dialogue.states
// ===========================
// Structures for each dialogue state type

(function(exports) {
  var maybeByName = go.utils.maybeByName,
      GridView = go.components.grid.GridView,
      ConfirmView = go.components.views.ConfirmView,
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

  // Base 'mode' for state views. Each mode acts as a 'delegate view',
  // targeting a dialogue view's element and acting according to the mode type
  // (for eg, `edit`) and state type (for eg, `freetext`).
  var DialogueStateModeView = TemplateView.extend({
    data: function() {
      return {
        mode: this,
        state: this.state,
        model: this.state.model
      };
    },

    bodyOptions: {},

    initialize: function(options) {
      DialogueStateModeView.__super__.initialize.call(this, options);
      this.state = options.state;

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
    jst: 'JST.campaign_dialogue_states_modes_edit',

    className: 'edit mode',

    events: {
      'click .ok': 'onOk',
      'click .cancel': 'onCancel',
      'change .type': 'onTypeChange',
      'change .name': 'onNameChange'
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
      this.state.model.set('name', $(e.target).val(), {silent: true});
      return this;
    },

    // Keep a backup to restore the model for when the user cancels the edit
    backupModel: function() {
      this.modelBackup = this.state.model.toJSON();
      return this;
    },

    cancel: function() {
      var model = this.state.model;
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
    jst: 'JST.campaign_dialogue_states_modes_preview',

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

    className: function() { return 'box item state ' + this.typeName || ''; },

    editModeType: DialogueStateEditView,
    previewModeType: DialogueStatePreviewView,

    endpointType: DialogueEndpointView,
    endpointCollectionType: AligningEndpointCollection,

    subtypes: {
      dummy: 'go.campaign.dialogue.states.dummy.DummyStateView',
      choice: 'go.campaign.dialogue.states.choice.ChoiceStateView',
      freetext: 'go.campaign.dialogue.states.freetext.FreeTextStateView',
      end: 'go.campaign.dialogue.states.end.EndStateView'
    },

    events: {
      'mousedown .titlebar': 'onTitlebarHold',
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

    onTitlebarHold: function(e) {
      if (this.isConnected()) { this.$el.addClass('locked'); }
      else { this.$el.removeClass('locked'); }
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

  var DialogueStateGridView = GridView.extend({
    className: 'grid container boxes',

    events: {
      'click .add': 'onAddClick'
    },

    sortableOptions: {
      items: '.item:not(.add-container)',
      cancel: '.locked,input',
      handle: '.titlebar',
      placeholder: 'placeholder',
      sort: function() { jsPlumb.repaintEverything(); },
      stop: function() { jsPlumb.repaintEverything(); }
    },

    initialize: function(options) {
      DialogueStateGridView.__super__.initialize.call(this, options);

      this.states = options.states;
      this.states.eachItem(
        function(id, state) { this.addState(id, state, {sort: false}); },
        this);
      this.items.sort();

      var $add = $('<button>')
        .addClass('add btn btn-primary')
        .text('+');

      var $addContainer = $('<div>')
        .addClass('item add-container')
        .append($add);

      this.add('add-btn', $addContainer, {index: Infinity});

      this.listenTo(this.states, 'add', this.addState);
      this.listenTo(this.states, 'remove', this.remove);
      this.on('reorder', this.onReorder, this);
    },

    onAddClick: function(e) {
      e.preventDefault();
      this.states.add();
    },

    onReorder: function(keys) {
      // The grid items have their indices reset when the user sorts the items
      // in the UI. We need to ensure the add button stays at the end, so we
      // need to change it back to `Infinity` each reorder
      this.items
        .get('add-btn')
        .data('grid:index', Infinity);

      // Remove the add button from the keys
      keys.pop();

      this.states.rearrange(keys);
    },

    addState: function(id, state, options) {
      options = _(options || {}).defaults({index: state.model.get('ordinal')});
      return this.add(id, state, options);
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
      this.grid = new DialogueStateGridView({states: this});

      // Change the default mode to edit once initialisation is done so new
      // states can be rendered in edit mode.
      this.defaultMode = 'edit';
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
      this.view.$el.append(this.grid.$el);
      this.grid.render();

      this.each(function(s) { s.render(); });
      return this;
    }
  });

  _(exports).extend({
    EntryEndpointView: EntryEndpointView,
    ExitEndpointView: ExitEndpointView,

    DialogueStateModeView: DialogueStateModeView,
    DialogueStatePreviewView: DialogueStatePreviewView,
    DialogueStateEditView: DialogueStateEditView,

    DialogueStateView: DialogueStateView,
    DialogueStateGridView: DialogueStateGridView,
    DialogueStateCollection: DialogueStateCollection
  });
})(go.campaign.dialogue.states = {});
