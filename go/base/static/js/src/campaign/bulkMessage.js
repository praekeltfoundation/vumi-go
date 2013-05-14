// go.campaign.bulkMessage
// ==============================
// Models, Views and other stuff for the bulk message composition screen

(function(exports) {

    var TextareaView = Backbone.View.extend({
        tagName: 'p',
        SMS_TOTAL_CHARS: 160,

        initialize: function() {
            _.bindAll(this, 'render');
            this.$textarea = this.options.$textarea;
            this.$textarea.on('keyup', this.render);
        },
        render: function() {
            var totalChars = this.$textarea.val().length;
            var totalSMS = Math.ceil(totalChars / this.SMS_TOTAL_CHARS)
            this.$el.html(totalChars + ' characters used<br>' 
                          + totalSMS + ' smses');
            return this;
        },
    });

    exports.TextareaView = TextareaView;


})(go.campaign.bulkMessage = {});
