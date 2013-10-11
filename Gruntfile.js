require('js-yaml');
var path = require('path');

module.exports = function (grunt) {
  grunt.loadNpmTasks('grunt-bower-task');
  grunt.loadNpmTasks('grunt-contrib-jst');
  grunt.loadNpmTasks('grunt-mocha-test');
  grunt.loadNpmTasks('grunt-mocha-cov');
  grunt.loadNpmTasks('grunt-karma');

  grunt.initConfig({
    paths: require('./js_paths.yml'),
    bower: {
      install: {
        options: {
          layout: 'byComponent',
          cleanTargetDir: true,
          targetDir: 'go/base/static/vendor'
        }
      }
    },
    mochaTest: {
      jsbox_apps: {
        src: ['<%= paths.tests.jsbox_apps.spec %>'],
        reporter: 'dot',
      },
    },
    mochacov: {
      jsbox_apps: {
        files: ['<%= paths.tests.jsbox_apps.spec %>'],
        options: {
          reporter: 'mocha-lcov-reporter',
          output: 'mochacov.lcov',
          coverage: true
        },
      },
    },
    jst: {
      options: {
        processName: function(filename) {
          // We need to process the template names the same way Django
          // Pipelines does
          var dir = path.dirname(filename);
          dir = path.relative('go/base/static/templates', dir);

          var parts = dir.split('/');
          parts.push(path.basename(filename, '.jst'));

          return parts.join('_');
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
        reporters: ['dots', 'coverage'],
        configFile: 'karma.conf.js'
      }
    }
  });

  grunt.registerTask('test:jsbox_apps', [
    'mochaTest:jsbox_apps',
    'mochacov:jsbox_apps'
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
