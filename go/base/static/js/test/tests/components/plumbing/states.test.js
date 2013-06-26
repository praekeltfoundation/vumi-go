describe("go.components.plumbing.states", function() {
  var stateMachine = go.components.stateMachine;

  var plumbing = go.components.plumbing;

  var testHelpers = plumbing.testHelpers,
      setUp = testHelpers.setUp,
      newSimpleDiagram = testHelpers.newSimpleDiagram,
      newComplexDiagram = testHelpers.newComplexDiagram,
      tearDown = testHelpers.tearDown;

  beforeEach(function() {
    setUp();
  });

  afterEach(function() {
    tearDown();
  });

  describe(".StateView", function() {
    var LeftEndpointView = testHelpers.LeftEndpointView,
        RightEndpointView = testHelpers.RightEndpointView;

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

      left.each(function(e) { assert.instanceOf(e, LeftEndpointView); });
      right.each(function(e) { assert.instanceOf(e, RightEndpointView); });

      assert.deepEqual(
        a1.endpoints.keys(),
        ['a1L1', 'a1L2', 'a1R1', 'a1R2']);
    });

    describe(".render", function() {
      it("should add the state view to the diagram", function() {
        assert(_.isEmpty(diagram.$('[data-uuid="a1"]').get()));
        a1.render();
        assert(!_.isEmpty(diagram.$('[data-uuid="a1"]').get()));
      });

      it("shouldn't render duplicates", function() {
        a1.render();
        a1.render();
        assert.equal(diagram.$('[data-uuid="a1"]').length, 1);
      });

      it("should render its endpoints", function() {
        a1.endpoints.each(function(e) { assert(!e.rendered); });
        a1.render();
        a1.endpoints.each(function(e) { assert(e.rendered); });
      });
    });
  });

  describe(".StateViewCollection", function() {
    var diagram,
        collection;

    beforeEach(function() {
      diagram = newSimpleDiagram();
      collection = diagram.states.members.get('states');
    });

    describe(".remove", function() {
      beforeEach(function() {
        diagram.render();
      });

      it("should remove the state", function(done) {
        collection.on('remove', function() {
          assert(!collection.has('x'));
          done();
        });

        collection.remove('x');
      });

      it("should remove the state's endpoints", function(done) {
        var state = collection.get('x');

        collection.on('remove', function() {
          console.log(state.endpoints._keyIndices);
          assert(_.isEmpty(state.endpoints.values()));
          done();
        });

        collection.remove('x');
      });
    });
  });
});
