// go.routing (views)
// ==================
// Views for routing diagram.

(function(exports) {
  var actions = go.components.actions,
      SaveActionView = actions.SaveActionView,
      ResetActionView = actions.ResetActionView;

  var plumbing = go.components.plumbing;

  var states = plumbing.states,
      StateView = states.StateView,
      StateViewCollection = states.StateViewCollection;

  var endpoints = plumbing.endpoints,
      ParametricEndpointView = endpoints.ParametricEndpointView,
      AligningEndpointCollection = endpoints.AligningEndpointCollection;

  var connections = plumbing.connections,
      DirectionalConnectionView = connections.DirectionalConnectionView,
      ConnectionViewCollection = connections.ConnectionViewCollection,
      connectorOverlays = connections.connectorOverlays;

  var diagrams = plumbing.diagrams,
      DiagramView = diagrams.DiagramView;

  // Endpoints
  // ---------

  var RoutingEndpointView = ParametricEndpointView.extend({
    className: 'endpoint label',
    render: function() {
      this.$el.text(this.model.get('name'));
      return ParametricEndpointView.prototype.render.call(this);
    }
  });

  var ChannelEndpointView = RoutingEndpointView.extend(),
      RouterChannelEndpointView = RoutingEndpointView.extend(),
      RouterConversationEndpointView = RoutingEndpointView.extend(),
      ConversationEndpointView = RoutingEndpointView.extend();

  // Routing entries (connections)
  // -----------------------------

  var RoutingEntryCollection = ConnectionViewCollection.extend({
    acceptedPairs: [
      [ChannelEndpointView, RouterChannelEndpointView],
      [ConversationEndpointView, RouterConversationEndpointView],
      [ChannelEndpointView, ConversationEndpointView]],

    accepts: function(source, target) {
      var pairs = this.acceptedPairs,
          i = pairs.length,
          pair, a, b;

      while (i--) {
        pair = pairs[i], a = pair[0], b = pair[1];
        if (source instanceof a && target instanceof b) { return true; }
        if (target instanceof a && source instanceof b) { return true; }
      }

      return false;
    }
  });

  // States
  // ------

  var RoutingStateView = StateView.extend({
    endpointType: RoutingEndpointView,
    endpointCollectionType: AligningEndpointCollection,
    maxEndpoints: 2,
    heightPerEndpoint: 45,

    initialize: function(options) {
      StateView.prototype.initialize.call(this, options);
      this.$name = $('<a class="name" href=""></a>');
    },

    endpointsForSide: function(side){
      return this.endpoints.where({side: side});
    },

    findMaxEndpoints: function(){
      return Math.max(
        this.endpointsForSide('left').length,
        this.endpointsForSide('right').length
      );
    },

    tooManyEndpoints: function() {
      return this.findMaxEndpoints() > this.maxEndpoints;
    },

    stretchedHeight: function() {
      return this.findMaxEndpoints() * this.heightPerEndpoint;
    },

    render: function() {
      this.collection.appendToView(this);

      this.$el
        .css('position', 'relative')
        .append(this.$name);
      
      if(this.tooManyEndpoints()) {
        this.$el.height(this.stretchedHeight());
      }

      this.$name.text(this.model.get('name'));
      this.$name.attr('href', this.model.viewURL());

      this.endpoints.render();

      return this;
    }
  });

  var ChannelStateView = RoutingStateView.extend({
    className: 'state channel',
    endpointSchema: [{
      attr: 'endpoints',
      side: 'right',
      type: ChannelEndpointView
    }]
  });

  var RouterStateView = RoutingStateView.extend({
    className: 'state router',
    endpointSchema: [{
      attr: 'channel_endpoints',
      side: 'left',
      type: RouterChannelEndpointView
    }, {
      attr: 'conversation_endpoints',
      side: 'right',
      type: RouterConversationEndpointView
    }]
  });

  var ConversationStateView = RoutingStateView.extend({
    className: 'state conversation',
    endpointSchema: [{
      attr: 'endpoints',
      side: 'left',
      type: ConversationEndpointView
    }]
  });

  var RoutingStateCollection = StateViewCollection.extend({
    ordered: true,

    comparator: function(state) {
      return state.model.get('ordinal');
    },

    initialize: function(options) {
      this.$column = this.view.$(options.columnEl);
    },

    appendToView: function(viewOrId) {
      var subview = this.resolveView(viewOrId);
      this.$column.append(subview.$el);
    }
  });

  // Columns
  // -------

  // A vertical section of the routing diagram dedicated to a particular
  // collection of the three state types (Channel, Router or
  // Conversation).
  var RoutingColumnView = Backbone.View.extend({
    initialize: function(options) {
      this.diagram = options.diagram;
      this.states = this.diagram.states.members.get(this.collectionName);
      this.setElement(this.diagram.$('#' + this.id));
      this.onDrag = this.onDrag.bind(this);
      this.onStop = this.onStop.bind(this);
    },

    onDrag: function() {
      this.repaint();
    },

    onStop: function() {
      this.repaint();
      this.updateOrdinals();
    },

    repaint: function() {
      _.chain(this.states.values())
       .map(getEndpoints)
       .flatten()
       .map(getEl)
       .each(plumbing.utils.repaintSortable);

      this.trigger('repaint');
    },

    updateOrdinals: function() {
      this.$('.state')
        .map(getElUuid)
        .get()
        .forEach(this._setOrdinal, this);

      this.trigger('update:ordinals');
    },

    render: function() {
      // Allow the user to 'shuffle' the states in the column, repainting the
      // jsPlumb connections and endpoints on each update hook
      this.$el.sortable({
        cursor: 'move',
        start: this.onDrag,
        sort: this.onDrag,
        stop: this.onStop
      });

      this.states.each(function(state) {
        state.render();
      });

      this.repaint();
    },

    _setOrdinal: function(id, i) {
      return this.states.get(id).model.set('ordinal', i);
    }
  });

  var ChannelColumnView = RoutingColumnView.extend({
    id: 'channels',
    collectionName: 'channels'
  });

  var RouterColumnView = RoutingColumnView.extend({
    id: 'routers',
    collectionName: 'routers'
  });

  var ConversationColumnView = RoutingColumnView.extend({
    id: 'conversations',
    collectionName: 'conversations'
  });

  // Main components
  // ---------------

  var RoutingDiagramView = DiagramView.extend({
    stateCollectionType: RoutingStateCollection,
    stateSchema: [{
      attr: 'channels',
      type: ChannelStateView,
      columnEl: '#channels'
    }, {
      attr: 'routers',
      type: RouterStateView,
      columnEl: '#routers'
    }, {
      attr: 'conversations',
      type: ConversationStateView,
      columnEl: '#conversations'
    }],

    connectionType: DirectionalConnectionView,
    connectionCollectionType: RoutingEntryCollection,
    connectionSchema: [{attr: 'routing_entries'}],

    initialize: function(options) {
      DiagramView.prototype.initialize.call(this, options);
      this.channels = new ChannelColumnView({diagram: this});
      this.routers = new RouterColumnView({diagram: this});
      this.conversations = new ConversationColumnView({diagram: this});

      // Give the jsPlumb connectors arrow overlays
      jsPlumb.Defaults.ConnectionOverlays = [connectorOverlays.headArrow];

      this.connections.on('error:unsupported', this.onUnsupportedConnection);
    },

    onUnsupportedConnection: function(source, target, plumbConnection) {
      // TODO handle better in future (Response in UI or something?)
      jsPlumb.detach(plumbConnection, {fireEvent: false});
    },

    render: function() {
      this.channels.render();
      this.routers.render();
      this.conversations.render();
      this.connections.render();
      return this;
    }
  });

  var RoutingView = Backbone.View.extend({
    bindings: {
      'success save': function() {
        this.model.persistOrdinals();
      }
    },

    initialize: function(options) {
      this.diagram = new RoutingDiagramView({
        el: '#diagram',
        model: this.model
      });

      this.save = new SaveActionView({
        el: this.$('#save'),
        sessionId: options.sessionId,
        model: this.model,
        useNotifier: true
      });

      this.reset = new ResetActionView({
        el: this.$('#reset'),
        model: this.model,
        useNotifier: true
      });

      go.routing.style.initialize();
      go.utils.bindEvents(this.bindings, this);
    },

    remove: function() {
      this.save.remove();
      this.reset.remove();
      this.diagram.remove();
      RoutingView.__super__.remove.call(this);
    },

    render: function() {
      this.diagram.render();
    }
  });


  function getEndpoints(state) {
    return state.endpoints.values();
  }


  function getEl(view) {
    return view.$el;
  }


  function getElUuid($el) {
    return $(this).attr('data-uuid');
  }


  _(exports).extend({
    RoutingDiagramView: RoutingDiagramView,
    RoutingView: RoutingView,

    RoutingColumnView: RoutingColumnView,
    ChannelColumnView: ChannelColumnView,
    RouterColumnView: RouterColumnView,
    ConversationColumnView: ConversationColumnView,

    RoutingStateView: RoutingStateView,
    RoutingStateCollection: RoutingStateCollection,
    ChannelStateView: ChannelStateView,
    RouterStateView: RouterStateView,
    ConversationStateView: ConversationStateView,

    RoutingEndpointView: RoutingEndpointView,
    RoutingEntryCollection: RoutingEntryCollection
  });
})(go.routing.views = {});
