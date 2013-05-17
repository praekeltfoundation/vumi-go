// go.campaign.bulkMessage
// ==============================
// Models, Views and other stuff for the bulk message composition screen

(function(exports) {

    var TextareaView = Backbone.View.extend({
        SMS_MAX_CHARS: 160,
        events: {
            'keyup': 'render'
        },
        initialize: function() {
            _.bindAll(this, 'render');
        },
        render: function() {
            var $p = this.$el.next();
            if (!$p.hasClass('textarea-char-count')) {
                $p = $('<p class="textarea-char-count"/>');
                this.$el.after($p);
            }
            this.totalChars = this.$el.val().length;
            this.totalSMS = Math.ceil(this.totalChars / this.SMS_MAX_CHARS);
            $p.html(this.totalChars + ' characters used<br>' + this.totalSMS + ' smses');

            return this;
        }
    });
    exports.TextareaView = TextareaView;

})(go.campaign.bulkMessage = {});
