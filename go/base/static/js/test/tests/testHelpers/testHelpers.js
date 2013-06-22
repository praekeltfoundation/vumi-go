// go.testHelpers
// ==============

(function(exports) {
  var assertFails = function(fn) { assert.throws(fn, chai.AssertionError); };

  var oneElExists = function(selector) {
    return $(selector).length === 1;
  };

  var noElExists = function(selector) {
    return $(selector).length === 0;
  };

  var attrsOfModel = function(obj) {
    var attrs = obj instanceof Backbone.Model
      ? obj.toJSON()
      : obj;

    // Backbone.rpc adds an extra `_rpcId` attribute which isn't part of
    // our model attributes. We need to exclude it for equality testing.
    return _(attrs).omit('_rpcId');
  };

  var assertModelAttrs = function(model, attrs) {
    assert.deepEqual(attrsOfModel(model), attrs);
  };

  _.extend(exports, {
    assertFails: assertFails,
    oneElExists: oneElExists,
    noElExists: noElExists,
    attrsOfModel: attrsOfModel,
    assertModelAttrs: assertModelAttrs
  });
})(go.testHelpers = {});
