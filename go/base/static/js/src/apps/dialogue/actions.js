// go.apps.dialogue.actions
// ========================

(function(exports) {
  var actions = go.components.actions,
      SaveActionView = actions.SaveActionView;

  var DialogueActionsView = Backbone.View.extend({
    initialize: function(options) {
      this.diagram = options.diagram;
      this.model = this.diagram.model;

      this.save = new SaveActionView({
        el: this.$('[data-action=save]'),
        sessionId: options.sessionId,
        model: this.model
      });

      this.listenTo(this.save, 'error', function() {
        bootbox.alert("Something bad happened, changes couldn't be saved.");
      });

      this.listenTo(this.save, 'success', function() {
        bootbox.alert("Something bad happened, changes couldn't be saved.");

        // send user to conversation show page
        go.utils.redirect('/conversations/'
          + this.model.get('conversation_key')
          + '/');
      });
    },

    events: {
      'click [data-action=new-state]': function() { this.diagram.newState(); }
    }
  });

  _(exports).extend({
    DialogueActionsView: DialogueActionsView
  });
})(go.apps.dialogue.actions = {});
