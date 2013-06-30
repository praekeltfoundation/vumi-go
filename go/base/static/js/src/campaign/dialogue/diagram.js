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
    connectionCollectionType: connections.DialogueConnectionCollection,

    initialize: function(options) {
      DialogueDiagramView.__super__.initialize.call(this, options);
      if (!this.states.size()) { this.newState(); }

      jsPlumb.Defaults.Connector = ['Flowchart'];
      this.connections.on('error:unsupported', this.onUnsupportedConnection);
    },

    newState: function() {
      return this.states.add('states', {mode: 'edit'});
    },

    onUnsupportedConnection: function(source, target, plumbConnection) {
      jsPlumb.detach(plumbConnection, {fireEvent: false});
    }
  });

  _(exports).extend({
    DialogueDiagramView: DialogueDiagramView
  });
})(go.campaign.dialogue.diagram = {});
