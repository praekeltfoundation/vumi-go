// go.campaign.dialogue.states.choice
// ==================================
// Structures for choice states (states where users enter any text they want)

(function(exports) {
  var TemplateView = go.components.views.TemplateView,
      UniqueView = go.components.views.UniqueView,
      PopoverView = go.components.views.PopoverView;

  var ViewCollection = go.components.structures.ViewCollection;

  var states = go.campaign.dialogue.states,
      EntryEndpointView = states.EntryEndpointView,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView,
      TextEditView = states.partials.TextEditView;

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
    popoverOptions: {container: 'body'},

    target: function() { return this.choice.$('.extras'); },

    events: {
      'click .ok': 'onOkClick',
      'click .cancel': 'onCancelClick',
      'change .value': 'onValueChange'
    },

    initialize: function(options) {
      ChoiceEditExtrasView.__super__.initialize.call(this, options);
      this.choice = options.choice;

      this.template = new TemplateView({
        el: this.$el,
        jst: 'JST.campaign_dialogue_states_choice_choice_extras',
        data: {model: this.choice.model}
      });

      this.valueBackup = null;
      this.on('show', function() {
        this.valueBackup = this.choice.model.get('value');
        this.delegateEvents();
      }, this);
    },

    onValueChange: function(e) {
      this.choice.model.set('value', go.utils.slugify(this.$('.value').val()));
    },

    onCancelClick: function(e) {
      e.preventDefault();
      this.choice.model.set('value', this.valueBackup);
      this.hide();
    },

    onOkClick: function(e) {
      this.hide();
    },

    render: function() {
      this.template.render();
      this.$('.info').tooltip();
      return this;
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
        jst: 'JST.campaign_dialogue_states_choice_choice_edit',
        data: {model: this.model}
      });

      this.extras = new ChoiceEditExtrasView({choice: this});
    },

    onLabelChange: function(e) {
      this.model.set(
        'label',
        this.$('.choice-label').prop('value'),
        {silent: true});
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
    events: _({
      'click .new-choice': 'onNewChoice'
    }).defaults(DialogueStateEditView.prototype.events),

    bodyOptions: function() {
      return {
        jst: 'JST.campaign_dialogue_states_choice_edit',
        partials: {
          text: new TextEditView({mode: this}),
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
      return {jst: 'JST.campaign_dialogue_states_choice_preview'};
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
    }]
  });

  _(exports).extend({
    ChoiceStateView: ChoiceStateView,

    ChoiceStateEditView: ChoiceStateEditView,
    ChoiceStatePreviewView: ChoiceStatePreviewView,
    ChoiceEndpointView: ChoiceEndpointView,

    ChoiceEditView: ChoiceEditView,
    ChoiceEditExtrasView: ChoiceEditExtrasView
  });
})(go.campaign.dialogue.states.choice = {});
