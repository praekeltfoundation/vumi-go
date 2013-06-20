// go.components.plumbing.testHelpers
// ==================================
// Contains example structures and data for plumbing component tests.

(function(exports) {
  var stateMachine = go.components.stateMachine,
      EndpointModel = stateMachine.EndpointModel,
      StateModel = stateMachine.StateModel,
      ConnectionModel = stateMachine.ConnectionModel,
      StateMachineModel = stateMachine.StateMachineModel;

  var plumbing = go.components.plumbing,
      EndpointView = plumbing.EndpointView,
      StateView = plumbing.StateView,
      ConnectionView = plumbing.ConnectionView,
      DiagramView = plumbing.DiagramView;

  // Mocks
  // -----

  var MockEndpointView = EndpointView.extend({
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

  var MockStateView = StateView.extend({
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

  var MockConnectionView = ConnectionView.extend({
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

  // Simple diagram example
  // ----------------------

  var SimpleEndpointView = MockEndpointView.extend({});

  var SimpleStateView = MockStateView.extend({
    endpointType: SimpleEndpointView
  });

  var SimpleDiagramView = DiagramView.extend({stateType: SimpleStateView});

  var simpleModelData = {
    states: [{
      uuid: 'x',
      endpoints: [
        {uuid: 'x1'},
        {uuid: 'x2'},
        {uuid: 'x3'}]
    }, {
      uuid: 'y',
      endpoints: [
        {uuid: 'y1'},
        {uuid: 'y2'},
        {uuid: 'y3'}]
    }],

    connections: [{
      uuid: 'x3-y2',
      source: {uuid: 'x3'},
      target: {uuid: 'y2'}
    }]
  };

  var newSimpleDiagram = function() {
    return new SimpleDiagramView({
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

  var ComplexEndpointView = MockEndpointView.extend(),
      LeftEndpointView = ComplexEndpointView.extend(),
      RightEndpointView = ComplexEndpointView.extend();

  var ComplexStateView = MockStateView.extend({
    endpointSchema: [
      {attr: 'left', type: LeftEndpointView},
      {attr: 'right', type: RightEndpointView}]
  });

  var AppleStateView = ComplexStateView.extend(),
      BananaStateView = ComplexStateView.extend();

  var ComplexConnectionView = MockConnectionView.extend(),
      LeftToRightView = ComplexConnectionView.extend(),
      RightToLeftView = ComplexConnectionView.extend();

  var ComplexDiagramView = DiagramView.extend({
    stateSchema: [
      {attr: 'apples', type: AppleStateView},
      {attr: 'bananas', type: BananaStateView}
    ],
    connectionSchema: [{
      attr: 'leftToRight',
      type: LeftToRightView,
      sourceType: LeftEndpointView,
      targetType: RightEndpointView
    }, {
      attr: 'rightToLeft',
      type: RightToLeftView,
      sourceType: RightEndpointView,
      targetType: LeftEndpointView
    }]
  });

  var complexModelData = {
    apples: [{
      uuid: 'a1',
      left: [{uuid: 'a1L1'}, {uuid: 'a1L2'}],
      right: [{uuid: 'a1R1'}, {uuid: 'a1R2'}]
    }, {
      uuid: 'a2',
      left: [{uuid: 'a2L1'}, {uuid: 'a2L2'}],
      right: [{uuid: 'a2R1'}, {uuid: 'a2R2'}]
    }],

    bananas: [{
      uuid: 'b1',
      left: [{uuid: 'b1L1'}, {uuid: 'b1L2'}],
      right: [{uuid: 'b1R1'}, {uuid: 'b1R2'}]
    }, {
      uuid: 'b2',
      left: [{uuid: 'b2L1'}, {uuid: 'b2L2'}],
      right: [{uuid: 'b2R1'}, {uuid: 'b2R2'}]
    }],

    leftToRight: [{
      uuid: 'a1L2-b2R2',
      source: {uuid: 'a1L2'},
      target: {uuid: 'b2R2'}
    }],

    rightToLeft: [{
      uuid: 'b1R2-a2L2',
      source: {uuid: 'b1R2'},
      target: {uuid: 'a2L2'}
    }]
  };

  var newComplexDiagram = function() {
    return new ComplexDiagramView({
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
    MockEndpointView: MockEndpointView,
    MockStateView: MockStateView,
    MockConnectionView: MockConnectionView,

    SimpleEndpointView: SimpleEndpointView,
    SimpleStateView: SimpleStateView,
    SimpleDiagramView: SimpleDiagramView,

    simpleModelData: simpleModelData,
    newSimpleDiagram: newSimpleDiagram,

    ComplexEndpointView: ComplexEndpointView,
    LeftEndpointView: LeftEndpointView,
    RightEndpointView: RightEndpointView,

    ComplexStateView: ComplexStateView,
    AppleStateView: AppleStateView,
    BananaStateView: BananaStateView,

    ComplexConnectionView: ComplexConnectionView,
    LeftToRightView: LeftToRightView,
    RightToLeftView: RightToLeftView,

    ComplexStateMachineModel: ComplexStateMachineModel,
    ComplexDiagramView: ComplexDiagramView,

    complexModelData: complexModelData,
    newComplexDiagram: newComplexDiagram,

    setUp: setUp,
    tearDown: tearDown
  });
})(go.components.plumbing.testHelpers = {});
