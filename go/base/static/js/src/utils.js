// go.utils
// ========
// Utilities and helpers for Go

(function(exports) {
  // Merges the passed in objects together into a single object
  var merge = exports.merge = function() {
    Array.prototype.unshift.call(arguments, {});
    return _.extend.apply(this, arguments);
  };

  // Acts as a 'base' for class-like objects which can be extended (with the
  // prototype chain set up automatically)
  exports.Extendable = function () {};

  exports.Extendable.extend = function() {
    // Backbone has an internal `extend()` function which it assigns to its
    // structures. We need this function, so we arbitrarily choose
    // `Backbone.Model`, since it has the function we are looking for.
    return Backbone.Model.extend.call(this, merge.apply(this, arguments));
  };

  // Returns the internal prototype ([[Prototype]]) of the instance's internal
  // prototype (One step up in the prototype chain, and thus the 'super'
  // prototype).
  //
  // If `propName` is specified, a property on 'super' prototype is returned.
  // If the property is a function, the function is bound to the instance.
  exports.parent = function(that, propName) {
    var proto = Object.getPrototypeOf(Object.getPrototypeOf(that)),
        prop;

    if (!propName) { return proto; }

    prop = proto[propName];
    return typeof prop === "function"
      ? prop.bind(that)
      : prop;
  };

  // Determine the unique id of a pair from the ids of its components
  exports.pairId = function(idA, idB) {
    return [idA, idB]
      .sort()
      .join('-');
  };
})(go.utils = {});
