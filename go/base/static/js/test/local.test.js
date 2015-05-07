describe("go.local", function() {
  afterEach(function() {
    localStorage.clear();
  });

  describe(".set", function() {
    it("should stringify and set values", function() {
      assert(!('foo' in localStorage));
      go.local.set('foo', {bar: 23});
      assert.deepEqual(JSON.parse(localStorage.foo), {bar: 23});
    });
  });

  describe(".get", function() {
    it("should return null for non-existent items", function() {
      assert(!('foo' in localStorage));
      localStorage.bar = JSON.stringify({baz: 21});

      assert.strictEqual(go.local.get('foo'), null);
      assert.notStrictEqual(go.local.get('bar'), null);
    });

    it("should support default values", function() {
      assert(!('foo' in localStorage));
      localStorage.bar = JSON.stringify({baz: 21});

      assert.strictEqual(go.local.get('foo', 23), 23);
      assert.notStrictEqual(go.local.get('bar', 23), 23);
    });

    it("should retrieve and parse values", function() {
      localStorage.foo = JSON.stringify({bar: 23});
      assert.deepEqual(go.local.get('foo'), {bar: 23});
    });
  });
});
