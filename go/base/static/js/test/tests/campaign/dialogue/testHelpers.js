// go.campaign.routing.testHelpers
// ===============================

(function(exports) {
  var dialogue = go.campaign.dialogue,
      DialogueModel = dialogue.models.DialogueModel,
      DialogueDiagramView = dialogue.diagram.DialogueDiagramView;

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
      name: 'Dummy Message 1',
      type: 'dummy',
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
      el: '.dialogue #diagram',
      model: new DialogueModel(modelData)
    });
  };

  // Helper methods
  // --------------

  var setUp = function() {
    $('body').append([
      "<div class='dialogue'>",
        "<div id='diagram'></div>",
      "</div>"
    ].join(''));
  };

  var tearDown = function() {
    go.testHelpers.unregisterModels();
    jsPlumb.unbind();
    jsPlumb.detachEveryConnection();
    jsPlumb.deleteEveryEndpoint();
    $('.dialogue #diagram').remove();
  };

  _.extend(exports, {
    setUp: setUp,
    tearDown: tearDown,
    modelData: modelData,
    newDialogueDiagram: newDialogueDiagram
  });
})(go.campaign.dialogue.testHelpers = {});
