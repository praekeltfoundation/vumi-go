// go.channel.views
// ================

(function(exports) {
  var CallActionView = go.components.actions.CallActionView;

  // NOTE: This view will hopefully not be around too long. Ideally, we want
  // models and collections for our channels that can invoke their actions,
  // and make api requests accordingly.
  var ChannelActionView = CallActionView.extend({
    name: function() { return this.$el.attr('data-action'); },
    data: function() { return {csrfmiddlewaretoken: $.cookie('csrftoken')}; },
    useNotifier: true,

    invoke: function() {
      var invoke = ChannelActionView.__super__.invoke.bind(this);

      bootbox.confirm(
        'Are you sure you want to ' + this.name() + ' this channel?',
        function(submit) { if (submit) { invoke(); } });
    }
  });

  _(exports).extend({
    ChannelActionView: ChannelActionView
  });
})(go.channel.views = {});
