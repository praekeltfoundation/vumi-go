// go.campaign.dialogue.states.end
// ===============================
// Structures for end states (states which display something to the user and
// end the session)

(function(exports) {
  var states = go.campaign.dialogue.states,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var EndStateEditView = DialogueStateEditView.extend({
    template: JST.campaign_dialogue_states_end_edit
  });

  var EndStatePreviewView = DialogueStatePreviewView.extend({
    template: JST.campaign_dialogue_states_end_preview
  });

  var EndStateView = DialogueStateView.extend({
    editorType: EndStateEditView,
    previewerType: EndStatePreviewView,

    endpointSchema: [
      {attr: 'entry_endpoint'},
      {attr: 'choice_endpoints'}]
  });

  _(exports).extend({
    EndStateView: EndStateView,

    EndStateEditView: EndStateEditView,
    EndStatePreviewView: EndStatePreviewView
  });
})(go.campaign.dialogue.states.end = {});
