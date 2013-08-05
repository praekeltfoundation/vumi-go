// go.apps.dialogue.diagram
// ========================
// Structures for the dialogue diagram (the main view for the dialogue screen).

(function(exports) {
  var components = go.components;

  var diagrams = components.plumbing.diagrams,
      DiagramView = diagrams.DiagramView;

  var dialogue = go.apps.dialogue,
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

      if (!this.states.size()) {
        var state = this.newState();
        this.model.set('start_state', state.model);
      }

      this.dialogueStates = this.states.members.get('states');
      go.utils.bindEvents(this.bindings, this);
    },

    newState: function() {
      return this.dialogueStates.add();
    },

    bindings: {
      'error:unsupported connections': function(source, target, plumbConnection) {
        jsPlumb.detach(plumbConnection, {fireEvent: false});
      },

      'sort dialogueStates': function() {
        this.model.set('start_state', this.dialogueStates.at(0).model);
      }
    }
  });

  _(exports).extend({
    DialogueDiagramView: DialogueDiagramView
  });
})(go.apps.dialogue.diagram = {});
