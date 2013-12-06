from django.forms import BooleanField, Form
from django.conf import settings
from django.contrib import messages

from vumi.persist.redis_manager import RedisManager
from vxpolls.manager import PollManager

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, ConversationTemplateView)
from go.apps.surveys import forms


def get_poll_config(poll_id):
    # FIXME: Do we really need this?
    redis = RedisManager.from_config(settings.VXPOLLS_REDIS_CONFIG)
    pm = PollManager(redis, settings.VXPOLLS_PREFIX)
    config = pm.get_config(poll_id)
    config.update({
        'poll_id': poll_id,
    })

    config.setdefault('repeatable', True)
    config.setdefault('survey_completed_response',
                        'Thanks for completing the survey')
    return pm, config


def _clear_empties(cleaned_data):
    """
    FIXME:  this is a work around because for some reason Django is seeing
            the new (empty) forms in the formsets as stuff that is to be
            stored when it really should be discarded.
    """
    return [cd for cd in cleaned_data if cd.get('copy')]


class SurveyEditView(ConversationTemplateView):
    """This app is a unique and special snowflake, so it gets special views.
    """
    view_name = 'edit'
    path_suffix = 'edit/'
    template_base = 'surveys'

    def get(self, request, conversation):
        poll_id = 'poll-%s' % (conversation.key,)
        pm, poll_data = get_poll_config(poll_id)
        questions_data = poll_data.get('questions', [])
        completed_response_data = poll_data.get(
            'survey_completed_responses', [])

        poll_form = forms.SurveyPollForm(initial=poll_data)
        questions_formset = forms.make_form_set(initial=questions_data)
        completed_response_formset = forms.make_completed_response_form_set(
            initial=completed_response_data)

        return self.render_to_response({
            'conversation': conversation,
            'poll_form': poll_form,
            'questions_formset': questions_formset,
            'completed_response_formset': completed_response_formset,
        })

    def post(self, request, conversation):
        poll_id = 'poll-%s' % (conversation.key,)
        pm, poll_data = get_poll_config(poll_id)

        post_data = request.POST.copy()
        post_data.update({
            'poll_id': poll_id,
        })

        questions_formset = forms.make_form_set(data=post_data)
        poll_form = forms.SurveyPollForm(data=post_data)
        completed_response_formset = forms.make_completed_response_form_set(
            data=post_data)
        if (questions_formset.is_valid() and poll_form.is_valid() and
                completed_response_formset.is_valid()):
            data = poll_form.cleaned_data.copy()
            data.update({
                'questions': _clear_empties(questions_formset.cleaned_data),
                'survey_completed_responses': _clear_empties(
                    completed_response_formset.cleaned_data)
                })
            pm.set(poll_id, data)
            messages.info(request, 'Conversation updated.')
            if request.POST.get('_save_contents'):
                return self.redirect_to(
                    'edit', conversation_key=conversation.key)
            else:
                return self.redirect_to(
                    'show', conversation_key=conversation.key)

        return self.render_to_response({
            'conversation': conversation,
            'poll_form': poll_form,
            'questions_formset': questions_formset,
            'completed_response_formset': completed_response_formset,
        })


class DownloadUserDataForm(Form):
    include_old_questions = BooleanField(
        label="Include old questions",
        help_text=("Whether to include answers to old questions that were"
                   " once part of the poll but are no longer."),
        initial=False, required=False)


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = SurveyEditView

    action_forms = {
        # TODO: The empty send_survey form is a work-around for not being able
        #       to directly trigger POSTs via conversation action buttons
        'send_survey': Form,
        'download_user_data': DownloadUserDataForm,
    }
