describe("go.components.plumbing (diagrams)", function() {
  describe(".Diagram", function() {
    var stateMachine = go.components.stateMachine,
        StateMachineModel = stateMachine.StateMachineModel,
        StateModel = stateMachine.StateModel;

    var plumbing = go.components.plumbing,
        DiagramView = go.components.plumbing.DiagramView,
        StateView = plumbing.StateView,
        EndpointView = plumbing.EndpointView,
        StateViewEndpointCollection = plumbing.StateViewEndpointCollection;

    var ToyStateView = StateView.extend({
      render: function() {
        StateView
          .prototype
          .render
          .call(this);

        this.rendered = true;
      }
    });

    var SithStateView = ToyStateView.extend(),
        JediStateView = ToyStateView.extend();

    var ToyStateMachineModel = StateMachineModel.extend({
      relations: [{
        type: Backbone.HasMany,
        key: 'jedis',
        relatedModel: 'go.components.stateMachine.StateModel'
      }, {
        type: Backbone.HasMany,
        key: 'siths',
        relatedModel: 'go.components.stateMachine.StateModel'
      }, {
        type: Backbone.HasOne,
        key: 'state0',
        includeInJSON: 'id',
        relatedModel: 'go.components.stateMachine.StateModel'
      }]
    });

    var ToyDiagramView = DiagramView.extend({
      stateSchema: [
        {attr: 'jedis', type: JediStateView},
        {attr: 'siths', type: SithStateView}
      ]
    });

    var diagram;

    beforeEach(function() {
      var model = new ToyStateMachineModel({
        jedis: [{
          id: 'jedi-a',
          endpoints: [
            {id: 'jedi-a1'},
            {id: 'jedi-a2'},
            {id: 'jedi-a3', target: {id: 'sith-b2'}}]
        }, {
          id: 'jedi-b',
          endpoints: [
            {id: 'jedi-b1'},
            {id: 'jedi-b2'},
            {id: 'jedi-b3'}]
        }],
        siths: [{
          id: 'sith-a',
          endpoints: [
            {id: 'sith-a1'},
            {id: 'sith-a2'},
            {id: 'sith-a3'}]
        }, {
          id: 'sith-b',
          endpoints: [
            {id: 'sith-b1'},
            {id: 'sith-b2'},
            {id: 'sith-b3'}]
        }]
      });

      $('body').append("<div id='diagram'></div>");
      diagram = new ToyDiagramView({el: '#diagram', model: model});
    });

    it("should set up the states according to the schema", function() {
      assert.deepEqual(
        diagram
          .states
          .members
          .get('jedis')
          .keys(),
        ['jedi-a', 'jedi-b']);

      assert.deepEqual(
        diagram
          .states
          .members
          .get('siths')
          .keys(),
        ['sith-a', 'sith-b']);

      assert.deepEqual(
        diagram.states.keys(),
        ['jedi-a', 'jedi-b', 'sith-a', 'sith-b']);

      diagram
        .states
        .members
        .get('jedis')
        .each(function(e) { assert.instanceOf(e, JediStateView); });

      diagram
        .states
        .members
        .get('siths')
        .each(function(e) { assert.instanceOf(e, SithStateView); });
    });

    describe(".render", function() {
      it("should render its states", function() {
        diagram.states.each(function(s) { assert(!s.rendered); });
        diagram.render();
        diagram.states.each(function(s) { assert(s.rendered); });
      });
    });
  });
});
