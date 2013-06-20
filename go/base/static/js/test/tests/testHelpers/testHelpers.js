// go.testHelpers
// ==============

(function(exports) {
  var elHasData = function(el, key, expectedVal) {
    var val = $(el).data(key);

    return _.isUndefined(expectedVal)
      ? !_.isUndefined(val)
      : val === expectedVal;
  };

  var oneElExists = function(selector) {
    return $(selector).length === 1;
  };

  var findByData = function(key, value) {
    return $(document)
      .find('*')
      .filter(function() { return elHasData(this, key, value); });
  };

  oneElExists.withData = function(key, value) {
    return findByData(key, value).length == 1;
  };

  var noElExists = function(selector) {
    return $(selector).length === 0;
  };

  noElExists.withData = function(key, value) {
    return findByData(key, value).length === 0;
  };

  _.extend(exports, {
    elHasData: elHasData,
    findByData: findByData,
    oneElExists: oneElExists,
    noElExists: noElExists
  });
})(go.testHelpers = {});
