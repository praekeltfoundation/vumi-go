// go.apps.dialogue.states.send
// ============================
// Structures for send states: states that send a message the user over a
// different channel.

(function(exports) {
  var states = go.apps.dialogue.states,
      EntryEndpointView = states.EntryEndpointView,
      ExitEndpointView = states.ExitEndpointView,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var SendStateEditView = DialogueStateEditView.extend({
    data: function() {
      var type = this.model.get('channel_type');
      var d = SendStateEditView.__super__.data.call(this);

      d.typeName = null;
      if (type) { d.typeName = type.get('name'); }
      d.types = this.model.get('dialogue').get('channel_types');

      return d;
    },

    bodyOptions: function() {
      return {
        jst: 'JST.apps_dialogue_states_send_edit'
      };
    },

    events: _.extend({
      'change .channel-type': function(e) {
        var name = $(e.target).val();

        if (name === 'unassigned') {
          this.model.set('channel_type', null, {silent: true});
        } else if (name !== 'none') {
          this.model.set('channel_type', {name: name}, {silent: true});
        }

      }
    }, DialogueStateEditView.prototype.events)
  });

  var SendStatePreviewView = DialogueStatePreviewView.extend({
    data: function() {
      var type = this.model.get('channel_type');
      var d = SendStatePreviewView.__super__.data.call(this);

      d.typeLabel = null;
      if (type) { d.typeLabel = type.get('label'); }

      return d;
    },

    bodyOptions: function() {
      return {
        jst: 'JST.apps_dialogue_states_send_preview'
      };
    }
  });

  var SendStateView = DialogueStateView.extend({
    typeName: 'send',

    editModeType: SendStateEditView,
    previewModeType: SendStatePreviewView,

    endpointSchema: [
      {attr: 'entry_endpoint', type: EntryEndpointView},
      {attr: 'exit_endpoint', type: ExitEndpointView}]
  });

  _(exports).extend({
    SendStateView: SendStateView,
    SendStateEditView: SendStateEditView,
    SendStatePreviewView: SendStatePreviewView
  });
})(go.apps.dialogue.states.send = {});
