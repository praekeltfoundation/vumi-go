describe("go.components.grid.Grid", function() {
  var Grid = go.components.grid.Grid;

  describe(".reset", function() {
    it("should reset the grid's state", function() {
      var grid = new Grid({numCols: 3});

      grid.add({
        width: 23,
        height: 23
      });

      var next = grid.next({
        width: 23,
        height: 23
      });

      grid.reset();
      assert.notDeepEqual(next, grid.next({
        width: 23,
        height: 23
      }));
    });
  });

  describe(".add", function() {
    it("should add a cell to the grid", function() {
      var grid = new Grid({numCols: 3});
      grid.numCols = 3;

      assert.deepEqual([{
        width: 10,
        height: 20
      }, {
        width: 30,
        height: 40
      }, {
        width: 50,
        height: 60
      }, {
        width: 70,
        height: 80
      }, {
        width: 90,
        height: 100
      }, {
        width: 110,
        height: 120
      }, {
        width: 130,
        height: 140
      }].map(grid.add.bind(grid)), [{
        x: 0,
        y: 0
      }, {
        x: 10,
        y: 0
      }, {
        x: 40,
        y: 0
      }, {
        x: 0,
        y: 40
      }, {
        x: 70,
        y: 40
      }, {
        x: 160,
        y: 40
      }, {
        x: 0,
        y: 140
      }]);
    });
  });

  describe(".next", function() {
    it("should return the next cell", function() {
      var grid = new Grid({numCols: 3});
      grid.numCols = 3;

      assert.deepEqual(grid.next({
        width: 10,
        height: 20
      }), {
        x: 10,
        y: 0
      });

      grid.add({
        width: 10,
        height: 20
      });

      assert.deepEqual(grid.next({
        width: 30,
        height: 40
      }), {
        x: 40,
        y: 0
      });
    });
  });
});
