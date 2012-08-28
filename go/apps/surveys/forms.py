from bootstrap.forms import BootstrapMixin
from vxpolls.content.forms import QuestionForm, PollForm

from django.forms.formsets import formset_factory
from django.utils.datastructures import SortedDict
from django import forms


class SurveyForm(BootstrapMixin, PollForm):
    pass

class SurveyQuestionForm(BootstrapMixin, QuestionForm):
    pass

SurveyQuestionFormSet = formset_factory(SurveyQuestionForm, extra=1)


def make_form_set(extra=1, **kwargs):
    SurveyQuestionFormset = formset_factory(QuestionForm, extra=extra)
    return SurveyQuestionFormset(**kwargs)

class BaseDynamicForm(object):
    def mapping_sets(self):
        return [{
            'field': field,
            'select': self['%s_map' % (field,)],
            'other': self['%s_other' % (field,)],
        } for field in self.known_fields]

    def get_value(self, mapping):
        other = mapping['other'].value()
        if other:
            return other
        selected = mapping['select'].value()
        if selected:
            return selected

    def get_complete_mappings(self):
        return dict([
            (mapping['field'], self.get_value(mapping))
                for mapping in self.mapping_sets()])

    def get_mappings(self):
        return dict([(field, value) for field, value
            in self.get_complete_mappings().items() if value])


def make_mapping_form_class(known_fields):
    fields = SortedDict()
    for field in known_fields:
        fields['%s_map' % (field,)] = forms.ChoiceField(required=False,
            label="%s maps to" % (field,), choices=[
                ('', 'Pick one ...'),
                ('name', 'Name'),
                ('surname', 'Surname'),
                ('email_address', 'Email Address'),
                ('msisdn', 'Contact Number'),
                ('dob', 'Date of Birth'),
                ('twitter_handle', 'Twitter Handle'),
                ('facebook_id', 'Facebook ID'),
                ('bbm_pin', 'BBM Pin'),
                ('gtalk_id', 'Google Talk / Jabber ID'),
            ])
        fields['%s_other' % (field,)] = forms.CharField(required=False,
            label='Other: ', widget=forms.TextInput(attrs={'class': 'span2',
                'placeholder': 'Other ...'}))

    form_class = type('DynamicSurveyForm', (
        BaseDynamicForm, BootstrapMixin, forms.BaseForm,), {
        'base_fields': fields,
        'known_fields': known_fields,
    })
    return form_class

def make_mapping_form_class_for_formset(questions_formset):
    # Make it a sorted dict so we get a list of unique keys while
    # still maintaining their original order. Just calling set() on the
    # list makes it unique but jumbles the order
    known_fields = SortedDict([(form['label'].value(), 1) for form in
                            questions_formset.forms if form['label'].value()])
    return make_mapping_form_class(known_fields)
