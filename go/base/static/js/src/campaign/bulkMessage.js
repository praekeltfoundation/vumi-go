// go.campaign.bulkMessage
// ==============================
// Models, Views and other stuff for the bulk message composition screen

(function(exports) {

    var TextareaView = Backbone.View.extend({
        SMS_TOTAL_CHARS: 160,

        events: {
            'keyup': 'render',
        },

        initialize: function() {
            _.bindAll(this, 'render');
        },
        render: function() {
            $p = this.$el.next();
            if (!$p.hasClass('textarea-char-count')) {
                $p = this.$el.after('<p class="textarea-char-count"/>');
            }
            var totalChars = this.$el.val().length;
            var totalSMS = Math.ceil(totalChars / this.SMS_TOTAL_CHARS)
            $p.html(totalChars + ' characters used<br>' + totalSMS + ' smses');

            return this;
        },
    });
    exports.TextareaView = TextareaView;

})(go.campaign.bulkMessage = {});
