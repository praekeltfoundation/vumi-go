// go.apps.dialogue.connections
// ============================
// Structures and logic for the connections between states in the dialogue
// diagram.

(function(exports) {
  var connections = go.components.plumbing.connections,
      ConnectionView = connections.ConnectionView,
      ConnectionViewCollection = connections.ConnectionViewCollection;

  var DialogueConnectionView = ConnectionView.extend();

  var DialogueConnectionCollection = ConnectionViewCollection.extend({
    type: DialogueConnectionView,

    accepts: function(source, target) {
      if (source.state === target.state) { return false; }
      return true;
    }
  });

  _(exports).extend({
    DialogueConnectionView: DialogueConnectionView,
    DialogueConnectionCollection: DialogueConnectionCollection
  });
})(go.apps.dialogue.connections = {});
