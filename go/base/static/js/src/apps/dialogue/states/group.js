// go.apps.dialogue.states.group
// ================================
// Structures for group states: states that add the user to a group.

(function(exports) {
  var states = go.apps.dialogue.states,
      EntryEndpointView = states.EntryEndpointView,
      ExitEndpointView = states.ExitEndpointView,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var GroupStateEditView = DialogueStateEditView.extend({
    bodyOptions: function() {
      return {
        jst: 'JST.apps_dialogue_states_group_edit'
      };
    }
  });

  var GroupStatePreviewView = DialogueStatePreviewView.extend({
    bodyOptions: function() {
      return {
        jst: 'JST.apps_dialogue_states_group_preview'
      };
    }
  });

  var GroupStateView = DialogueStateView.extend({
    typeName: 'group',

    editModeType: GroupStateEditView,
    previewModeType: GroupStatePreviewView,

    endpointSchema: [
      {attr: 'entry_endpoint', type: EntryEndpointView},
      {attr: 'exit_endpoint', type: ExitEndpointView}]
  });

  _(exports).extend({
    GroupStateView: GroupStateView,

    GroupStateEditView: GroupStateEditView,
    GroupStatePreviewView: GroupStatePreviewView
  });
})(go.apps.dialogue.states.group = {});
