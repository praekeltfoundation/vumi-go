// go.campaign.dialogue.states.choice
// ==================================
// Structures for choice states (states where users enter any text they want)

(function(exports) {
  var states = go.campaign.dialogue.states,
      EntryEndpointView = states.EntryEndpointView,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var plumbing = go.components.plumbing,
      EndpointViewCollection = plumbing.endpoints.EndpointViewCollection,
      FollowingEndpointView = plumbing.endpoints.FollowingEndpointView;

  var ChoiceEndpointView = FollowingEndpointView.extend({
    className: 'choice endpoint',
    side: 'right',
    isTarget: false,
    target: function() {
      return '.choice[data-endpoint-id="' + this.uuid() + '"]';
    }
  });

  var ChoiceStateEditView = DialogueStateEditView.extend({
    events: _({
      'click .new-choice': 'onNewChoice',
      'click .choice .remove': 'onRemoveChoice',
      'change .choice input': 'onChoiceChange',
      'change .text': 'onTextChange'
    }).defaults(DialogueStateEditView.prototype.events),

    bodyOptions: function() {
      return {
        jst: 'JST.campaign_dialogue_states_choice_edit'
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
      return this;
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

    onChoiceChange: function(e) {
      var $choice = $(e.target).parent();

      this.state.model
        .get('choice_endpoints')
        .get($choice.attr('data-endpoint-id'))
        .set('label', $choice.find('input').prop('value'), {silent: true});
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
        jst: 'JST.campaign_dialogue_states_choice_preview'
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
