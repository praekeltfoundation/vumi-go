// go.campaign.dialogue.states.dummy
// =================================
// A dummy state type for testing

(function(exports) {
  var states = go.campaign.dialogue.states,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var DummyStateEditView = DialogueStateEditView.extend({
    bodyTemplate: _.template("dummy edit mode: <%= model.name %>")
  });

  var DummyStatePreviewView = DialogueStatePreviewView.extend({
    bodyTemplate: _.template("dummy preview mode: <%= model.name %>")
  });

  // A state view type that does nothing. Useful for testing.
  var DummyStateView = DialogueStateView.extend({
    typeName: 'dummy',

    editModeType: DummyStateEditView,
    previewModeType: DummyStatePreviewView,

    endpointSchema: [
      {attr: 'entry_endpoint', side: 'left'},
      {attr: 'exit_endpoint', side: 'right'}]
  });

  _(exports).extend({
    DummyStatePreviewView: DummyStatePreviewView,
    DummyStateEditView: DummyStateEditView,
    DummyStateView: DummyStateView
  });
})(go.campaign.dialogue.states.dummy = {});
