from django.conf import settings
from django.http import HttpResponse
from bootstrap.forms import BootstrapForm

from vumi.persist.redis_manager import RedisManager
from vxpolls.manager import PollManager

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, ConversationTemplateView)


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


class SurveyEditView(ConversationTemplateView):
    """This app is a unique and special snowflake, so it gets special views.
    """
    view_name = 'edit'
    path_suffix = 'edit/'
    template_base = 'surveys'

    def get(self, request, conversation):
        # TODO Use api to get model data and bootstrap it to page load

        return self.render_to_response({
            'conversation': conversation
        })


class UserDataView(ConversationTemplateView):
    view_name = 'user_data'
    path_suffix = 'users.csv'

    def get(self, request, conversation):
        poll_id = 'poll-%s' % (conversation.key,)
        pm, poll_data = get_poll_config(poll_id)
        poll = pm.get(poll_id)
        csv_data = pm.export_user_data_as_csv(poll)
        return HttpResponse(csv_data, content_type='application/csv')


class SendSurveyForm(BootstrapForm):
    # TODO: Something better than this?
    pass


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = SurveyEditView

    extra_views = (
        SurveyEditView,
        UserDataView,
    )

    action_forms = {
        'send_survey': SendSurveyForm,
    }
