// go
// ==
// Base module for the client side of Go

(function(exports) {
  var urls = {
    loaders: {
      circles: {
        info: '/static/img/loaders/circles/info.gif'
      }
    }
  };

  _(exports).extend({
    urls: urls
  });
})(window.go = window.go || {});
