// go.services
// ===============

(function(exports) {
  var ajaxForm = go.utils.ajaxForm;

  var BaseVoucherPoolView = Backbone.View.extend({

    events: {
      'click a[rel="modal"]': 'showModal'
    },

    initialize: function(options) {
        this.url = options.url;
        this.$modal = options.$modal;
    },

    refresh: function() {
        this.$el.load(this.url);
    },

    showModal: function(event) {
      var self = this;

      event.preventDefault();
      event.stopPropagation();

      var $link = $(event.currentTarget);
      var url = $link.attr('href');
      var keepOpen = $link.data('keep-modal-open');
      this.$modal.load(url, function() {
        var $form = self.$modal.find('form');
        if ($form.length > 0) {
          ajaxForm($form, function() {
            if (!keepOpen) {
              self.$modal.modal('hide');
              self.refresh();
            }
          });
        }
        self.$modal.modal('show');
      });
    }
  });

  _.extend(exports, {
    BaseVoucherPoolView: BaseVoucherPoolView
  });

})(go.services = {});
