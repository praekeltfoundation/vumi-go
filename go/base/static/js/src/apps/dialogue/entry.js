(function(exports) {
  var DialogueEntryPointView = Backbone.View.extend({
    className: 'box entry-point',

    initialize: function(options) {
      this.diagram = options.diagram;

      this.$text = $('<span>');

      this.$endpoint = $('<div>')
        .addClass('endpoint')
        .addClass('endpoint-source')
        .addClass('endpoint-entry');

      this.target = null;
      this.plumbConnection = null;

      this.onEnding = this.onEnding.bind(this);
      this.onConnect = this.onConnect.bind(this);
      jsPlumb.bind('connection', this.onConnect);
      jsPlumb.makeSource(this.$endpoint, {maxConnections: 1});
    },

    render: function() {
      this.$text
        .text('Start')
        .appendTo(this.$el);

      this.$endpoint
        .appendTo(this.$el);

      this.initTarget();
      if (this.target) this.connect(this.target);
    },

    connect: function(target) {
      this.setTarget(target);

      this.plumbConnection = jsPlumb.connect({
        source: this.$endpoint,
        target: this.target.$el,
      }, {fireEvent: false});

      this.plumbConnection.setReattach(true);
      this.trigger('connect', this.target);
    },

    detach: function(options) {
      options = _.defaults(options || {}, {fireEvent: false});
      var target = this.target;
      jsPlumb.detach(this.plumbConnection, options.fireEvent);
      this.unsetTarget();
      this.trigger('detach', target);
    },

    initTarget: function() {
      var target = this.getTarget();
      if (target) this.setTarget(target);
    },

    getTarget: function() {
      var model = this.diagram.model
        .get('start_state')
        .get('entry_endpoint');

      if (!model) return null;
      var endpoint = this.diagram.endpoints.get(model.id);
      return endpoint;
    },

    setTarget: function(target) {
      this.unsetTarget();
      this.target = target;
      this.target.once('ending', this.onEnding);
      this.diagram.model.set('start_state', this.target.state.model);
      this.trigger('set:target', target);
    },

    unsetTarget: function() {
      var target = this.target;
      if (!target) return;
      this.target.off('ending', this.onEnding);
      this.diagram.model.unset('start_state');
      this.target = null;
      this.trigger('unset:target', target);
    },

    onConnect: function(e) {
      if (!this.$endpoint.is(e.source)) return;
      this.plumbConnection = e.connection;
      var targetId = $(e.target).attr('data-uuid');
      this.setTarget(this.diagram.endpoints.get(targetId));
    },

    onEnding: function() {
      this.detach();
    }
  });


  exports.DialogueEntryPointView = DialogueEntryPointView;
})(go.apps.dialogue.entry = {});
