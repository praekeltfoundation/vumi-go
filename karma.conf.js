require('js-yaml');

module.exports = function(config) {
  var paths = require('./go/js_paths.yml');

  var files_to_cover = [].concat(
      paths.client.scripts.go,
      paths.tests.client.spec
  );

  var preprocessors = {};
  files_to_cover.forEach(function (file) {
      preprocessors[file] = ['coverage'];
  })

  config.set({
    files: [].concat(
      paths.client.styles.vendor,
      paths.client.styles.go,
      paths.client.templates.dest,
      paths.client.scripts.vendor,
      paths.client.scripts.go,
      paths.tests.client.vendor,
      paths.tests.client.spec
    ),

    preprocessors: preprocessors,
    coverageReporter: {
      type : 'lcov',
      dir : 'coverage/'
    },

    browsers: ['PhantomJS'],
    frameworks: ['mocha'],

    plugins: [
      'karma-mocha',
      'karma-phantomjs-launcher',
      'karma-coverage'
    ]
  });
};
