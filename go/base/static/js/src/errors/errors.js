(function(exports) {
  var GoError = exports.GoError = function(message) {
    if (message) { this.message = message; }
  };

  // Creates a sub-error constructor from 'this' error constructor
  GoError.suberror = function(name, message) {
    var NewError = function() { GoError.call(this); };

    // provides the 'e instanceof SomeError' magic we need
    NewError.prototype = Object.create(this.prototype);

    // allow further sub-error creation
    NewError.suberror = GoError.suberror;

    NewError.name = name;
    if (message) { NewError.prototype.message = message; }

    return NewError;
  };

  GoError.prototype = _.extend(Object.create(Error.prototype), {
    name: 'GoError',
    toString: function() {
      return '['
        + this.name
        + (this.message ? ': ' + this.message : '')
        + ']';
    }
  });
})(go.errors = {});
