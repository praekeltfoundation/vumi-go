// go.campaign.dialogue.connections
// ================================
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
      // TODO scary connection acceptance rules go here
      return true;
    }
  });

  _(exports).extend({
    DialogueConnectionView: DialogueConnectionView,
    DialogueConnectionCollection: DialogueConnectionCollection
  });
})(go.campaign.dialogue.connections = {});
