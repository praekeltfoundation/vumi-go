// go.campaign.dialogue.states.choice
// ==================================
// Structures for choice states (states where users enter any text they want)

(function(exports) {
  var states = go.campaign.dialogue.states,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var ChoiceStateEditView = DialogueStateEditView.extend({
    bodyTemplate: JST.campaign_dialogue_states_choice_edit,

    events: _({
      'click .new-choice': 'newChoice',
      'click .choice .remove': 'removeChoice'
    }).defaults(DialogueStateEditView.prototype.events),

    _save: function() {
      var model = this.state.model,
          choices = model.get('choice_endpoints');

      model.set('text', this.$('.text').val(), {silent: true});
      this.$('.choice').each(function() {
        var $choice = $(this);

        choices
          .get($choice.attr('data-endpoint-id'))
          .set('label', $choice.find('input').prop('value'), {silent: true});
      });
    },

    save: function(e) {
      e.preventDefault();
      this._save();
      this.state.preview();
    },

    newChoice: function(e) {
      e.preventDefault();
      this._save();

      this.state.endpoints.add(
        'choice_endpoints',
        {model: {uuid: uuid.v4()}});

      this.render();
    },

    removeChoice: function(e) {
      e.preventDefault();
      this._save();

      var $choice = $(e.target).parent();
      this.state.endpoints.remove($choice.attr('data-endpoint-id'));

      this.render();
    }
  });

  var ChoiceStatePreviewView = DialogueStatePreviewView.extend({
    bodyTemplate: JST.campaign_dialogue_states_choice_preview
  });

  var ChoiceStateView = DialogueStateView.extend({
    editModeType: ChoiceStateEditView,
    previewModeType: ChoiceStatePreviewView,
    endpointSchema: [
      {attr: 'entry_endpoint', side: 'left'},
      {attr: 'choice_endpoints', side: 'right'}]
  });

  _(exports).extend({
    ChoiceStateView: ChoiceStateView,

    ChoiceStateEditView: ChoiceStateEditView,
    ChoiceStatePreviewView: ChoiceStatePreviewView
  });
})(go.campaign.dialogue.states.choice = {});
