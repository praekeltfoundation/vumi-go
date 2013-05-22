// go.components.structures
// ========================
// Reusable, generic structures for Go

(function(exports) {
  var merge = go.utils.merge;

  // Acts as a 'base' for class-like objects which can be extended (with the
  // prototype chain set up automatically)
  exports.Extendable = function () {};

  exports.Extendable.extend = function() {
    // Backbone has an internal `extend()` function which it assigns to its
    // structures. We need this function, so we arbitrarily choose
    // `Backbone.Model`, since it has the function we are looking for.
    return Backbone.Model.extend.call(this, merge.apply(this, arguments));
  };
})(go.components.structures = {});
