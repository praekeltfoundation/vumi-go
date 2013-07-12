// go.campaign.dialogue.states.freetext
// ====================================
// Structures for freetext states (states where users enter any text they want)

(function(exports) {
  var states = go.campaign.dialogue.states,
      EntryEndpointView = states.EntryEndpointView,
      ExitEndpointView = states.ExitEndpointView,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView,
      TextEditView = states.partials.TextEditView;

  var FreeTextStateEditView = DialogueStateEditView.extend({
    bodyOptions: function() {
      return {
        jst: 'JST.campaign_dialogue_states_freetext_edit',
        partials: {text: new TextEditView({mode: this})}
      };
    }
  });

  var FreeTextStatePreviewView = DialogueStatePreviewView.extend({
    bodyOptions: function() {
      return {
        jst: 'JST.campaign_dialogue_states_freetext_preview'
      };
    }
  });

  var FreeTextStateView = DialogueStateView.extend({
    typeName: 'freetext',

    editModeType: FreeTextStateEditView,
    previewModeType: FreeTextStatePreviewView,

    endpointSchema: [
      {attr: 'entry_endpoint', type: EntryEndpointView},
      {attr: 'exit_endpoint', type: ExitEndpointView}]
  });

  _(exports).extend({
    FreeTextStateView: FreeTextStateView,

    FreeTextStateEditView: FreeTextStateEditView,
    FreeTextStatePreviewView: FreeTextStatePreviewView
  });
})(go.campaign.dialogue.states.freetext = {});
