describe("go.components.plumbing (diagrams)", function() {
  var stateMachine = go.components.stateMachine,
      EndpointModel = stateMachine.EndpointModel,
      StateModel = stateMachine.StateModel,
      StateMachineModel = stateMachine.StateMachineModel;

  var plumbing = go.components.plumbing,
      EndpointView = plumbing.EndpointView,
      StateView = plumbing.StateView,
      ConnectionView = plumbing.ConnectionView,
      DiagramView = plumbing.DiagramView;

  var ToyEndpointView = EndpointView.extend({
    destroy: function() {
      EndpointView.prototype.destroy.call(this);
      this.destroyed = true;
      return this;
    },

    render: function() {
      EndpointView.prototype.render.call(this);
      this.rendered = true;
      return this;
    }
  });

  var JediEndpointView  = ToyEndpointView.extend(),
      SithEndpointView  = ToyEndpointView.extend();

  var ToyStateView = StateView.extend({
    destroy: function() {
      StateView.prototype.destroy.call(this);
      this.destroyed = true;
      return this;
    },

    render: function() {
      StateView.prototype.render.call(this);
      this.rendered = true;
      return this;
    }
  });

  var JediStateView = ToyStateView.extend({endpointType: JediEndpointView}),
      SithStateView = ToyStateView.extend({endpointType: SithEndpointView});

  var ToyConnectionView = ConnectionView.extend({
    destroy: function() {
      ConnectionView.prototype.destroy.call(this);
      this.destroyed = true;
      return this;
    },

    render: function() {
      ConnectionView.prototype.render.call(this);
      this.rendered = true;
      return this;
    }
  });

  var JedisToSithsView = ToyConnectionView.extend(),
      SithsToJedisView = ToyConnectionView.extend();

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
      type: Backbone.HasMany,
      key: 'jedisToSiths',
      relatedModel: 'go.components.stateMachine.ConnectionModel'
    }, {
      type: Backbone.HasMany,
      key: 'sithsToJedis',
      relatedModel: 'go.components.stateMachine.ConnectionModel'
    }]
  });

  var ToyDiagramView = DiagramView.extend({
    stateSchema: [
      {attr: 'jedis', type: JediStateView},
      {attr: 'siths', type: SithStateView}
    ],
    connectionSchema: [{
      attr: 'jedisToSiths',
      type: JedisToSithsView,
      sourceType: JediEndpointView,
      targetType: SithEndpointView
    }, {
      attr: 'sithsToJedis',
      type: SithsToJedisView,
      sourceType: SithEndpointView,
      targetType: JediEndpointView
    }]
  });

  var diagram;

  beforeEach(function() {
    // Sorry, I know its a very bad example. Siths and Jedis are state types.
    // ToyStateMachineModel contains two collections of states: one for the
    // sith states, one for jedi states. It also contains two collections of
    // connections: one for jedi-to-sith connections and one for sith-to-jedi
    // connections. I have no idea what the connections are supposed to mean
    // (shifts in sides of the force?), so don't try look into it :).

    var model = new ToyStateMachineModel({
      jedis: [{
        id: 'jediA',
        endpoints: [
          {id: 'jediA1'},
          {id: 'jediA2'},
          {id: 'jediA3'}]
      }, {
        id: 'jediB',
        endpoints: [
          {id: 'jediB1'},
          {id: 'jediB2'},
          {id: 'jediB3'}]
      }],

      siths: [{
        id: 'sithA',
        endpoints: [
          {id: 'sithA1'},
          {id: 'sithA2'},
          {id: 'sithA3'}]
      }, {
        id: 'sithB',
        endpoints: [
          {id: 'sithB1'},
          {id: 'sithB2'},
          {id: 'sithB3'}]
      }],
      
      jedisToSiths: [{
        id: 'jediA3-sithB2',
        source: {id: 'jediA3'},
        target: {id: 'sithB2'}
      }],

      sithsToJedis: [{
        id: 'sithA3-jediB2',
        source: {id: 'sithA3'},
        target: {id: 'jediB2'}
      }]
    });

    $('body').append("<div id='diagram'></div>");
    diagram = new ToyDiagramView({el: '#diagram', model: model});
  });

  afterEach(function() {
    Backbone.Relational.store.reset();
    jsPlumb.unbind();
    jsPlumb.detachEveryConnection();
    jsPlumb.deleteEveryEndpoint();
    $('#diagram').remove();
  });

  describe(".DiagramViewEndpoints", function() {
    var DiagramViewEndpoints = plumbing.DiagramViewEndpoints;

    var endpoints,
        jediA,
        ewokA;

    var assertSubscribed = function(id, subscriber) {
      assert(endpoints.members.has(id));
      assert.includeMembers(endpoints.keys(), subscriber.keys());
    };

    var assertUnsubscribed = function(id, subscriber) {
      assert(!endpoints.members.has(id));
      subscriber.eachItem(function(id) { assert(!endpoints.has(id)); });
    };

    beforeEach(function() {
      endpoints = new DiagramViewEndpoints(diagram);

      var ewokModelA = new StateModel({
        id: 'ewok-a',
        endpoints: [{id: 'ewok-a1'}, {id: 'ewok-a2'}]
      });

      ewokA = new StateView({diagram: diagram, model: ewokModelA});
      jediA = diagram.states.get('jediA');
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
          assertUnsubscribed('jediA', jediA.endpoints);
          done();
        });

        diagram.states.remove('jediA');
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
        endpoints.removeState('jediA');
        assertUnsubscribed('jediA', jediA.endpoints);
      });
    });
  });

  describe(".DiagramViewConnectionCollection", function() {
    var DiagramViewConnectionCollection
      = plumbing.DiagramViewConnectionCollection;

    var connections;

    beforeEach(function() {
      connections = new DiagramViewConnectionCollection({
        view: diagram,
        attr: 'sithsToJedis',
        sourceType: SithEndpointView,
        targetType: JediEndpointView
      });
    });

    describe(".accepts", function() {
      it("should determine whether the source and target are belong",
      function() {
        assert(connections.accepts(
          diagram.endpoints.get('sithA3'),
          diagram.endpoints.get('jediB2')));

        assert(!connections.accepts(
          diagram.endpoints.get('jediA3'),
          diagram.endpoints.get('sithB2')));
      });
    });
  });

  describe(".DiagramViewConnections", function() {
    var DiagramViewConnections = plumbing.DiagramViewConnections;

    var connections,
        jedisToSiths;

    beforeEach(function() {
      connections = diagram.connections;
      jedisToSiths = connections.members.get('jedisToSiths');
    });

    describe(".determineCollection", function() {
      it("should determine which collection a source and target belong to",
      function() {
        assert.equal(
          connections.members.get('jedisToSiths'),
          connections.determineCollection(
            diagram.endpoints.get('jediA1'),
            diagram.endpoints.get('sithB1')));

        assert.equal(
          connections.members.get('sithsToJedis'),
          connections.determineCollection(
            diagram.endpoints.get('sithA1'),
            diagram.endpoints.get('jediB1')));
      });
    });

    describe("on 'connection' jsPlumb events", function() {
      beforeEach(function() {
        // render the diagram to ensure the jsPlumb endpoints are drawn
        diagram.render();
      }); 

      it("should add a connection model and its view if they do not yet exist",
      function(done) {
        var jediA1 = diagram.endpoints.get('jediA1'),
            sithB1 = diagram.endpoints.get('sithB1');

        connections.on('add', function(id, connection) {

          // check that the model was added
          assert.equal(connection.model.get('source'), jediA1.model);
          assert.equal(connection.model.get('target'), sithB1.model);
          assert.equal(
            connection.model,
            jedisToSiths.models.get('jediA1-sithB1'));

          // check that the view was added
          assert.equal(connection.source, jediA1);
          assert.equal(connection.target, sithB1);
          assert.equal(connection, connections.get('jediA1-sithB1'));

          done();
        });

        jsPlumb.connect({
          source: jediA1.plumbEndpoint,
          target: sithB1.plumbEndpoint
        });
      });
    });

    describe("on 'connectionDetached' jsPlumb events", function() {
      beforeEach(function() {
        // render the diagram and connections to ensure the jsPlumb endpoints
        // and connections are drawn
        diagram.render();
      }); 

      it("should remove the connection model and its view if they still exist",
      function(done) {
        var jediA3 = diagram.endpoints.get('jediA3'),
            sithB2 = diagram.endpoints.get('sithB2'),
            jediA3SithB2 = connections.get('jediA3-sithB2');

        // make sure that the connection did initially exist
        assert(jediA3SithB2);

        connections.on('remove', function(id, connection) {

          // check that the model was removed
          assert(!jedisToSiths.models.get('jediA3-sithB2'));
          assert.equal(connection.model.get('source'), jediA3.model);
          assert.equal(connection.model.get('target'), sithB2.model);

          // check that the view was removed
          assert(!connections.has('jediA3-sithB2'));
          assert.equal(jediA3SithB2, connection);

          done();
        });

        jsPlumb.detach(jediA3SithB2.plumbConnection);
      });
    });
  });

  describe(".Diagram", function() {
    it("should keep track of all endpoints in the diagram", function() {
      assert.deepEqual(
        diagram.endpoints.keys(),
        ['jediA1', 'jediA2', 'jediA3',
         'jediB1', 'jediB2', 'jediB3',
         'sithA1', 'sithA2', 'sithA3',
         'sithB1', 'sithB2', 'sithB3']);
    });

    it("should set up the connections according to the schema", function() {
      var jedisToSiths = diagram.connections.members.get('jedisToSiths'),
          sithsToJedis = diagram.connections.members.get('sithsToJedis');

      assert.deepEqual(jedisToSiths.keys(), ['jediA3-sithB2']);
      assert.deepEqual(sithsToJedis.keys(), ['sithA3-jediB2']);

      jedisToSiths.each(
        function(e) { assert.instanceOf(e, JedisToSithsView); });

      sithsToJedis.each(
        function(e) { assert.instanceOf(e, SithsToJedisView); });

      assert.deepEqual(
        diagram.connections.keys(),
        ['jediA3-sithB2', 'sithA3-jediB2']);
    });

    it("should set up the states according to the schema", function() {
      var jedis = diagram.states.members.get('jedis'),
          siths = diagram.states.members.get('siths');

      assert.deepEqual(jedis.keys(), ['jediA', 'jediB']);
      assert.deepEqual(siths.keys(), ['sithA', 'sithB']);

      jedis.each(function(e) { assert.instanceOf(e, JediStateView); });
      siths.each(function(e) { assert.instanceOf(e, SithStateView); });

      assert.deepEqual(
        diagram.states.keys(),
        ['jediA', 'jediB', 'sithA', 'sithB']);
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
