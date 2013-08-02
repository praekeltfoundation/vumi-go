// go.conversation.dashboard
// =========================

(function(exports) {
  var TableFormView = go.components.tables.TableFormView,
      ConversationActionView = go.conversation.views.ConversationActionView;

  var ConversationDashboardView = TableFormView.extend({
    initialize: function(options) {
      ConversationDashboardView.__super__.initialize.call(this, options);

      this.actions = this.$('.inline-action').map(function() {
        return new ConversationActionView({el: $(this)});
      }).get();
    }
  });

  _.extend(exports, {
    ConversationDashboardView: ConversationDashboardView
  });
})(go.conversation.dashboard = {});
