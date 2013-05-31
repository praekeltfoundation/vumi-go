describe("go.components.plumbing (diagrams)", function() {
  var stateMachine = go.components.stateMachine,
      EndpointModel = stateMachine.EndpointModel,
      StateModel = stateMachine.StateModel,
      StateMachineModel = stateMachine.StateMachineModel;

  var plumbing = go.components.plumbing,
      EndpointView = plumbing.EndpointView,
      StateView = plumbing.StateView,
      ConnectionView = plumbing.ConnectionView,
      DiagramView = plumbing.DiagramView,
      DiagramViewConnections = plumbing.DiagramViewConnections;

  var ToyStateView = StateView.extend({
    destroy: function() {
      StateView
        .prototype
        .destroy
        .call(this);

      this.destroyed = true;
    },

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

  var ToyConnectionView = ConnectionView.extend({
    destroy: function() {
      ConnectionView
        .prototype
        .destroy
        .call(this);

      this.destroyed = true;
    },

    render: function() {
      ConnectionView
        .prototype
        .render
        .call(this);

      this.rendered = true;
    }
  });

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
    ConnectionView: ToyConnectionView,
    stateSchema: [
      {attr: 'jedis', type: JediStateView},
      {attr: 'siths', type: SithStateView}
    ]
  });

  var diagram;

  beforeEach(function() {
    // Sorry, I know its a very bad example. Siths and Jedis are state types.
    // ToyStateMachineModel contains two collections of states: one for the
    // sith states, one for jedi states.
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

  afterEach(function() {
    Backbone.Relational.store.reset();
    jsPlumb.unbind();
    jsPlumb.detachEveryConnection();
    $('#diagram').remove();
  });

  describe(".DiagramViewEndpoints", function() {
    var endpoints,
        jediA,
        ewokA;

    var assertSubscribed = function(id, otherEndpoints) {
      assert(endpoints.members.has(id));
      assert.includeMembers(endpoints.keys(), otherEndpoints.keys());
    };

    var assertUnsubscribed = function(id, otherEndpoints) {
      assert(!endpoints.members.has(id));
      otherEndpoints.eachItem(function(id) { assert(!endpoints.has(id)); });
    };

    beforeEach(function() {
      endpoints = diagram.endpoints;

      var ewokModelA = new StateModel({
        id: 'ewok-a',
        endpoints: [{id: 'ewok-a1'}, {id: 'ewok-a2'}]
      });

      ewokA = new StateView({diagram: diagram, model: ewokModelA});
      jediA = diagram.states.get('jedi-a');
    });

    describe("on 'add' state events", function() {
      it("should subscribe the new state's endpoints to the group",
      function(done) {
        diagram.states.on('add', function() {
          assertSubscribed('ewok-a', ewokA.endpoints);
          done();
        });

        diagram.states.add('ewok-a', ewokA);
      });
    });

    describe("on 'remove' state events", function() {
      it("should unsubscribe the state's endpoints from the group",
      function(done) {
        diagram.states.on('remove', function() {
          assertUnsubscribed('jedi-a', jediA.endpoints);
          done();
        });

        diagram.states.remove('jedi-a');
      });
    });

    describe(".addState", function() {
      it("should subscribe the state's endpoints to the group", function() {
        endpoints.addState('ewok-a', ewokA);
        assertSubscribed('ewok-a', ewokA.endpoints);
      });
    });

    describe(".removeState", function() {
      it("should unsubscribe the state's endpoints from the group",
      function() {
        endpoints.removeState('jedi-a');
        assertUnsubscribed('jedi-a', jediA.endpoints);
      });
    });
  });

  describe(".DiagramViewConnections", function() {
    var connections;

    beforeEach(function() {
      connections = diagram.connections;

      // render to ensure the jsPlumb endpoints exist so we can create jsPlumb
      // endpoints between them
      diagram.render();
    });

    var assertAdded = function(sourceId, targetId) {
      var connection = connections.get(sourceId);
      assert(connection);
      assert.equal(connection.source, diagram.endpoints.get(sourceId));
      assert.equal(connection.target, diagram.endpoints.get(targetId));
    };

    var assertRemoved = function(sourceId) {
      assert(!connections.has(sourceId));
    };

    describe("on diagram endpoint 'add' events", function() {
      var subscribed;

      var MockDiagramViewConnections = DiagramViewConnections.extend({
        subscribeEndpoint: function(id, endpoint, options) {
          DiagramViewConnections
            .prototype
            .subscribeEndpoint
            .call(this, id, endpoint, options);

          subscribed[id] = endpoint;
        }
      });

      beforeEach(function() {
        subscribed = {};
        connections = new MockDiagramViewConnections(diagram);
      });

      it("should subscribe the endpoint", function(done) {
        var jediA4Model = new EndpointModel({id: 'jedi-a4'});
        var jediA4 = new EndpointView({
          state: diagram.states.get('jedi-a'),
          model: jediA4Model
        });

        diagram.endpoints.on('add', function() {
          assert.equal(subscribed['jedi-a4'], jediA4);
          done();
        });

        diagram.endpoints.add('jedi-a4', jediA4);
      });
    });

    describe("on diagram endpoint 'remove' events", function() {
      var unsubscribed;

      var MockDiagramViewConnections = DiagramViewConnections.extend({
        unsubscribeEndpoint: function(id, endpoint) {
          DiagramViewConnections
            .prototype
            .unsubscribeEndpoint
            .call(this, id, endpoint);

          unsubscribed[id] = endpoint;
        }
      });

      beforeEach(function() {
        unsubscribed = {};
        connections = new MockDiagramViewConnections(diagram);
      });

      it("should unsubscribe the endpoint", function(done) {
        var jediA3 = diagram.endpoints.get('jedi-a3');

        diagram.endpoints.on('remove', function(id, endpoint) {
          assert.equal(unsubscribed['jedi-a3'], jediA3);
          done();
        });

        diagram.endpoints.remove('jedi-a3');
      });
    });

    describe("on 'connection' jsPlumb events", function() {
      it("should add the connection if it does not yet exist",
      function(done) {
        jsPlumb.bind('connection', function() {
          assertAdded('jedi-a1', 'sith-a3');
          done();
        });

        diagram.render();
        jsPlumb.connect({
          source: diagram
            .endpoints
            .get('jedi-a1')
            .plumbEndpoint,

          target: diagram
            .endpoints
            .get('sith-a3')
            .plumbEndpoint
        });
      });
    });

    describe("on 'connectionDetached' jsPlumb events", function() {
      it("delegate the event to the relevant connection", function(done) {
        var jediA3 = diagram.endpoints.get('jedi-a3'),
            sithB2 = diagram.endpoints.get('sith-b2'),
            connection = diagram.connections.get('jedi-a3');

        connection.on('plumb:disconnect', function() { done(); });
        diagram.render();
        jsPlumb.detach(connection.plumbConnection);
      });
    });

    describe(".subscribeEndpoint", function() {
      beforeEach(function() {
        // Turn off endpoint add events so `subscribeEndpoint` isn't called
        // automatically (making testing difficult)
        diagram.endpoints.off('add');
      });

      it("should add a connection if the endpoint's model's target is set",
      function() {
        var jediA4Model = new EndpointModel({
          id: 'jedi-a4',
          target: {id: 'sith-a3'}
        });

        var jediA4 = new EndpointView({
          state: diagram.states.get('jedi-a'),
          model: jediA4Model
        });

        diagram.endpoints.add('jedi-a4', jediA4);

        connections.subscribeEndpoint('jedi-a4', jediA4, {render: false});
        assertAdded('jedi-a4', 'sith-a3');
      });

      it("should add a connection when the endpoint's target is set",
      function(done) {
        var jediA4Model = new EndpointModel({id: 'jedi-a4'});
        var jediA4 = new EndpointView({
          state: diagram.states.get('jedi-a'),
          model: jediA4Model
        });

        diagram.endpoints.add('jedi-a4', jediA4);
        connections.subscribeEndpoint('jedi-a4', jediA4, {render: false});

        jediA4Model.on('change:target', function() {
          assertAdded('jedi-a4', 'sith-a3');
          done();
        });

        jediA4Model.set(
          'target',
          diagram
            .endpoints
            .get('sith-a3')
            .model);
      });

      it("should remove a connection when an endpoint's target is unset",
      function(done) {
        var jediA3Model = diagram
          .endpoints
          .get('jedi-a3')
          .model;

        jediA3Model.on('change:target', function() {
          assertRemoved('jedi-a3');
          done();
        });

        jediA3Model.unset('target');
      });
    });

    describe(".unsubscribeEndpoint", function() {
      it("should remove a connection if the endpoint's model's target is set",
      function() {
        var jediA3 = diagram.endpoints.get('jedi-a3');
        connections.unsubscribeEndpoint('jedi-a3', jediA3);
        assertRemoved('jedi-a3');
      });
    });

    describe(".add", function() {
      it("should return the connection if it already exists", function() {
        assert.equal(
          connections.get('jedi-a3'),
          connections.add('jedi-a3', 'sith-b2'));
      });

      it("add a new connection with the associated endpoints", function() {
        connections.add('jedi-a1', 'sith-b1');
        assertAdded('jedi-a1', 'sith-b1');
      });
    });

    describe(".remove", function() {
      it("should destroy the connection", function() {
        var connection = connections.remove('jedi-a3');
        assert(connection.destroyed);
      });

      it("should remove the connection", function() {
        connections.remove('jedi-a3');
        assertRemoved('jedi-a3');
      });
    });
  });

  describe(".Diagram", function() {
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

    it("should keep track of all endpoints in the diagram", function() {
      assert.deepEqual(
        diagram.endpoints.keys(),
        ['jedi-a1', 'jedi-a2', 'jedi-a3',
         'jedi-b1', 'jedi-b2', 'jedi-b3',
         'sith-a1', 'sith-a2', 'sith-a3',
         'sith-b1', 'sith-b2', 'sith-b3']);
    });

    it("should keep track of all connections in the diagram", function() {
      assert.deepEqual(
        diagram.connections.keys(),
        ['jedi-a3']);  // connections are keyed by their source endpoint id
    });

    describe(".render", function() {
      it("should render its states", function() {
        diagram.states.each(function(s) { assert(!s.rendered); });
        diagram.render();
        diagram.states.each(function(s) { assert(s.rendered); });
      });

      it("should render its connections", function() {
        diagram.connections.each(function(s) { assert(!s.rendered); });
        diagram.render();
        diagram.connections.each(function(s) { assert(s.rendered); });
      });
    });
  });
});
