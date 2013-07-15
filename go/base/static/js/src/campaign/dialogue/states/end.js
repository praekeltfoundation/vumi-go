// go.campaign.dialogue.states.end
// ===============================
// Structures for end states (states which display something to the user and
// end the session)

(function(exports) {
  var states = go.campaign.dialogue.states,
      EntryEndpointView = states.EntryEndpointView,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView,
      TextEditView = states.partials.TextEditView;

  var EndStateEditView = DialogueStateEditView.extend({
    bodyOptions: function() {
      return {
        jst: 'JST.campaign_dialogue_states_end_edit',
        partials: {text: new TextEditView({mode: this})}
      };
    }
  });

  var EndStatePreviewView = DialogueStatePreviewView.extend({
    bodyOptions: function() {
      return {
        jst: 'JST.campaign_dialogue_states_end_preview'
      };
    }
  });

  var EndStateView = DialogueStateView.extend({
    typeName: 'end',

    editModeType: EndStateEditView,
    previewModeType: EndStatePreviewView,

    endpointSchema: [{attr: 'entry_endpoint', type: EntryEndpointView}]
  });

  _(exports).extend({
    EndStateView: EndStateView,

    EndStateEditView: EndStateEditView,
    EndStatePreviewView: EndStatePreviewView
  });
})(go.campaign.dialogue.states.end = {});
