describe("go.campaign", function() {

  describe(".bulkMessage", function() {

    var $div = $('<div/>');
    var text = 'Margle. The. World.';
    var $textarea = $('<textarea>' + text + '</textarea>');
    $div.append($textarea);
    view = new go.campaign.bulkMessage.TextareaView({el: $textarea});

    it("should append an element `.textarea-char-count`", function() {
        $textarea.trigger('keyup');
        assert.equal($div.find('.textarea-char-count').length, 1);
    });

    it("should update char and SMS counters on keyup.", function() {
        $textarea.trigger('keyup');
        assert.equal(text.length, view.totalChars);
        assert.equal(Math.ceil(text.length/160), view.totalSMS);

        text = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec quis tortor magna. Sed tristique mattis lectus sed tristique. Proin et diam id libero ullamcorper rhoncus. Cras bibendum aliquet faucibus. Maecenas nunc neque, laoreet sed bibendum eget, ullamcorper nec dui. Nam tortor quam, convallis dignissim auctor id, vehicula in nisl. Aenean accumsan, ipsum ac tristique interdum, leo quam pretium magna, nec sollicitudin ante ligula et sem. Aliquam a nulla orci. Curabitur vitae tortor nibh, id vulputate nisi. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae;';
        $textarea.text(text);
        $textarea.trigger('keyup');
        assert.equal(text.length, view.totalChars);
        assert.equal(Math.ceil(text.length/160), view.totalSMS);
    });
  });
});
