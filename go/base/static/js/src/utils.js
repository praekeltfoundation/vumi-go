// go.utils
// ========
// Utilities and helpers for Go

(function(exports) {
  // Merges the passed in objects together into a single object
  var merge = function() {
    Array.prototype.unshift.call(arguments, {});
    return _.extend.apply(this, arguments);
  };

  var highlightActiveLinks = function() {
    // find links in the document that match the current
    // windows url and set them as active.

    var loc = window.location;
    var url = loc.href;
    url = url.replace(loc.host, '').replace(loc.protocol + '//', '');

    $('a[href="' + url + '"]').addClass('active');
  };

  // Returns `obj` if it is a function, otherwise wraps `obj` in a function and
  // returns the function
  var functor = function(obj) {
    return typeof obj === 'function'
      ? obj
      : function() { return obj; };
  };

  // Returns an object given a 'dotted' name like `thing.subthing.Subthing`,
  // and an optional context to look for the object in
  var objectByName = function(name, that) {
    return _(name.split( '.' )).reduce(
      function(obj, propName) { return obj[propName]; },
      that || window);
  };

  // If given a string, gets the object by name, otherwise just returns what
  // it was given
  var ensureObject = function(nameOrObj, that) {
    return typeof nameOrObj === 'string'
      ? objectByName(nameOrObj, that)
      : nameOrObj;
  };

  _.extend(exports, {
    merge: merge,
    functor: functor,
    objectByName: objectByName,
    ensureObject: ensureObject,
    highlightActiveLinks: highlightActiveLinks
  });
})(go.utils = {});
