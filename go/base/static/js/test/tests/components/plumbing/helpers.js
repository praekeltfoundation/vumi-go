// go.components.plumbing.testHelpers)
// =====================================
// Contains example structures and data for plumbing component tests.

(function(exports) {
  var stateMachine = go.components.stateMachine,
      EndpointModel = stateMachine.EndpointModel,
      StateModel = stateMachine.StateModel,
      ConnectionModel = stateMachine.ConnectionModel,
      StateMachineModel = stateMachine.StateMachineModel;

  var plumbing = go.components.plumbing,
      Endpoint = plumbing.Endpoint,
      State = plumbing.State,
      Connection = plumbing.Connection,
      Diagram = plumbing.Diagram;

  // Mocks
  // -----

  var MockEndpoint = Endpoint.extend({
    destroy: function() {
      Endpoint.prototype.destroy.call(this);
      this.destroyed = true;
      return this;
    },

    render: function() {
      Endpoint.prototype.render.call(this);
      this.rendered = true;
      return this;
    }
  });

  var MockState = State.extend({
    destroy: function() {
      State.prototype.destroy.call(this);
      this.destroyed = true;
      return this;
    },

    render: function() {
      State.prototype.render.call(this);
      this.rendered = true;
      return this;
    }
  });

  var MockConnection = Connection.extend({
    destroy: function() {
      Connection.prototype.destroy.call(this);
      this.destroyed = true;
      return this;
    },

    render: function() {
      Connection.prototype.render.call(this);
      this.rendered = true;
      return this;
    }
  });

  // Simple diagram example
  // ----------------------

  var SimpleEndpoint = MockEndpoint.extend({});

  var SimpleState = MockState.extend({
    endpointType: SimpleEndpoint
  });

  var SimpleDiagram = Diagram.extend({stateType: SimpleState});

  var simpleModelData = {
    states: [{
      id: 'x',
      endpoints: [
        {id: 'x1'},
        {id: 'x2'},
        {id: 'x3'}]
    }, {
      id: 'y',
      endpoints: [
        {id: 'y1'},
        {id: 'y2'},
        {id: 'y3'}]
    }],

    connections: [{
      id: 'x3-y2',
      source: {id: 'x3'},
      target: {id: 'y2'}
    }]
  };

  var newSimpleDiagram = function() {
    return new SimpleDiagram({
      el: '#diagram',
      model: new StateMachineModel(simpleModelData)
    });
  };

  // Complex diagram example
  // -----------------------

  var ComplexStateModel = StateModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'left',
      relatedModel: EndpointModel
    }, {
      type: Backbone.HasMany,
      key: 'right',
      relatedModel: EndpointModel
    }]
  });

  var ComplexStateMachineModel = StateMachineModel.extend({
    relations: [{
      type: Backbone.HasMany,
      key: 'apples',
      relatedModel: ComplexStateModel
    }, {
      type: Backbone.HasMany,
      key: 'bananas',
      relatedModel: ComplexStateModel
    }, {
      type: Backbone.HasMany,
      key: 'leftToRight',
      relatedModel: ConnectionModel
    }, {
      type: Backbone.HasMany,
      key: 'rightToLeft',
      relatedModel: ConnectionModel
    }]
  });

  var ComplexEndpoint = MockEndpoint.extend(),
      LeftEndpoint = ComplexEndpoint.extend(),
      RightEndpoint = ComplexEndpoint.extend();

  var ComplexState = MockState.extend({
    endpointSchema: [
      {attr: 'left', type: LeftEndpoint},
      {attr: 'right', type: RightEndpoint}]
  });

  var AppleState = ComplexState.extend(),
      BananaState = ComplexState.extend();

  var ComplexConnection = MockConnection.extend(),
      LeftToRight = ComplexConnection.extend(),
      RightToLeft = ComplexConnection.extend();

  var ComplexDiagram = Diagram.extend({
    stateSchema: [
      {attr: 'apples', type: AppleState},
      {attr: 'bananas', type: BananaState}
    ],
    connectionSchema: [{
      attr: 'leftToRight',
      type: LeftToRight,
      sourceType: LeftEndpoint,
      targetType: RightEndpoint
    }, {
      attr: 'rightToLeft',
      type: RightToLeft,
      sourceType: RightEndpoint,
      targetType: LeftEndpoint
    }]
  });

  var complexModelData = {
    apples: [{
      id: 'a1',
      left: [{id: 'a1L1'}, {id: 'a1L2'}],
      right: [{id: 'a1R1'}, {id: 'a1R2'}]
    }, {
      id: 'a2',
      left: [{id: 'a2L1'}, {id: 'a2L2'}],
      right: [{id: 'a2R1'}, {id: 'a2R2'}]
    }],

    bananas: [{
      id: 'b1',
      left: [{id: 'b1L1'}, {id: 'b1L2'}],
      right: [{id: 'b1R1'}, {id: 'b1R2'}]
    }, {
      id: 'b2',
      left: [{id: 'b2L1'}, {id: 'b2L2'}],
      right: [{id: 'b2R1'}, {id: 'b2R2'}]
    }],

    leftToRight: [{
      id: 'a1L2-b2R2',
      source: {id: 'a1L2'},
      target: {id: 'b2R2'}
    }],

    rightToLeft: [{
      id: 'b1R2-a2L2',
      source: {id: 'b1R2'},
      target: {id: 'a2L2'}
    }]
  };

  var newComplexDiagram = function() {
    return new ComplexDiagram({
      el: '#diagram',
      model: new ComplexStateMachineModel(complexModelData)
    });
  };

  // Helper methods
  // --------------

  var setUp = function() {
    $('body').append("<div id='diagram'></div>");
  };

  var tearDown = function() {
    Backbone.Relational.store.reset();
    jsPlumb.unbind();
    jsPlumb.detachEveryConnection();
    jsPlumb.deleteEveryEndpoint();
    $('#diagram').remove();
  };

  _.extend(exports, {
    MockEndpoint: MockEndpoint,
    MockState: MockState,
    MockConnection: MockConnection,

    SimpleEndpoint: SimpleEndpoint,
    SimpleState: SimpleState,
    SimpleDiagram: SimpleDiagram,

    simpleModelData: simpleModelData,
    newSimpleDiagram: newSimpleDiagram,

    ComplexEndpoint: ComplexEndpoint,
    LeftEndpoint: LeftEndpoint,
    RightEndpoint: RightEndpoint,

    ComplexState: ComplexState,
    AppleState: AppleState,
    BananaState: BananaState,

    ComplexConnection: ComplexConnection,
    LeftToRight: LeftToRight,
    RightToLeft: RightToLeft,

    ComplexStateMachineModel: ComplexStateMachineModel,
    ComplexDiagram: ComplexDiagram,

    complexModelData: complexModelData,
    newComplexDiagram: newComplexDiagram,

    setUp: setUp,
    tearDown: tearDown
  });
})(go.components.plumbing.testHelpers = {});
