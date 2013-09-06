require('js-yaml');

module.exports = function (grunt) {
  grunt.loadNpmTasks('grunt-contrib-jst');
  grunt.loadNpmTasks('grunt-mocha-test');
  grunt.loadNpmTasks('grunt-karma');

  grunt.initConfig({
    paths: require('paths.yml'),
    mochaTest: {
      jsbox_apps: {
        src: ['<%= paths.tests.jsbox_apps.spec %>'],
      }
    },
    jst: {
      options: {
        processName: function(filename) {
          // process the template names the arb Django Pipelines way
          return filename
            .replace('go/base/static/templates/', '')
            .replace(/\..+$/, '')
            .split('/')
            .join('_');
        }
      },
      templates: {
        files: {
          "<%= paths.client.templates.dest %>": [
            "<%= paths.client.templates.src %>"
          ]
        }
      },
    },
    karma: {
      dev: {
        singleRun: true,
        reporters: ['dots'],
        configFile: 'karma.conf.js'
      }
    }
  });

  grunt.registerTask('test:jsbox_apps', [
    'mochaTest:jsbox_apps'
  ]);

  grunt.registerTask('test:client', [
    'jst:templates',
    'karma:dev'
  ]);

  grunt.registerTask('test', [
    'test:jsbox_apps',
    'test:client'
  ]);

  grunt.registerTask('default', [
    'test'
  ]);
};
