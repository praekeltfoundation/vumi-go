// go.routing.testHelpers
// ======================

(function(exports) {
  var dialogue = go.apps.dialogue,
      DialogueModel = dialogue.models.DialogueModel,
      DialogueDiagramView = dialogue.diagram.DialogueDiagramView;

   var modelData = function() {
     return {
       campaign_id: 'campaign-1',
       conversation_key: 'conversation-1',
       channel_types: [],
       poll_metadata: {
         repeatable: false,
         delivery_class: 'ussd'
       },
       start_state: {uuid: 'state1'},
       groups: [{
         key: 'group1',
         name: 'Group 1',
         urls: null
       }, {
         key: 'group2',
         name: 'Group 2',
         urls: null
       }, {
         key: 'group3',
         name: 'Group 3',
         urls: null
       }],
       urls: {
         show: 'conversation:show:conversation-1'
       },
       states: [{
         uuid: 'state1',
         name: 'Message 1',
         type: 'choice',
         store_as: 'message-1',
         text: 'What is your favourite colour?',
         user_defined_store_as: false,
         entry_endpoint: {uuid: 'endpoint0'},
         choice_endpoints: [{
           value: 'red',
           label: 'Red',
           uuid: 'endpoint1',
           user_defined_value: false
         }, {
           value: 'blue',
           label: 'Blue',
           uuid: 'endpoint2',
           user_defined_value : false
         }],
         layout: {
           x: 10,
           y: 20
         }
       }, {
         uuid: 'state2',
         name: 'Message 2',
         type: 'freetext',
         store_as: 'message-2',
         user_defined_store_as: false,
         entry_endpoint: {uuid: 'endpoint3'},
         exit_endpoint: {uuid: 'endpoint4'},
         text: 'What is your name?',
         layout: {
           x: 70,
           y: 80
         }
       }, {
         uuid: 'state3',
         name: 'Ending 1',
         type: 'end',
         store_as: 'ending-1',
         user_defined_store_as: false,
         entry_endpoint: {uuid: 'endpoint5'},
         text: 'Thank you for taking our survey',
         layout: {
           x: 130,
           y: 140
         }
       }, {
         uuid: 'state4',
         name: 'Dummy Message 1',
         type: 'dummy',
         user_defined_store_as: false,
         store_as: 'dummy-message-1',
         entry_endpoint: {uuid: 'endpoint6'},
         exit_endpoint: {uuid: 'endpoint7'},
         layout: {
           x: 190,
           y: 200
         }
       }, {
         uuid: 'state5',
         name: 'Message 5',
         type: 'group',
         group: {key: 'group1'},
         user_defined_store_as: false,
         store_as: 'message-5',
         entry_endpoint: {uuid: 'endpoint8'},
         exit_endpoint: {uuid: 'endpoint9'},
         layout: {
           x: 250,
           y: 260
         }
       }],
       connections: [{
         uuid: 'endpoint1-endpoint3',
         source: {uuid: 'endpoint1'},
         target: {uuid: 'endpoint3'}
       }]
    };
  };

  var newDialogueDiagram = function() {
    return new DialogueDiagramView({
      el: '.dialogue #diagram',
      model: new DialogueModel(modelData())
    });
  };

  // Helper methods
  // --------------

  var setUp = function() {
    $('body')
      .append($('<div>')
        .width(1280)
        .attr('class', 'dialogue')
        .append($('<input>')
          .attr('type', 'checkbox')
          .attr('id', 'repeatable'))
        .append($('<select>')
          .attr('id', 'delivery-class')
            .append($('<option>')
              .attr('value', 'ussd')
              .text('Ussd'))
            .append($('<option>')
              .attr('value', 'twitter')
              .text('Twitter')))
        .append($('<button>').attr('id', 'new-state'))
        .append($('<button>').attr('id', 'save-and-exit'))
        .append($('<button>').attr('id', 'save'))
        .append($('<div>').attr('id', 'diagram')));
  };

  var tearDown = function() {
    go.testHelpers.unregisterModels();
    jsPlumb.unbind();
    jsPlumb.detachEveryConnection();
    jsPlumb.deleteEveryEndpoint();
    $('.dialogue').remove();
  };

  _.extend(exports, {
    setUp: setUp,
    tearDown: tearDown,
    modelData: modelData,
    newDialogueDiagram: newDialogueDiagram
  });
})(go.apps.dialogue.testHelpers = {});
