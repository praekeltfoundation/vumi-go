describe("go.components.templating", function() {
  var templating = go.components.templating;

  describe(".Template", function() {
    var Template = templating.Template;

    var ToyView = Backbone.View.extend({
      initialize: function(options) {
        this.thing = options.thing;
      },

      render: function() {
        this.$el.text(this.thing);
      }
    });

    describe(".render", function() {
      it("should apply the jst template", function()  {
        var template = new Template({
          jst: _.template('I am the <%= thing %>.'),
          data: {thing: 'Walrus'}
        });

        assert.equal(template.$el.html(), '');
        template.render();
        assert.equal(template.$el.html(), 'I am the Walrus.');
      });

      it("should apply its view partials", function() {
        var i = 0;

        var template = new Template({
          jst: _.template([
            '<script data-partial="p1" type="partial"></script>',
            '<script data-partial="p2" type="partial"></script>'
          ].join('')),

          partials: {
            p1: new ToyView({thing: 'Walrus'}),
            p2: new ToyView({thing: 'Eggman'})
          }
        });

        template.render();

        assert.equal(
          template.$el.html(), [
          '<div data-partial="p1">Walrus</div>',
          '<div data-partial="p2">Eggman</div>'
        ].join(''));
      });

      it("should apply its template function partials", function() {
        var i = 0;

        var template = new Template({
          jst: _.template([
            '<script data-partial="p1" type="partial"></script>',
            '<script data-partial="p2" type="partial"></script>'
          ].join('')),

          partials: {
            p1: _.template('<div>I am the Eggman</div>'),
            p2: _.template('<div>They are the Eggmen</div>')
          }
        });

        template.render();

        assert.equal(
          template.$el.html(), [
          '<div data-partial="p1">I am the Eggman</div>',
          '<div data-partial="p2">They are the Eggmen</div>'
        ].join(''));
      });
    });
  });
});
