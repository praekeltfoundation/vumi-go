from django.forms.formsets import formset_factory
from crispy_forms.layout import Fieldset

from vxpolls.content import forms


class SurveyPollForm(forms.PollForm):
    class Meta:
        layout = (
            Fieldset('Miscellaneous'),
            'poll_id',
            'repeatable',
            'case_sensitive',
            'include_labels',
            'survey_completed_response',
        )


class SurveyQuestionForm(forms.QuestionForm):
    pass


class SurveyCompletedResponseForm(forms.CompletedResponseForm):
    pass


def make_form_set(extra=1, **kwargs):
    SurveyQuestionFormset = formset_factory(SurveyQuestionForm, extra=extra)
    return SurveyQuestionFormset(prefix='questions', **kwargs)


def make_completed_response_form_set(extra=1, **kwargs):
    CRFormset = formset_factory(SurveyCompletedResponseForm, extra=extra)
    return CRFormset(prefix='completed_response', **kwargs)
