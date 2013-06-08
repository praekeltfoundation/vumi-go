describe("go.components.plumbing (states)", function() {
  var stateMachine = go.components.stateMachine,
      plumbing = go.components.plumbing;

  var testHelpers = plumbing.testHelpers,
      setUp = testHelpers.setUp,
      newComplexDiagram = testHelpers.newComplexDiagram,
      tearDown = testHelpers.tearDown;

  beforeEach(function() {
    setUp();
  });

  afterEach(function() {
    tearDown();
  });

  describe(".State", function() {
    var LeftEndpoint = testHelpers.LeftEndpoint,
        RightEndpoint = testHelpers.RightEndpoint;

    var diagram,
        a1;

    beforeEach(function() {
      diagram = newComplexDiagram();
      a1 = diagram.states.get('a1');
    });

    it("should set up the endpoints according to the schema", function() {
      var left = a1.endpoints.members.get('left'),
          right = a1.endpoints.members.get('right');

      assert.deepEqual(left.keys(), ['a1L1', 'a1L2']);
      assert.deepEqual(right.keys(), ['a1R1', 'a1R2']);

      left.each(function(e) { assert.instanceOf(e, LeftEndpoint); });
      right.each(function(e) { assert.instanceOf(e, RightEndpoint); });

      assert.deepEqual(
        a1.endpoints.keys(),
        ['a1L1', 'a1L2', 'a1R1', 'a1R2']);
    });

    describe(".render", function() {
      it("should add the state view to the diagram", function() {
        assert(_.isEmpty($('#diagram #a1').get()));
        a1.render();
        assert(!_.isEmpty($('#diagram #a1').get()));
      });

      it("shouldn't render duplicates", function() {
        a1.render();
        a1.render();
        assert.equal($('#diagram #a1').length, 1);
      });

      it("should render its endpoints", function() {
        a1.endpoints.each(function(e) { assert(!e.rendered); });
        a1.render();
        a1.endpoints.each(function(e) { assert(e.rendered); });
      });
    });
  });
});
