// go.campaign.dialogue.states.freetext
// ====================================
// Structures for freetext states (states where users enter any text they want)

(function(exports) {
  var states = go.campaign.dialogue.states,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var FreeTextStateEditView = DialogueStateEditView.extend({
    template: JST.campaign_dialogue_states_freetext_edit
  });

  var FreeTextStatePreviewView = DialogueStatePreviewView.extend({
    template: JST.campaign_dialogue_states_freetext_preview
  });

  var FreeTextStateView = DialogueStateView.extend({
    editorType: FreeTextStateEditView,
    previewerType: FreeTextStatePreviewView
  });

  _(exports).extend({
    FreeTextStateView: FreeTextStateView,

    FreeTextStateEditView: FreeTextStateEditView,
    FreeTextStatePreviewView: FreeTextStatePreviewView
  });
})(go.campaign.dialogue.states.freetext = {});
