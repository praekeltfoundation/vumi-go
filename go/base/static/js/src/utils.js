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
  var maybeByName = function(nameOrObj, that) {
    return typeof nameOrObj === 'string'
      ? objectByName(nameOrObj, that)
      : nameOrObj;
  };

  var idOfModel = function(obj) {
    if (obj instanceof Backbone.Model) { return obj.id || obj.cid; }

    return obj.id
      ? obj.id
      : obj.uuid || obj;
  };

  var idOfView = function(obj) {
    return obj.uuid
      ? _(obj).result('uuid')
      : _(obj).result('id') || obj;
  };

  _.extend(exports, {
    merge: merge,
    functor: functor,
    objectByName: objectByName,
    maybeByName: maybeByName,
    idOfModel: idOfModel,
    idOfView: idOfView,
    highlightActiveLinks: highlightActiveLinks
  });
})(go.utils = {});
