describe("go.errors", function() {
  describe(".GoError", function() {
    var GoError = go.errors.GoError;

    it("should allow prototype chained sub-error creation", function() {
      var SubError = GoError.subtype('SubError'),
          SubSubError = SubError.subtype('SubSubError'),
          fn = function() { throw new SubSubError(); };

      assert.throws(fn, Error);
      assert.throws(fn, GoError);
      assert.throws(fn, SubError);
      assert.throws(fn, SubSubError);
    });

    it("should stringify errors", function() {
      var SubError = GoError.subtype('SubError');

      assert.equal('' + new GoError('Aaah!'), '[GoError: Aaah!]');
      assert.equal('' + new GoError(), '[GoError]');

      assert.equal('' + new SubError('Aaah!'), '[SubError: Aaah!]');
      assert.equal('' + new SubError(), '[SubError]');
    });

    it("should use a default message if no message is provided", function() {
      var SubError = GoError.subtype('SubError', 'Aaah!');
      assert.equal(new GoError().message, '');
      assert.equal(new SubError().message, 'Aaah!');
    });
  });
});
