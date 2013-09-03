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
        sessionId: this.sessionId,
        useNotifier: true
      });

      go.apps.dialogue.style.initialize();
    },

    remove: function() {
      DialogueView.__super__.remove.call(this);
      this.save.remove();
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
