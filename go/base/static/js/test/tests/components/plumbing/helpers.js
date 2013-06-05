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
