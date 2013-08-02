// go.conversation.dashboard
// =========================

(function(exports) {
  var TableFormView = go.components.tables.TableFormView,
      ConversationActionView = go.conversation.views.ConversationActionView;

  var ConversationDashboardView = TableFormView.extend({
    initialize: function(options) {
      ConversationDashboardView.__super__.initialize.call(this, options);

      this.actions = this.$('.action').map(function() {
        return new ConversationActionView({
          el: $(this),
          csrfToken: options.csrfToken
        });
      }).get();
    }
  });

  _.extend(exports, {
    ConversationDashboardView: ConversationDashboardView
  });
})(go.conversation.dashboard = {});
