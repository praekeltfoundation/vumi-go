// go.campaign.dialogue.states
// ===========================
// Structures for each dialogue state type

(function(exports) {
  var maybeByName = go.utils.maybeByName;

  var GridView = go.components.grid.GridView;

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
  var DialogueStateModeView = Backbone.View.extend({
    titlebarTemplate: _.template(''),
    headTemplate: _.template(''),
    bodyTemplate: _.template(''),
    tailTemplate: _.template(''),
    templateData: {},

    initialize: function(options) {
      this.state = options.state;

      this.$titlebar = $('<div><div>').addClass('titlebar');
      this.$main = $('<div><div>').addClass('main');
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
      this.$el.append(this.$titlebar);
      this.$el.append(this.$main);

      this.$titlebar.html(maybeByName(this.titlebarTemplate)(data));

      this.$main.html([
         maybeByName(this.headTemplate)(data),
         maybeByName(this.bodyTemplate)(data),
         maybeByName(this.tailTemplate)(data)
      ].join(''));

      return this;
    }
  });

  // Mode allowing the user to make changes to the dialogue state. Acts as a
  // base for each state type's `edit` mode
  var DialogueStateEditView = DialogueStateModeView.extend({
    className: 'edit mode',

    titlebarTemplate: 'JST.campaign_dialogue_states_modes_edit_titlebar',
    headTemplate: 'JST.campaign_dialogue_states_modes_edit_head',
    tailTemplate: 'JST.campaign_dialogue_states_modes_edit_tail',

    events: {
      'click .ok': 'onOk',
      'click .cancel': 'onCancel',
      'change .type': 'onTypeChange',
      'change .name': 'onNameChange'
    },

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

      bootbox.confirm(
        "Changing the message's type will break its connections and reset " +
        "its content.", function(submit) {
          if (submit) { this.state.reset($option.val()); }
          else { this.$('.type').val(this.state.typeName); }
        }.bind(this));
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
    className: 'preview mode',
    titlebarTemplate: 'JST.campaign_dialogue_states_modes_preview_titlebar',

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
      this.mode.render();
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
      this.items
        .get('add-btn')
        .data('grid:index', Infinity);

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
