require('js-yaml');

module.exports = function (grunt) {
  grunt.loadNpmTasks('grunt-mocha-test');

  grunt.initConfig({
    paths: require('js_paths.yml'),
    mochaTest: {
      jsbox_apps: {
        src: ['<%= paths.tests.jsbox_apps %>'],
      }
    }
  });

  grunt.registerTask('test:jsbox_apps', [
    'mochaTest:jsbox_apps'
  ]);

  grunt.registerTask('test', [
    'mochaTest'
  ]);

  grunt.registerTask('default', [
    'test'
  ]);
};
