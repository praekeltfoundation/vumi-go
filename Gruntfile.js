require('js-yaml');

module.exports = function (grunt) {
  grunt.loadNpmTasks('grunt-mocha-test');

  grunt.initConfig({
    paths: require('paths.yml'),
    mochaTest: {
      jsbox_apps: {
        src: ['<%= paths.jsbox_apps.tests %>'],
      }
    }
  });

  grunt.registerTask('test', [
    'mochaTest'
  ]);

  grunt.registerTask('default', [
    'test'
  ]);
};
