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
    className: 'boxes',

    stateType: states.DialogueStateView,
    stateCollectionType: states.DialogueStateCollection,

    connectionType: connections.DialogueConnectionView,
    connectionCollectionType: connections.DialogueConnectionCollection,

    initialize: function(options) {
      DialogueDiagramView.__super__.initialize.call(this, options);
      go.utils.bindEvents(this.bindings, this);
    },

    newState: function() {
      return this.states.add('states');
    },

    bindings: {
      'error:unsupported connections': function(source, target, plumbConnection) {
        jsPlumb.detach(plumbConnection, {fireEvent: false});
      }
    },

    render: function() {
      this.$el.addClass(this.className);
      DialogueDiagramView.__super__.render.call(this);
    }
  });

  _(exports).extend({
    DialogueDiagramView: DialogueDiagramView
  });
})(go.apps.dialogue.diagram = {});
