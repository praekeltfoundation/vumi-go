(function(exports) {
  var Extendable = go.components.structures.Extendable;


  var Grid = Extendable.extend({
    constructor: function(options) {
      this.numCols = options.numCols;
      this.reset();
    },

    reset: function() {
      this.cell = {
        x: 0,
        y: 0,
        colIdx: 0,
        rowHeight: 0
      };
    },

    add: function(dims) {
      var cell = this.cell;
      this.cell = this._next(dims);

      return {
        x: cell.x,
        y: cell.y
      };
    },

    next: function(dims) {
      var cell = this._next(dims);

      return {
        x: cell.x,
        y: cell.y
      };
    },

    _next: function(dims) {
      return this.cell.colIdx + 1 < this.numCols
        ? this._nextCol(dims)
        : this._nextRow(dims);
    },

    _nextCol: function(dims) {
      return {
        x: this.cell.x + dims.width,
        y: this.cell.y,
        colIdx: this.cell.colIdx + 1,
        rowHeight: Math.max(dims.height, this.cell.rowHeight)
      };
    },

    _nextRow: function(dims) {
      return {
        x: 0,
        y: this.cell.y + this.cell.rowHeight,
        colIdx: 0,
        rowHeight: dims.height
      };
    }
  });


  exports.Grid = Grid;
})(go.components.grid = {});
