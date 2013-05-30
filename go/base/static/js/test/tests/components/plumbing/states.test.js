describe("go.components.plumbing (states)", function() {
  var states = go.components.states,
      StateMachineModel = states.StateMachineModel,
      StateModel = states.StateModel,
      EndpointModel = states.EndpointModel;

  var plumbing = go.components.plumbing,
      DiagramView = go.components.plumbing.DiagramView,
      StateView = plumbing.StateView,
      EndpointView = plumbing.EndpointView,
      StateViewEndpointCollection = plumbing.StateViewEndpointCollection;

  var diagram;

  beforeEach(function() {
    var smModel = new StateMachineModel({
      states: [{
        id: 'a',
        endpoints: [
          {id: 'a1'},
          {id: 'a2'},
          {id: 'a3', target: {id: 'b3'}}]
      }, {
        id: 'b',
        endpoints: [
          {id: 'b1'},
          {id: 'b2'},
          {id: 'b3'}]
      }]
    });

    $('body').append("<div id='diagram'></div>");
    diagram = new DiagramView({el: '#diagram', model: smModel});
  });

  afterEach(function() {
    Backbone.Relational.store.reset();
    jsPlumb.unbind();
    jsPlumb.detachEveryConnection();
    $('#diagram').remove();
  });

  describe(".StateViewEndpointCollection", function() {
    var SingleEndpointStateModel = StateModel.extend({
      relations: [{
          type: Backbone.HasOne,
          key: 'endpoint',
          relatedModel: 'go.components.states.EndpointModel'
        }]
    });

    var SingleEndpointStateView = StateView.extend({
      endpointSchema: [{attr: 'endpoint'}]
    });
    it("should be useable with endpoint collections", function() {
      var endpoints = new StateViewEndpointCollection({
        state: diagram.states.get('a'),
        attr: 'endpoints'
      });

      assert.deepEqual(endpoints.keys(), ['a1', 'a2', 'a3']);
    });

    it("should be useable with single endpoint models", function() {
      var state = new SingleEndpointStateView({
        diagram: diagram,
        model: new SingleEndpointStateModel({id: 'c', endpoint: {id: 'c1'}})
      });

      var endpoints = new StateViewEndpointCollection({
        state: state,
        attr: 'endpoint'
      });

      assert.deepEqual(endpoints.keys(), ['c1']);
    });

    describe(".create", function() {
      var endpoints,
          endpointModel;

      var ToyEndpointView = EndpointView.extend();
      
      beforeEach(function() {
        endpointModel = new EndpointModel({id: 'a4'});

        endpoints = new StateViewEndpointCollection({
          state: diagram.states.get('a'),
          attr: 'endpoints',
          type: ToyEndpointView
        });
      });

      it("should create endpoints of the collection's type", function() {
        assert.instanceOf(endpoints.create(endpointModel), ToyEndpointView);
      });

      it("should give the created endpoint the state view", function() {
        assert.equal(
          endpoints.create(endpointModel).state,
          diagram.states.get('a'));
      });
    });
  });

  describe(".StateView", function() {
    var ToyEndpointView = EndpointView.extend({
      render: function() { this.rendered = true; }
    });

    var InEndpointView = ToyEndpointView.extend(),
        OutEndpointView = ToyEndpointView.extend();

    var ToyStateModel = StateModel.extend({
      relations: [{
          type: Backbone.HasOne,
          key: 'inEndpoint',
          relatedModel: 'go.components.states.EndpointModel'
        }, {
          type: Backbone.HasMany,
          key: 'outEndpoints',
          relatedModel: 'go.components.states.EndpointModel'
        }
      ]
    });

    var ToyStateView = StateView.extend({
      endpointSchema: [
        {attr: 'inEndpoint', type: InEndpointView},
        {attr: 'outEndpoints', type: OutEndpointView}
      ]
    });

    var state;

    beforeEach(function() {
      var model = new ToyStateModel({
        id: 'c',
        inEndpoint: {id: 'cIn'},
        outEndpoints: [
          {id: 'cOut1'},
          {id: 'cOut2'},
          {id: 'cOut3'}]
      });

      state = new ToyStateView({
        diagram: diagram,
        model: model
      });
    });

    it("should set up the endpoints according to the schema", function() {
      assert.deepEqual(
        state
          .endpoints
          .members
          .get('inEndpoint')
          .keys(),
        ['cIn']);

      assert.deepEqual(
        state
          .endpoints
          .members
          .get('outEndpoints')
          .keys(),
        ['cOut1', 'cOut2', 'cOut3']);

      assert.deepEqual(
        state.endpoints.keys(),
        ['cIn', 'cOut1', 'cOut2', 'cOut3']);

      state
        .endpoints
        .members
        .get('inEndpoint')
        .each(function(e) { assert.instanceOf(e, InEndpointView); });

      state
        .endpoints
        .members
        .get('outEndpoints')
        .each(function(e) { assert.instanceOf(e, OutEndpointView); });
    });

    describe(".render", function() {
      it("should add the state view to the diagram", function() {
        assert(_.isEmpty($('#diagram #c').get()));
        state.render();
        assert(!_.isEmpty($('#diagram #c').get()));
      });

      it("shouldn't render duplicates", function() {
        state.render();
        state.render();
        assert.equal($('#diagram #c').length, 1);
      });

      it("should render its endpoints", function() {
        state.endpoints.each(function(e) { assert(!e.rendered); });
        state.render();
        state.endpoints.each(function(e) { assert(e.rendered); });
      });
    });
  });
});
