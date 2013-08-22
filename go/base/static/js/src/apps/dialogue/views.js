// go.apps.dialogue.views
// ======================

(function(exports) {
  var SaveActionView = go.components.actions.SaveActionView;

  var DialogueDiagramView = go.apps.dialogue.diagram.DialogueDiagramView;

  var DialogueView = Backbone.View.extend({
    initialize: function(options) {
      this.sessionId = options.sessionId;

      this.diagram = new DialogueDiagramView({
        el: this.$('#diagram'),
        model: this.model
      });

      this.save = new SaveActionView({
        el: this.$('#save'),
        model: this.model,
        sessionId: this.sessionId
      });

      this.listenTo(this.save, 'error', function() {
        bootbox.alert("Something bad happened, changes couldn't be saved.");
      });

      this.listenTo(this.save, 'success', function() {
        // send user to conversation show page
        go.utils.redirect('/conversations/'
          + this.model.get('conversation_key')
          + '/');
      });

      go.apps.dialogue.style.initialize();
    },

    render: function() {
      this.diagram.render();

      this.$('#repeatable').prop(
        'checked',
        this.model.get('poll_metadata').get('repeatable'));
    },

    events: {
      'click #new-state': function() {
        this.diagram.newState();
      },

      'change #repeatable': function(e) {
        this.model
          .get('poll_metadata')
          .set('repeatable', $(e.target).prop('checked'));
      },
    }
  });

  _(exports).extend({
    DialogueView: DialogueView
  });
})(go.apps.dialogue.views = {});
