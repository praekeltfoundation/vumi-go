describe("go.components.dates", function() {
  describe(".DateRangeView", function() {
    var DateRangeView = go.components.dates.DateRangeView;

    var view;

    beforeEach(function() {
      view = new DateRangeView({
        el: $('<div>')
          .append($('<label>')
            .addClass('date-preset')
            .append($('<input>')
              .attr('type', 'radio')
              .attr('name', 'preset')
              .attr('value', '1d')))
          .append($('<label>')
            .addClass('date-preset')
            .append($('<input>')
              .attr('type', 'radio')
              .attr('name', 'preset')
              .attr('value', '7d')))
          .append($('<div>')
            .addClass('date-custom-toggle')
            .append($('<span>')
              .addClass('glyphicon')
              .attr('data-up', 'glyphicon-up')
              .attr('data-down', 'glyphicon-down')))
          .append($('<div>')
            .addClass('date-custom-container'))
      });
    });

    describe("when the custom date toggle is clicked", function() {
      it("should re-render the view", function(done) {
        view
          .once('rendered', function() { done(); });

        view
          .$('.date-custom-toggle')
          .click();
      });

      it("should toggle collapsing the custom date container",
      function(done) {
        function onceShown(fn) {
          view
            .$('.date-custom-container')
            .one('shown.bs.collapse', fn);
        }

        function onceHidden(fn) {
          view
            .$('.date-custom-container')
            .one('hidden.bs.collapse', fn);
        }

        onceShown(function() {
          onceHidden(function() { done(); });

          view
            .$('.date-custom-toggle')
            .click();
        });

        view
          .$('.date-custom-toggle')
          .click();
      });

      it("should uncheck all presets", function() {
        view
          .$('.date-preset input[value="7d"]')
          .prop('checked', true);

        assert.strictEqual(
          view.$('.date-preset input:checked').length,
          1);

        view
          .$('.date-custom-toggle')
          .click();

        assert.strictEqual(
          view.$('.date-preset input:checked').length,
          0);
      });
    });

    describe("when a date preset is changed", function() {
      it("should re-render the view", function(done) {
        view
          .once('rendered', function() { done(); });

        view
          .$('.date-preset input[value="7d"]')
          .change();
      });

      it("should collapse the custom date container", function(done) {
        function show(fn) {
          view
            .$('.date-custom-container')
            .one('shown.bs.collapse', fn)
            .collapse('show');
        }

        function onceHidden(fn) {
          view
            .$('.date-custom-container')
            .one('hidden.bs.collapse', fn);
        }

        show(function() {
          onceHidden(function() { done(); });

          view
            .$('.date-preset input[value="7d"]')
            .change();
        });
      });
    });

    describe("when the custom date container is hidden", function() {
      it("should set the custom date toggle's glyph to 'down'", function(done) {
        function show(fn) {
          view
            .$('.date-custom-container')
            .one('shown.bs.collapse', fn)
            .collapse('show');
        }

        function hide(fn) {
          view
            .$('.date-custom-container')
            .one('hidden.bs.collapse', fn)
            .collapse('hide');
        }

        show(function() {
          view
            .$('date-custom-toggle .glyphicon')
            .addClass('glyphicon-up');

          hide(function() {
            assert.strictEqual(
              view.$('.date-custom-toggle .glyphicon-up').length,
              0);

            assert.strictEqual(
              view.$('.date-custom-toggle .glyphicon-down').length,
              1);

            done();
          });
        });
      });
    });

    describe("when the custom date container is shown", function() {
      it("should set the custom date toggle's glyph to 'up'", function(done) {
        function show(fn) {
          view
            .$('.date-custom-container')
            .one('shown.bs.collapse', fn)
            .collapse('show');
        }

        view
          .$('date-custom-toggle .glyphicon')
          .addClass('glyphicon-down');

        show(function() {
          assert.strictEqual(
            view.$('.date-custom-toggle .glyphicon-down').length,
            0);

          assert.strictEqual(
            view.$('.date-custom-toggle .glyphicon-up').length,
            1);

          done();
        });
      });
    });

    describe(".render", function() {
      it("should set the correct item to active", function() {
        view
          .$('.date-preset input[value="7d"]')
          .prop('checked', true);

        assert.strictEqual(
          view.$('.active').length,
          0);

        view.render();

        assert.strictEqual(
          view.$('.active').length,
          1);

        assert.strictEqual(
          view.$('.date-preset.active input[value="7d"]').length,
          1);

        view
          .$('.date-preset input')
          .prop('checked', false);

        view
          .$('.date-preset input[value="1d"]')
          .prop('checked', true);

        view.render();

        assert.strictEqual(
          view.$('.active').length,
          1);

        assert.strictEqual(
          view.$('.date-preset.active input[value="1d"]').length,
          1);

        view
          .$('.date-preset input')
          .prop('checked', false);

        view.render();

        assert.strictEqual(
          view.$('.active').length,
          1);

        assert.strictEqual(
          view.$('.date-custom-toggle.active').length,
          1);
      });
    });
  });
});
