describe("go.components.plumbing (states)", function() {
  var stateMachine = go.components.stateMachine,
      StateMachineModel = stateMachine.StateMachineModel,
      StateModel = stateMachine.StateModel;

  var plumbing = go.components.plumbing,
      DiagramView = go.components.plumbing.DiagramView,
      StateView = plumbing.StateView,
      EndpointView = plumbing.EndpointView,
      StateViewEndpointCollection = plumbing.StateViewEndpointCollection;

  var ToyStateModel = StateModel.extend({
    relations: [{
        type: Backbone.HasOne,
        key: 'inEndpoint',
        relatedModel: 'go.components.stateMachine.EndpointModel'
      }, {
        type: Backbone.HasMany,
        key: 'outEndpoints',
        relatedModel: 'go.components.stateMachine.EndpointModel'
      }
    ]
  });

  var ToyStateMachineModel = StateMachineModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'states',
      relatedModel: ToyStateModel
    }, {
      type: Backbone.HasOne,
      key: 'state0',
      includeInJSON: 'id',
      relatedModel: 'go.components.stateMachine.StateModel'
    }, {
      type: Backbone.HasMany,
      key: 'connections',
      relatedModel: 'go.components.stateMachine.ConnectionModel'
    }]
  });

  var ToyEndpointView = EndpointView.extend({
    render: function() {
      EndpointView.prototype.render.call(this);
      this.rendered = true;
    }
  });

  var InEndpointView = ToyEndpointView.extend(),
      OutEndpointView = ToyEndpointView.extend();

  var ToyStateView = StateView.extend({
    endpointSchema: [
      {attr: 'inEndpoint', type: InEndpointView},
      {attr: 'outEndpoints', type: OutEndpointView}
    ]
  });

  var ToyDiagramView = DiagramView.extend({stateType: ToyStateView});

  var diagram,
      state;

  beforeEach(function() {
    var model = new ToyStateMachineModel({
      states: [{
        id: 'state',
        inEndpoint: {id: 'in'},
        outEndpoints: [
          {id: 'out1'},
          {id: 'out2'},
          {id: 'out3'}]
      }],

      connections: []
    });

    $('body').append("<div id='diagram'></div>");
    diagram = new ToyDiagramView({el: '#diagram', model: model});
    state = diagram.states.get('state');
  });

  afterEach(function() {
    Backbone.Relational.store.reset();
    jsPlumb.unbind();
    jsPlumb.detachEveryConnection();
    $('#diagram').remove();
  });

  describe(".StateView", function() {
    it("should set up the endpoints according to the schema", function() {
      var inEndpoint = state.endpoints.members.get('inEndpoint'),
          outEndpoints = state.endpoints.members.get('outEndpoints');

      assert.deepEqual(inEndpoint.keys(), ['in']);
      assert.deepEqual(outEndpoints.keys(), ['out1', 'out2', 'out3']);

      inEndpoint.each(function(e) { assert.instanceOf(e, InEndpointView); });
      outEndpoints.each(function(e) { assert.instanceOf(e, OutEndpointView); });

      assert.deepEqual(
        state.endpoints.keys(),
        ['in', 'out1', 'out2', 'out3']);
    });

    describe(".render", function() {
      it("should add the state view to the diagram", function() {
        assert(_.isEmpty($('#diagram #state').get()));
        state.render();
        assert(!_.isEmpty($('#diagram #state').get()));
      });

      it("shouldn't render duplicates", function() {
        state.render();
        state.render();
        assert.equal($('#diagram #state').length, 1);
      });

      it("should render its endpoints", function() {
        state.endpoints.each(function(e) { assert(!e.rendered); });
        state.render();
        state.endpoints.each(function(e) { assert(e.rendered); });
      });
    });
  });
});
