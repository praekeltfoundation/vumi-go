// go.apps.dialogue.states.choice
// ==============================
// Structures for choice states (states where users enter any text they want)

(function(exports) {
  var TemplateView = go.components.views.TemplateView,
      UniqueView = go.components.views.UniqueView,
      PopoverView = go.components.views.PopoverView;

  var ViewCollection = go.components.structures.ViewCollection;

  var states = go.apps.dialogue.states,
      EntryEndpointView = states.EntryEndpointView,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView,
      TextEditView = states.partials.TextEditView,
      maxChars = states.maxChars;

  var plumbing = go.components.plumbing,
      EndpointViewCollection = plumbing.endpoints.EndpointViewCollection,
      FollowingEndpointView = plumbing.endpoints.FollowingEndpointView;

  var ChoiceEndpointView = FollowingEndpointView.extend({
    className: 'choice endpoint',
    side: 'right',
    isTarget: false,
    target: function() { return '[data-uuid="choice:' + this.uuid() + '"]'; }
  });

  var ChoiceEndpointCollection = EndpointViewCollection.extend({
    type: ChoiceEndpointView,

    addDefaults: _({
      render: false
    }).defaults(EndpointViewCollection.prototype.addDefaults)
  });

  var ChoiceEditExtrasView = PopoverView.extend({
    className: 'extras-popover',

    bootstrapOptions: {container: 'body'},

    target: function() { return this.choice.$('.extras'); },

    events: {
      'click .ok': 'onOkClick',
      'click .cancel': 'onCancelClick',
      'change .value': 'onValueChange'
    },

    initialize: function(options) {
      ChoiceEditExtrasView.__super__.initialize.call(this, options);
      this.choice = options.choice;
      this.model = this.choice.model;

      this.template = new TemplateView({
        el: this.$el,
        jst: 'JST.apps_dialogue_states_choice_choice_extras',
        data: {model: this.choice.model}
      });

      this.valueBackup = null;
      go.utils.bindEvents(this.bindings, this);
    },

    onValueChange: function(e) {
      this.model.setValue(this.$('.value').val());
      this.model.set('user_defined_value', true);
    },

    onCancelClick: function(e) {
      e.preventDefault();
      this.model.set('value', this.valueBackup);
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
        this.valueBackup = this.model.get('value');
        this.$('.info').tooltip();
      },

      'hide': function() {
        this.$('.info').tooltip('destroy');
      }
    }
  });

  var ChoiceEditView = UniqueView.extend({
    tagName: 'li',
    className: 'choice',

    uuid: function() { return 'choice:' + this.model.get('uuid'); },

    events: {
      'change .choice-label': 'onLabelChange',
      'click .remove': 'onRemoveClick',
      'click .extras': 'onExtrasClick'
    },

    initialize: function(options) {
      this.mode = options.mode;

      this.template = new TemplateView({
        el: this.$el,
        jst: 'JST.apps_dialogue_states_choice_choice_edit',
        data: {model: this.model}
      });

      this.extras = new ChoiceEditExtrasView({choice: this});
    },

    onLabelChange: function(e) {
      this.model.set(
        'label',
        this.$('.choice-label').prop('value'));
      this.mode.render();
    },

    onRemoveClick: function(e) {
      e.preventDefault();

      this.mode.state.model
        .get('choice_endpoints')
        .remove(this.model);

      this.mode.state.render();
      jsPlumb.repaintEverything();
    },

    onExtrasClick: function(e) {
      this.extras.toggle();
    },

    render: function() {
      this.template.render();
      return this;
    }
  });

  var ChoiceEditCollection = ViewCollection.extend({
    type: ChoiceEditView,

    addDefaults: _({
      render: false
    }).defaults(ViewCollection.prototype.addDefaults),

    viewOptions: function() { return {mode: this.mode}; },

    initialize: function(options) {
      this.mode = options.mode;
    }
  });

  var ChoiceStateEditView = DialogueStateEditView.extend({
    maxChars: maxChars,
    events: _({
      'click .new-choice': 'onNewChoice',
      'change .text': 'onTextChange'
    }).defaults(DialogueStateEditView.prototype.events),

    bodyOptions: function() {
      return {
        jst: 'JST.apps_dialogue_states_choice_edit',
        partials: {
          choices: new ChoiceEditCollection({
            mode: this,
            models: this.state.model.get('choice_endpoints')
          })
        }
      };
    },

    initialize: function(options) {
      ChoiceStateEditView.__super__.initialize.call(this, options);
      this.on('activate', this.onActivate, this);
    },

    onActivate: function() {
      var choices = this.state.endpoints.members.get('choice_endpoints');

      if (!choices.size()) {
        this.newChoice();
        this.state.render();
      }
    },

    onTextChange: function(e) {
      this.state.model.set('text', $(e.target).val(), {silent: true});
      this.state.render();
    },

    // onChoiceChange: function(e) {
    // },

    onNewChoice: function(e) {
      e.preventDefault();
      this.newChoice();
      this.state.render();
      jsPlumb.repaintEverything();
    },

    newChoice: function() {
      this.state.model
        .get('choice_endpoints')
        .add({uuid: uuid.v4()});

      return this;
    }
  });

  var ChoiceStatePreviewView = DialogueStatePreviewView.extend({
    bodyOptions: function() {
      return {jst: 'JST.apps_dialogue_states_choice_preview'};
    }
  });

  var ChoiceStateView = DialogueStateView.extend({
    typeName: 'choice',

    editModeType: ChoiceStateEditView,
    previewModeType: ChoiceStatePreviewView,

    endpointSchema: [{
      attr: 'entry_endpoint',
      type: EntryEndpointView
    }, {
      attr: 'choice_endpoints',
      type: ChoiceEndpointView,
      collectionType: ChoiceEndpointCollection
    }],

      calcChars: function() {
      var numChars = this.model.get('choice_endpoints')
        .reduce(function(count, choice) {
          return ('N. ' + choice.get('label') + '\n').length + count;
        }, 0);

      // Remove the '\n' from the last choice_endpoint
      numChars--;
      numChars += this.model.get('text').length;
      return numChars;
    }
  });

  _(exports).extend({
    ChoiceStateView: ChoiceStateView,

    ChoiceStateEditView: ChoiceStateEditView,
    ChoiceStatePreviewView: ChoiceStatePreviewView,
    ChoiceEndpointView: ChoiceEndpointView,

    ChoiceEditView: ChoiceEditView,
    ChoiceEditExtrasView: ChoiceEditExtrasView
  });
})(go.apps.dialogue.states.choice = {});
