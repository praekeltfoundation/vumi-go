// go.utils
// ========
// Utilities and helpers for Go

(function(exports) {
  // Merges the passed in objects together into a single object
  var merge = exports.merge = function() {
    Array.prototype.unshift.call(arguments, {});
    return _.extend.apply(this, arguments);
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

  exports.highlightActiveLinks = function() {
    // find links in the document that match the current
    // windows url and set them as active.

    var loc = window.location;
    var url = loc.href;
    url = url.replace(loc.host, '').replace(loc.protocol + '//', '');

    $('a[href="' + url + '"]').addClass('active');
  };
})(go.utils = {});
