// go.channel.show
// ===============

(function(exports) {
  var ChannelActionView = go.channel.views.ChannelActionView;

  var ChannelActionsView = Backbone.View.extend({
    initialize: function(options) {
      this.actions = this.$('.action').map(function() {
        return new ChannelActionView({el: $(this)});
      }).get();
    }
  });

  _.extend(exports, {
    ChannelActionsView: ChannelActionsView
  });
})(go.channel.show = {});
