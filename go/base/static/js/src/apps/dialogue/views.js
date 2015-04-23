// go.apps.dialogue.views
// ======================

(function(exports) {
  var SaveActionView = go.components.actions.SaveActionView;

  var DialogueDiagramView = go.apps.dialogue.diagram.DialogueDiagramView;

  var DialogueView = Backbone.View.extend({
    events: {
      'click #new-state': function() {
        this.diagram.newState();
      },

      'change #repeatable': function(e) {
        this.model
          .get('poll_metadata')
          .set('repeatable', $(e.target).prop('checked'));
      },

      'change #delivery-class': function(e) {
        this.model
          .get('poll_metadata')
          .set('delivery_class', $(e.target).val());
      },
    },

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

      this.listenTo(this.save, 'success', function() {
        go.utils.redirect(this.model.get('urls').get('show'));
      });

      go.apps.dialogue.style.initialize();
    },

    remove: function() {
      DialogueView.__super__.remove.call(this);
      this.save.remove();
    },

    render: function() {
      this.diagram.render();

      var metadata = this.model.get('poll_metadata');
      this.$('#repeatable').prop('checked', metadata.get('repeatable'));

      if (metadata.get('delivery_class')) {
        this.$('#delivery-class').val(metadata.get('delivery_class'));
      }
    }
  });

  _(exports).extend({
    DialogueView: DialogueView
  });
})(go.apps.dialogue.views = {});
