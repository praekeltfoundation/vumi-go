// go
// ==
// Base module for the client side of Go

(function(exports) {
  // Backbone.Rpc does something like:
  // `Backbone.Model = Backbone.Model.extend(...)`, which means:
  // `Backbone.Collection.prototype.model !== Backbone.Model`.
  //
  // Models created automatically when added to Backbone.Collection won't be
  // recognised as instances of Backbone.Model, so we need to change this.
  Backbone.Collection.prototype.model = Backbone.Model;
})(window.go = window.go || {});
