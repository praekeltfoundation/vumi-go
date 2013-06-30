// go.campaign.dialogue.states.freetext
// ====================================
// Structures for freetext states (states where users enter any text they want)

(function(exports) {
  var states = go.campaign.dialogue.states,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var FreeTextStateEditView = DialogueStateEditView.extend({
    bodyTemplate: 'JST.campaign_dialogue_states_freetext_edit',

    save: function() {
      this.state.model.set('text', this.$('.text').val(), {silent: true});
      return this;
    }
  });

  var FreeTextStatePreviewView = DialogueStatePreviewView.extend({
    bodyTemplate: 'JST.campaign_dialogue_states_freetext_preview'
  });

  var FreeTextStateView = DialogueStateView.extend({
    typeName: 'freetext',

    editModeType: FreeTextStateEditView,
    previewModeType: FreeTextStatePreviewView,

    endpointSchema: [
      {attr: 'entry_endpoint'},
      {attr: 'exit_endpoint'}]
  });

  _(exports).extend({
    FreeTextStateView: FreeTextStateView,

    FreeTextStateEditView: FreeTextStateEditView,
    FreeTextStatePreviewView: FreeTextStatePreviewView
  });
})(go.campaign.dialogue.states.freetext = {});
