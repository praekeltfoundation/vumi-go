// go.campaign.dialogue.states.choice
// ==================================
// Structures for choice states (states where users enter any text they want)

(function(exports) {
  var states = go.campaign.dialogue.states,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var ChoiceStateEditView = DialogueStateEditView.extend({
    template: JST.campaign_dialogue_states_choice_edit
  });

  var ChoiceStatePreviewView = DialogueStatePreviewView.extend({
    template: JST.campaign_dialogue_states_choice_preview
  });

  var ChoiceStateView = DialogueStateView.extend({
    editorType: ChoiceStateEditView,
    previewerType: ChoiceStatePreviewView,

    endpointSchema: [{attr: 'entry_endpoint'}]
  });

  _(exports).extend({
    ChoiceStateView: ChoiceStateView,

    ChoiceStateEditView: ChoiceStateEditView,
    ChoiceStatePreviewView: ChoiceStatePreviewView
  });
})(go.campaign.dialogue.states.choice = {});
