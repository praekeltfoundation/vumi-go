// go.campaign.routing.testHelpers
// ===============================

(function(exports) {
  var dialogue = go.campaign.dialogue,
      DialogueModel = dialogue.models.DialogueModel,
      DialogueStateModel = dialogue.models.DialogueStateModel,
      DialogueEndpointModel = dialogue.models.DialogueEndpointModel,
      DialogueDiagramView = dialogue.diagram.DialogueDiagramView;

  var states = dialogue.states,
      DialogueStateView = states.DialogueStateView,
      DialogueStateEditView = states.DialogueStateEditView,
      DialogueStatePreviewView = states.DialogueStatePreviewView;

  var ToyStateModel = DialogueStateModel.extend({
    relations: [{
      type: Backbone.HasOne,
      key: 'entry_endpoint',
      relatedModel: DialogueEndpointModel
    }, {
      type: Backbone.HasOne,
      key: 'exit_endpoint',
      relatedModel: DialogueEndpointModel
    }]
  });

  var ToyStateEditView = DialogueStateEditView.extend({
    template: _.template("toy edit mode")
  });

  var ToyStatePreviewView = DialogueStatePreviewView.extend({
    template: _.template("toy preview mode")
  });

  // A state view type that does nothing. Useful for testing.
  var ToyStateView = DialogueStateView.extend({
    editModeType: ToyStateEditView,
    previewModeType: ToyStatePreviewView,

    endpointSchema: [
      {attr: 'entry_endpoint'},
      {attr: 'exit_endpoint'}]
  });

  // Make toy state subtype to use for testing
  DialogueStateModel.prototype.subModelTypes.toy = 'ToyStateModel';
  DialogueStateView.prototype.subtypes.toy = ToyStateView;

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
      entry_endpoint: {uuid: 'endpoint-3'},
      exit_endpoint: {uuid: 'endpoint-4'},
      text: 'What is your name?'
    }, {
      uuid: 'state-3',
      name: 'Ending 1',
      type: 'end',
      entry_endpoint: {uuid: 'endpoint-5'},
      text: 'Thank you for taking our survey'
    }, {
      uuid: 'state-4',
      name: 'Toy Message 1',
      type: 'toy',
      entry_endpoint: {uuid: 'endpoint-6'},
      exit_endpoint: {uuid: 'endpoint-7'}
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
    ToyStateModel: ToyStateModel,
    ToyStateEditView: ToyStateEditView,
    ToyStatePreviewView: ToyStatePreviewView,
    ToyStateView: ToyStateView,

    setUp: setUp,
    tearDown: tearDown,
    modelData: modelData,
    newDialogueDiagram: newDialogueDiagram
  });
})(go.campaign.dialogue.testHelpers = {});
