
from django import forms
from django.utils.translation import ugettext_lazy as _


class AjaxFormMixin(object):
    """Implements some useful methods for AJAX forms"""

    def errors_as_json(self):
        """Return all field errors as a JSON object"""
        obj = {}
        for field in self:
            errors = []
            for error in field.errors:
                errors.append(error)
            if len(errors) > 0:
                field_name = field.name
                if self.prefix:
                    field_name = '%s-%s' % (self.prefix, field.name)
                obj[field_name] = errors
        return obj


class BaseServiceForm(forms.Form):
    """Base class for service forms"""

    config = {
        'title': None,
        'method': 'POST',
        'action': None,
        'submit_text': _("Submit"),
        'as_modal': False,
    }

    def __init__(self, *args, **kwargs):
        self.config.update(kwargs.pop('config', {}))
        self.service_def = kwargs.pop('service_def')
        super(BaseServiceForm, self).__init__(*args, **kwargs)
