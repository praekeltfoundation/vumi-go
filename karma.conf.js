require('js-yaml');

module.exports = function(config) {
  var paths = require('js_paths.yml');

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

    browsers: ['PhantomJS'],
    frameworks: ['mocha'],

    plugins: [
      'karma-mocha',
      'karma-phantomjs-launcher'
    ]
  });
};
