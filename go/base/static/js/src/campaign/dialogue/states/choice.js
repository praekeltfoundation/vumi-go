// go.campaign.dialogue.states.choice
// ==================================
// Structures for choice states (states where users enter any text they want)

(function(exports) {
  var TemplateView = go.components.views.TemplateView,
      UniqueView = go.components.views.UniqueView;

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
    target: function() { return '.choice[data-endpoint-id="' + this.uuid() + '"]'; }
  });

  // View for an individual choice/answer in a choice state
  var ChoiceView = UniqueView.extend({
    tagName: 'li',
    className: 'choice',
    uuid: function() { return 'uuid:' + this.model.get('uuid'); },
    attributes: function() {
      return {'data-endpoint-id': this.model.get('uuid')};
    }
  });

  var ChoiceEditView = ChoiceView.extend({
    events: {
      'change input': 'onLabelChange'
    },

    initialize: function() {
      this.template = new TemplateView({
        el: this.$el,
        jst: 'JST.campaign_dialogue_states_choice_choice_edit',
        data: {model: this.model}
      });
    },

    onLabelChange: function(e) {
      this.model.set('label', this.$('input').prop('value'), {silent: true});
    },

    render: function() {
      this.template.render();
      return this;
    }
  });

  var ChoicePreviewView = ChoiceView.extend({
    render: function() {
      this.$el.text(this.model.get('label'));
      return this;
    }
  });

  var ChoiceStateEditView = DialogueStateEditView.extend({
    events: _({
      'click .new-choice': 'onNewChoice',
      'click .choice .remove': 'onRemoveChoice',
    }).defaults(DialogueStateEditView.prototype.events),

    bodyOptions: function() {
      return {
        jst: 'JST.campaign_dialogue_states_choice_edit',
        partials: {
          text: new TextEditView({mode: this}),
          choices: new ViewCollection({
            type: ChoiceEditView,
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

    onRemoveChoice: function(e) {
      e.preventDefault();

      var $choice = $(e.target).parent();
      this.state.endpoints.remove($choice.attr('data-endpoint-id'));

      this.state.render();
      jsPlumb.repaintEverything();
    },

    newChoice: function() {
      return this.state.endpoints.add(
        'choice_endpoints',
        {model: {uuid: uuid.v4()}},
        {render: false});
    }
  });

  var ChoiceStatePreviewView = DialogueStatePreviewView.extend({
    bodyOptions: function() {
      return {
        jst: 'JST.campaign_dialogue_states_choice_preview',
        partials: {
          choices: new ViewCollection({
            type: ChoicePreviewView,
            models: this.state.model.get('choice_endpoints')
          })
        }
      };
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
      collectionType: EndpointViewCollection
    }]
  });

  _(exports).extend({
    ChoiceStateView: ChoiceStateView,

    ChoiceStateEditView: ChoiceStateEditView,
    ChoiceStatePreviewView: ChoiceStatePreviewView,
    ChoiceEndpointView: ChoiceEndpointView
  });
})(go.campaign.dialogue.states.choice = {});
