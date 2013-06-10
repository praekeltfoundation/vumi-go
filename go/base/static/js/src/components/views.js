// go.components.views
// ===================
// Generic, re-usable views for Go

(function(exports) {
  var utils = go.utils,
      functor = utils.functor;

  // View for a label which can be attached to an element.
  //
  // Options:
  //   - text: A string or a function returning a string containing the text to
  //   be displayed by the label
  //   - of: The target element this label should be attached to
  //   - my: The point on the label to align with the of
  //   - at: The point on the target element to align the label against
  var LabelView = Backbone.View.extend({
    tagName: 'span',
    className: 'label',

    initialize: function(options) {
      this.$of = $(options.of);
      this.text = functor(options.text);
      this.my = options.my;
      this.at = options.at;
    },

    render: function() {
      // Append the label to the of element so it can follow the of
      // around (in the case of moving or draggable ofs)
      this.$of.append(this.$el);

      this.$el
        .text(this.text())
        .position({
          of: this.$of,
          my: this.my,
          at: this.at
        })
        .css('position', 'absolute')
        .css('pointer-events', 'none');
    }
  });

  _.extend(exports, {
    LabelView: LabelView
  });
})(go.components.views = {});
