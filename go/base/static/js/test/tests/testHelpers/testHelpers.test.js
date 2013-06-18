describe("go.testHelpers", function() {
  var testHelpers = go.testHelpers,
      unloadTemplates = testHelpers.unloadTemplates;

  describe(".loadTemplate", function() {
    var loadTemplate = testHelpers.loadTemplate;

    afterEach(function() {
      unloadTemplates();
    });

    it("should load the template in the same way Django pipelines does",
    function() {
      loadTemplate('tests/testHelpers/dummy.jst', './');
      assert.equal(
        JST.tests_testHelpers_dummy({name: 'Anakin'}),
        'Hi! I am a dummy template. My name is Anakin.\n');
    });
  });

  describe("unloadTemplate", function() {
    it("should empty the global template holder object", function() {
      JST.thing = 23;
      unloadTemplates();
      assert(_.isEmpty(JST));
    });
  });
});
