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
    template: _.template("toy edit mode: <%= model.name %>")
  });

  var ToyStatePreviewView = DialogueStatePreviewView.extend({
    template: _.template("toy preview mode: <%= model.name %>")
  });

  // A state view type that does nothing. Useful for testing.
  var ToyStateView = DialogueStateView.extend({
    editModeType: ToyStateEditView,
    previewModeType: ToyStatePreviewView,

    endpointSchema: [
      {attr: 'entry_endpoint', side: 'left'},
      {attr: 'exit_endpoint', side: 'right'}]
  });

  // Make a toy state subtype to use for testing
  DialogueStateModel.prototype.subModelTypes.toy
    = 'go.campaign.dialogue.testHelpers.ToyStateModel';

  DialogueStateView.prototype.subtypes.toy = ToyStateView;

  var modelData = {
    conversation: 'conversation-key',
    start_state: {uuid: 'state1'},
    states: [{
      uuid: 'state1',
      name: 'Message 1',
      type: 'choice',
      text: 'What is your favourite colour?',
      entry_endpoint: {uuid: 'endpoint0'},
      choice_endpoints: [
        {value: 'value1', label: 'Red', uuid: 'endpoint1'},
        {value: 'value2', label: 'Blue', uuid: 'endpoint2'}]
    }, {
      uuid: 'state2',
      name: 'Message 2',
      type: 'freetext',
      entry_endpoint: {uuid: 'endpoint3'},
      exit_endpoint: {uuid: 'endpoint4'},
      text: 'What is your name?'
    }, {
      uuid: 'state3',
      name: 'Ending 1',
      type: 'end',
      entry_endpoint: {uuid: 'endpoint5'},
      text: 'Thank you for taking our survey'
    }, {
      uuid: 'state4',
      name: 'Toy Message 1',
      type: 'toy',
      entry_endpoint: {uuid: 'endpoint6'},
      exit_endpoint: {uuid: 'endpoint7'}
    }],
    connections: [{
     source: {uuid: 'endpoint1'},
     target: {uuid: 'endpoint3'}
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
    $('body').append("<div id='dialogue-diagram'></div>");
  };

  var tearDown = function() {
    go.testHelpers.unregisterModels();
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
