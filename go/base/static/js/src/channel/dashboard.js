// go.channel.dashboard
// ====================

(function(exports) {
  var TableFormView = go.components.tables.TableFormView,
      ChannelActionView = go.channel.views.ChannelActionView;

  var ChannelDashboardView = TableFormView.extend({
    initialize: function(options) {
      ChannelDashboardView.__super__.initialize.call(this, options);

      this.actions = this.$('.action').map(function() {
        return new ChannelActionView({el: $(this)});
      }).get();
    }
  });

  _.extend(exports, {
    ChannelDashboardView: ChannelDashboardView
  });
})(go.channel.dashboard = {});
