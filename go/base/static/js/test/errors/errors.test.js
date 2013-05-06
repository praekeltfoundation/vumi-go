describe("go.errors", function() {
  describe(".GoError", function() {
    var GoError = go.errors.GoError;

    it("should allow prototype chained sub-error creation", function() {
      var SubError = GoError.suberror('SubError'),
          SubSubError = SubError.suberror('SubSubError'),
          fn = function() { throw new SubSubError(); };

      assert.Throw(fn, Error);
      assert.Throw(fn, GoError);
      assert.Throw(fn, SubError);
      assert.Throw(fn, SubSubError);
    });

    it("should stringify errors", function() {
      assert.equal('' + new GoError('Aaah!'), '[GoError: Aaah!]');
      assert.equal('' + new GoError(), '[GoError]');
    });

    it("should use a default message if no message is provided", function() {
      var SubError = GoError.suberror('SubError', 'Aaah!');
      assert.equal(new GoError().message, '');
      assert.equal(new SubError().message, 'Aaah!');
    });
  });
});
