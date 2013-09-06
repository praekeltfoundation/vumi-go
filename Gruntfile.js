require('js-yaml');

module.exports = function (grunt) {
  grunt.loadNpmTasks('grunt-mocha-test');
  grunt.loadNpmTasks('grunt-karma');

  grunt.initConfig({
    paths: require('paths.yml'),
    mochaTest: {
      jsbox_apps: {
        src: ['<%= paths.tests.jsbox_apps.spec %>'],
      }
    },
    karma: {
      dev: {
        configFile: 'karma.conf.js',
        singleRun: true,
        reporters: 'progress'
      }
    },
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
