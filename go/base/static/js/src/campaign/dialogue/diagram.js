// go.campaign.dialogue.diagram
// ============================
// Structures for the dialogue diagram (the main view for the dialogue screen).

(function(exports) {
  var components = go.components;

  var diagrams = components.plumbing.diagrams,
      DiagramView = diagrams.DiagramView;

  var dialogue = go.campaign.dialogue,
      connections = dialogue.connections,
      states = dialogue.states;

  // The main view containing all the dialogue states and connections
  var DialogueDiagramView = DiagramView.extend({
    stateType: states.DialogueStateView,
    stateCollectionType: states.DialogueStateCollection,

    connectionType: connections.DialogueConnectionView,
    connectionCollectionType: connections.DialogueConnectionCollection
  });

  _(exports).extend({
    DialogueDiagramView: DialogueDiagramView
  });
})(go.campaign.dialogue.diagram = {});
