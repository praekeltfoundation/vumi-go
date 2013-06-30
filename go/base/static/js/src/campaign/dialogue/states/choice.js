// go.campaign.dialogue.states.choice
// ==================================
// Structures for choice states (states where users enter any text they want)

(function(exports) {
  var states = go.campaign.dialogue.states,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var plumbing = go.components.plumbing,
      EndpointViewCollection = plumbing.endpoints.EndpointViewCollection,
      FollowingEndpointView = plumbing.endpoints.FollowingEndpointView;

  var ChoiceEndpointView = FollowingEndpointView.extend({
    side: 'right',
    target: function() {
      return '.choice[data-endpoint-id="' + this.uuid() + '"]';
    }
  });

  var ChoiceStateEditView = DialogueStateEditView.extend({
    bodyTemplate: 'JST.campaign_dialogue_states_choice_edit',

    events: _({
      'click .new-choice': 'onNewChoice',
      'click .choice .remove': 'onRemoveChoice'
    }).defaults(DialogueStateEditView.prototype.events),

    initialize: function(options) {
      ChoiceStateEditView.__super__.initialize.call(this, options);
      this.on('activate', this.onActivate, this);
    },

    save: function() {
      var model = this.state.model,
          choices = model.get('choice_endpoints');

      model.set('text', this.$('.text').val(), {silent: true});
      this.$('.choice').each(function() {
        var $choice = $(this);

        choices
          .get($choice.attr('data-endpoint-id'))
          .set('label', $choice.find('input').prop('value'), {silent: true});
      });

      return this;
    },

    newChoice: function() {
      return this.state.endpoints.add(
        'choice_endpoints',
        {model: {uuid: uuid.v4()}},
        {render: false});
    },

    onActivate: function() {
      var choices = this.state.endpoints.members.get('choice_endpoints');
      if (!choices.size()) { this.state.newChoice(); }
    },

    onNewChoice: function(e) {
      e.preventDefault();
      this.save();
      this.newChoice();
      this.state.render();
      jsPlumb.repaintEverything();
    },

    onRemoveChoice: function(e) {
      e.preventDefault();
      this.save();

      var $choice = $(e.target).parent();
      this.state.endpoints.remove($choice.attr('data-endpoint-id'));

      this.state.render();
      jsPlumb.repaintEverything();
    }
  });

  var ChoiceStatePreviewView = DialogueStatePreviewView.extend({
    bodyTemplate: 'JST.campaign_dialogue_states_choice_preview'
  });

  var ChoiceStateView = DialogueStateView.extend({
    typeName: 'choice',

    editModeType: ChoiceStateEditView,
    previewModeType: ChoiceStatePreviewView,
    endpointSchema: [{
      attr: 'entry_endpoint',
      side: 'left'
    }, {
      attr: 'choice_endpoints',
      side: 'right',
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
