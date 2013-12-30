// go.utils
// ========
// Utilities and helpers for Go

(function(exports) {
  // Merges the passed in objects together into a single object
  var merge = function() {
    Array.prototype.unshift.call(arguments, {});
    return _.extend.apply(this, arguments);
  };

  var highlightActiveLinks = function() {
    // find links in the document that match the current
    // windows url and set them as active.

    var loc = window.location;
    var url = loc.href;
    url = url.replace(loc.host, '').replace(loc.protocol + '//', '');

    $('a[href="' + url + '"]').addClass('active');
  };

  // Returns `obj` if it is a function, otherwise wraps `obj` in a function and
  // returns the function
  var functor = function(obj) {
    return typeof obj === 'function'
      ? obj
      : function() { return obj; };
  };

  // Returns an object given a 'dotted' name like `thing.subthing.Subthing`,
  // and an optional context to look for the object in
  var objectByName = function(name, that) {
    return _(name.split( '.' )).reduce(
      function(obj, propName) { return obj[propName]; },
      that || this);
  };

  // If given a string, gets the object by name, otherwise just returns what
  // it was given
  var maybeByName = function(nameOrObj, that) {
    return typeof nameOrObj === 'string'
      ? objectByName(nameOrObj, that)
      : nameOrObj;
  };

  var idOfModel = function(obj) {
    if (obj instanceof Backbone.Model) { return obj.id || obj.cid; }

    return obj.id
      ? obj.id
      : obj.uuid || obj;
  };

  var idOfView = function(obj) {
    return obj.uuid
      ? _(obj).result('uuid')
      : _(obj).result('id') || obj;
  };

  var unaccentify = (function() {
    var accents     = 'àáâãäåçèéêëìíîïñðóòôõöøùúûüýÿ',
        accentRepls = 'aaaaaaceeeeiiiinooooooouuuuyy';

    var unaccentifyChar = function(c) {
      var i = accents.indexOf(c);

      return i < 0
        ? c
        : accentRepls[i];
    };

    return function(s) {
      var r = '',
          i = -1,
          n = s.length;

      s = s.toLowerCase();
      while (++i < n) { r += unaccentifyChar(s[i]); }

      return r;
    };
  })();

  var slugify = (function() {
    var wierdCharRe = /[^-A-Za-z0-9]/g,
        whitespaceRe = /\s+/g;

    return function(s) {
      return unaccentify(s)
        .replace(whitespaceRe, '-')
        .replace(wierdCharRe, '');
    };
  })();

  // For test stubbing purposes
  var redirect = function(url) { window.location = url; };

  var bindEvents = function(events, that) {
    that = that || this;

    _(events).each(function(fn, e) {
      var parts = e.split(' '),
          event = parts[0],
          entity = parts[1];

      if (entity) { that.listenTo(objectByName(entity, that), event, fn); }
      else { that.on(event, fn); }
    });
  };

  var delayed = function(fn, delay, that) {
    if (delay > 0) { _.delay(fn.bind(that), delay); }
    else { fn.call(that); }
  };

  var capitalise = function(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
  };

  var makeMessage = function(message) {
    var $message = $('<p>').addClass('message');
    $message.text(message);
    return $message;
  }

  var makeError = function(error) {
    var $error = $('<p>').addClass('error');
    $error.text(error);
    return $error;
  }

  var makeErrorlist = function(formErrors, fieldName) {
    var $errorList = $('<ul>').addClass('errorlist');
    var fieldErrors = formErrors[fieldName];
    for (index in fieldErrors) {
      var $listItem = $('<li>');
      var $helpBlock = $('<span>').addClass('help-block');
      $helpBlock.text(fieldErrors[index]);
      $listItem.append($helpBlock);
      $errorList.append($listItem);
    }
    return $errorList;
  }

  var ajaxForm = function($form, success, error) {
    var options = {
      beforeSubmit: function (formData, $form, options) {
        $form.find('div.form-group.error').removeClass('error');
        $form.find('div.controls ul.errorlist').remove();
        $form.find('div.form-messages').empty();
      },
      success: function (responseText, statusText, jqXHR, $form) {
        if (statusText == 'success') {
          $form.find('input[type=text], textarea, select').val("");

          var $formMessages = $form.find('div.form-messages');
          var contentType = jqXHR.getResponseHeader('Content-Type');
          if (contentType.indexOf('application/json') != -1) {
            var responseData = $.parseJSON(jqXHR.responseText);
            for (index in responseData) {
              $formMessages.append(makeMessage(responseData[index]));
            }

          } else {
            $formMessages.append(makeMessage(responseText));
          }

          if (success) {
            success(responseText);
          }
        }
      },
      error: function (jqXHR, textStatus, errorThrown) {
        var status = jqXHR.status;
        var contentType = jqXHR.getResponseHeader('Content-Type');
        if (status == 400 /* Bad Request */
            && contentType.indexOf('application/json') != -1) {
          var responseData = $.parseJSON(jqXHR.responseText);
          for (fieldName in responseData) {
            var $field = $form.find('*[name="' + fieldName + '"]');
            $field.parents('div.form-group:first').addClass('error');
            var $controls = $field.parents('div.controls:first');
            $controls.append(makeErrorlist(responseData, fieldName));
          }

        } else {
          var $formMessages = $form.find('div.form-messages');
          $formMessages.append(makeError(jqXHR.responseText));
        }

        if (error) {
          error(jqXHR.responseText);
        }
      }
    };
    $form.ajaxForm(options);
  };

  _.extend(exports, {
    merge: merge,
    functor: functor,
    objectByName: objectByName,
    maybeByName: maybeByName,
    idOfModel: idOfModel,
    idOfView: idOfView,
    slugify: slugify,
    unaccentify: unaccentify,
    redirect: redirect,
    bindEvents: bindEvents,
    delayed: delayed,
    capitalise: capitalise,
    highlightActiveLinks: highlightActiveLinks,
    ajaxForm: ajaxForm
  });
})(go.utils = {});
