// go.campaign.routing.testHelpers
// ===============================

(function(exports) {
  var dialogue = go.campaign.dialogue,
      DialogueModel = dialogue.models.DialogueModel,
      DialogueDiagramView = dialogue.diagram.DialogueDiagramView;

  var states = dialogue.states,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var DummyStateEditView = DialogueStateEditView.extend({
    template: _.template("<div>dummy-edit</div>")
  });

  var DummyStatePreviewView = DialogueStatePreviewView.extend({
    template: _.template("<div>dummy-preview</div>")
  });

  var DummyStateView = DialogueStateView.extend({
    editorType: DummyStateEditView,
    previewerType: DummyStatePreviewView,

    render: function() {
      DialogueStateView.prototype.render.call(this);
      this.rendered = true;
    }
  });

  // Give `DialogueStateView` a dummy subtype to use for testing
  DialogueStateView.prototype.subtypes.dummy = DummyStateView;

  var modelData = {
    conversation: 'conversation-key',
    start_state: {uuid: 'state-1'},
    states: [{
      uuid: 'state-1',
      name: 'Message 1',
      type: 'choice',
      entry_endpoint: null,
      text: 'What is your favourite colour?',
      choice_endpoints: [
        {value: 'value-1', label: 'Red', uuid: 'endpoint-1'},
        {value: 'value-2', label: 'Blue', uuid: 'endpoint-2'}]
    }, {
      uuid: 'state-2',
      name: 'Message 2',
      type: 'freetext',
      entry_endpoint: 'endpoint-3',
      exit_endpoint: 'endpoint-4',
      text: 'What is your name?'
    }, {
      uuid: 'state-3',
      name: 'Ending 1',
      type: 'end',
      entry_endpoint: 'endpoint-5',
      text: 'Thank you for taking our survey'
    }, {
      uuid: 'state-4',
      name: 'Dummy Message 1',
      type: 'dummy',
      entry_endpoint: 'endpoint-6',
      exit_endpoint: 'endpoint-7'
    }],
    connections: [{
     source: {uuid: 'endpoint-1'},
     target: {uuid: 'endpoint-2'}
    }]
  };

  var newDialogueDiagram = function() {
    return new DialogueDiagramView({
      el: '#dialogue-diagram',
      model: new DialogueModel(modelData)
    });
  };

  // Helper methods
  // --------------

  var setUp = function() {
    $('body').append([
      "<div id='dialogue-diagram'>",
        "<div class='grid'>",
        "</div>",
      "</div>"
    ].join(''));
  };

  var tearDown = function() {
    Backbone.Relational.store.reset();
    jsPlumb.unbind();
    jsPlumb.detachEveryConnection();
    jsPlumb.deleteEveryEndpoint();
    $('#dialogue-diagram').remove();
  };

  _.extend(exports, {
    setUp: setUp,
    tearDown: tearDown,
    modelData: modelData,
    newDialogueDiagram: newDialogueDiagram
  });
})(go.campaign.dialogue.testHelpers = {});
