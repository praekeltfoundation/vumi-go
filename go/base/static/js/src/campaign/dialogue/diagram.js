// go.campaign.dialogue.diagram
// ============================
// Structures for the dialogue diagram (the main view for the dialogue screen).

(function(exports) {
  var plumbing = go.components.plumbing,
      DiagramView = plumbing.DiagramView;

  var dialogue = go.campaign.dialogue,
      connections = dialogue.connections,
      states = dialogue.states,
      grid = dialogue.grid;

  var DialogueStateShellCollection = states.DialogueStateShellCollection;

  // The main view containing all the dialogue states and connections
  var DialogueDiagramView = DiagramView.extend({
    stateType: states.DialogueStateView,

    connectionType: connections.DialogueConnectionView,
    connectionCollectionType: connections.DialogueConnectionCollection,

    initialize: function(options) {
      DiagramView.prototype.initialize.call(this, options);

      this.grid = new grid.DialogueGridView({diagram: this});
      this.stateShells = new DialogueStateShellCollection({diagram: this});
    },

    render: function() {
      this.grid.render();
      this.stateShells.render();
      this.connections.render();
      return this;
    }
  });

  _(exports).extend({
    DialogueDiagramView: DialogueDiagramView
  });
})(go.campaign.dialogue.diagram = {});
