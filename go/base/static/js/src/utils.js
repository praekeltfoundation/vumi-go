(function(exports) {
  exports.Extendable = function () {};

  // Backbone has an internal `extend()` function which it assigns to its
  // structures. We need this function, so we arbitrarily choose
  // `Backbone.Model`, since it has the `extend()` function we are looking for.
  exports.Extendable.extend = Backbone.Model.extend;
})(go.utils = {});
