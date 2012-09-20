from django.forms.formsets import formset_factory

from bootstrap.forms import BootstrapMixin

from vxpolls.content import forms


class SurveyPollForm(BootstrapMixin, forms.PollForm):
    pass

class SurveyQuestionForm(BootstrapMixin, forms.QuestionForm):
    pass

def make_form_set(extra=1, **kwargs):
    SurveyQuestionFormset = formset_factory(SurveyQuestionForm, extra=extra)
    return SurveyQuestionFormset(**kwargs)
