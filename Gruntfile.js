require('js-yaml');
var path = require('path');

module.exports = function (grunt) {
  grunt.loadNpmTasks('grunt-bower-task');
  grunt.loadNpmTasks('grunt-contrib-jst');
  grunt.loadNpmTasks('grunt-mocha-cli');
  grunt.loadNpmTasks('grunt-mocha-cov');
  grunt.loadNpmTasks('grunt-karma');
  grunt.loadNpmTasks('grunt-exec');
  grunt.loadNpmTasks('grunt-contrib-less');
  grunt.loadNpmTasks('grunt-contrib-watch');
  grunt.loadNpmTasks('grunt-uncss');

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
    mochacli: {
      jsbox_apps: {
        options: {reporter: 'dot'},
        src: ['<%= paths.tests.jsbox_apps.spec %>']
      },
    },
    mochacov: {
      jsbox_apps: {
        options: {
          files: ['<%= paths.tests.jsbox_apps.spec %>'],
          reporter: 'mocha-lcov-reporter',
          output: 'mochacov.lcov',
          coverage: true
        }
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
    },
    exec: {
      'fonts': {
        cmd: [
          'mkdir -p `dirname <%= paths.client.fonts.vendor.dest %>`',
          ' && ',
          'cp <%= paths.client.fonts.vendor.src %> ',
          '   <%= paths.client.fonts.vendor.dest %>'
        ].join('')
      }
    },
    less: {
      dev: {
        options: {
          paths: ["go/base/static/css"],
          sourceMap: true,
          sourceMapFilename: "go/base/static/css/vumigo.css.map",
          sourceMapBasepath: "go/base/static/css/"
        },
        files: {
          "go/base/static/css/vumigo.css": "go/base/static/css/vumigo.less"
        },
      }
    },
    watch: {
      less: {
        files: ['go/base/static/css/*.less'],
        tasks: ['less']
      }
    },
    uncss: {
      dist: {
        files: {
          'go/base/static/css/tidy.css': ['http://localhost:8000/conversations/', 'http://localhost:8000/contacts/people/', 'http://localhost:8000/help/', 'http://localhost:8000/account/details/', 'http://localhost:8000/account/billing/', 'http://localhost:8000/wizard/create/', 'http://localhost:8000/routing/', 'http://localhost:8000/channels/', 'http://localhost:8000/routers/']
        }
      }
    }
  });

  grunt.registerTask('test:jsbox_apps', [
    'mochacli:jsbox_apps',
    'mochacov:jsbox_apps'
  ]);

  grunt.registerTask('test:client', [
    'jst:templates',
    'karma:dev'
  ]);

  grunt.registerTask('vendor', [
    'bower',
    'exec:fonts'
  ]);

  grunt.registerTask('test', [
    'test:jsbox_apps',
    'test:client'
  ]);

  grunt.registerTask('default', [
    'test'
  ]);

};
