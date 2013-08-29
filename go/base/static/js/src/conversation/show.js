// go.conversation.show
// ====================

(function(exports) {
  var ConversationActionView = go.conversation.views.ConversationActionView;

  var ConversationActionsView = Backbone.View.extend({
    initialize: function(options) {
      this.actions = this.$('.action').map(function() {
        return new ConversationActionView({el: $(this)});
      }).get();
    }
  });

  _.extend(exports, {
    ConversationActionsView: ConversationActionsView
  });
})(go.conversation.show = {});
