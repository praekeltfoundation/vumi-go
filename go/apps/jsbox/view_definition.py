from StringIO import StringIO

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, ConversationTemplateView,
    EditConversationView)

from go.apps.jsbox.forms import JsboxForm, JsboxAppConfigFormset
from go.apps.jsbox.log import LogManager
from go.apps.jsbox.kv import KeyValueManager
from go.base.utils import UnicodeCSVWriter


class JSBoxLogsView(ConversationTemplateView):
    view_name = 'jsbox_logs'
    path_suffix = 'jsbox_logs/'
    template_base = 'jsbox'

    def get(self, request, conversation):
        campaign_key = request.user_api.user_account_key
        log_manager = LogManager(request.user_api.api.redis)
        logs = log_manager.get_logs(campaign_key, conversation.key)
        logs = list(reversed(logs))
        return self.render_to_response({
            "conversation": conversation,
            "logs": logs,
        })


class JSBoxAnswersView(ConversationTemplateView):
    view_name = 'jsbox_answers'
    path_suffix = 'jsbox_answers/'

    @staticmethod
    def _answers_to_csv(answers):
        io = StringIO()
        writer = UnicodeCSVWriter(io)

        fieldnames = set()
        rows = []
        for line in infile:
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if "key" not in data:
                continue
            if key_re.match(data["key"]) is None:
                continue
            row = flatten(json.loads(data["value"]))
            rows.append(row)
            fieldnames.update(row.keys())
            row["key"] = data["key"]

        fieldnames = ["key"] + sorted(fieldnames)
        writer = csv.DictWriter(outfile, fieldnames)
        writer.writeheader()
        writer.writerows(rows)



    def get(self, request, conversation):
        campaign_key = request.user_api.user_account_key
        kv_manager = KeyValueManager(request.user_api.api.redis)
        user_store = conversation.config.get("TODO")
        answers = kv_manager.answers(campaign_key, user_store)



        return self.render_to_response({
            "conversation": conversation,
            "answers": answers,
        })


class EditJSBoxView(EditConversationView):
    template_base = 'jsbox'

    edit_forms = (
        ('jsbox', JsboxForm),
        ('jsbox_app_config', JsboxAppConfigFormset),
    )

    def get(self, request, conversation):
        edit_forms = dict(self.make_forms_dict(conversation))

        return self.render_to_response({
            'conversation': conversation,
            'jsbox_form': edit_forms['jsbox'],
            'jsbox_app_config_forms': edit_forms['jsbox_app_config'],
            'edit_forms_media': self.sum_media(edit_forms.values())
        })


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditJSBoxView

    extra_views = (
        JSBoxLogsView,
    )
