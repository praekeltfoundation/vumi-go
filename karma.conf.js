require('js-yaml');

module.exports = function(config) {
  var paths = require('paths.yml');

  config.set({
    basePath: 'go/base/static/',

    files: [].concat(
      paths.client.scripts.vendor,
      paths.client.scripts.go,
      paths.tests.client.vendor,
      paths.tests.client.spec
    ),

    browsers: ['PhantomJS'],
    frameworks: ['mocha'],
    plugins: ['karma-phantomjs-launcher', 'karma-mocha']
  });
};
