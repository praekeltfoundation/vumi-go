// go.conversation.views
// =====================

(function(exports) {
  var CallActionView = go.components.actions.CallActionView;

  // NOTE: This view will hopefully not be around too long. Ideally, we want
  // models and collections for our conversations that can invoke their actions,
  // and make api requests accordingly.
  var ConversationActionView = CallActionView.extend({
    data: function() { return {csrfmiddlewaretoken: this.csrfToken}; },

    initialize: function(options) {
      this.csrfToken = options.csrfToken;
      this.on('success', function() { location.reload(); });
    }
  });

  _(exports).extend({
    ConversationActionView: ConversationActionView
  });
})(go.conversation.views = {});
