import json

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from django.contrib import messages

from go.services.view_definition import (ServiceTemplateView,
                                         ServiceViewDefinitionBase)

from go.services.vouchers.unique_codes import settings as service_settings
from go.services.vouchers.unique_codes.forms import (UniqueCodePoolForm,
                                                     UniqueCodeQueryForm)

from go.services.vouchers.unique_codes.utils import unique_codes_pool_or_404


class IndexView(ServiceTemplateView):
    """Render the Unique Codes service page"""

    template_base = 'unique_codes'
    view_name = 'index'
    path_suffix = None

    def get(self, request):
        store = request.user_api.unique_code_pool_store
        paginator = Paginator(store.get_all_pools(),
                              service_settings.UNIQUE_CODE_POOLS_PER_PAGE)

        try:
            page = paginator.page(request.GET.get('p', 1))
        except PageNotAnInteger:
            page = paginator.page(1)
        except EmptyPage:
            page = paginator.page(paginator.num_pages)

        return self.render_to_response({
            'paginator': paginator, 'page': page})


class AddUniqueCodePoolView(ServiceTemplateView):
    """Handle a ``go.services.vouchers.unique_codes.forms.UniqueCodePoolForm``
    submission.
    """

    FORM_TITLE = _("Upload unique codes")
    SUBMIT_TEXT = _("Upload codes")

    template_base = 'unique_codes'
    view_name = 'add'
    path_suffix = 'add'

    def _get_form_config(self, request, **extra_config):
        form_config = {
            'title': self.FORM_TITLE,
            'submit_text': self.SUBMIT_TEXT,
            'as_modal': request.GET.get('as_modal', False),
        }
        form_config.update(extra_config)
        return form_config

    def get(self, request):
        form = UniqueCodePoolForm(config=self._get_form_config(request),
                                  service_def=self.service_def,
                                  user_api=request.user_api)

        return self.render_to_response({'form': form})

    def post(self, request):
        form = UniqueCodePoolForm(request.POST, request.FILES,
                                  config=self._get_form_config(request),
                                  service_def=self.service_def,
                                  user_api=request.user_api)

        if form.is_valid():
            form.import_vouchers()
            msg = _("Unique codes imported successfully.")
            if request.is_ajax():
                return HttpResponse(str(msg), mimetype="text/plain")
            else:
                messages.add_message(request, messages.INFO, msg)
                return self.redirect_to('index')
        else:
            msg = _("Please correct the errors below and try again.")
            if request.is_ajax():
                return HttpResponse(json.dumps(form.errors_as_json()),
                                    mimetype="application/json",
                                    status=400)
            else:
                messages.add_message(request, messages.ERROR, msg)

        return self.render_to_response({'form': form})


class ImportUniqueCodesView(ServiceTemplateView):
    """Handle a ``go.services.vouchers.unique_codes.forms.UniqueCodePoolForm``
    submission.
    """

    FORM_TITLE = _("Upload unique codes")
    SUBMIT_TEXT = _("Upload codes")

    template_base = 'unique_codes'
    view_name = 'import'
    path_suffix = 'import'

    def _get_form_config(self, request, **extra_config):
        form_config = {
            'title': self.FORM_TITLE,
            'submit_text': self.SUBMIT_TEXT,
            'as_modal': request.GET.get('as_modal', False),
        }
        form_config.update(extra_config)
        return form_config

    def get(self, request):
        unique_code_pool = unique_codes_pool_or_404(
            request.user_api, request.GET.get('unique_code_pool_key', None))

        form = UniqueCodePoolForm(config=self._get_form_config(request),
                                  service_def=self.service_def,
                                  user_api=request.user_api,
                                  unique_code_pool=unique_code_pool)

        return self.render_to_response({'form': form})

    def post(self, request):
        unique_code_pool = unique_codes_pool_or_404(
            request.user_api, request.GET.get('unique_code_pool_key', None))

        form = UniqueCodePoolForm(request.POST, request.FILES,
                                  config=self._get_form_config(request),
                                  service_def=self.service_def,
                                  user_api=request.user_api,
                                  unique_code_pool=unique_code_pool)

        if form.is_valid():
            form.import_vouchers()
            msg = _("Unique codes imported successfully.")
            if request.is_ajax():
                return HttpResponse(str(msg), mimetype="text/plain")
            else:
                messages.add_message(request, messages.INFO, msg)
                return self.redirect_to('index')
        else:
            msg = _("Please correct the errors below and try again.")
            if request.is_ajax():
                return HttpResponse(json.dumps(form.errors_as_json()),
                                    mimetype="application/json",
                                    status=400)
            else:
                messages.add_message(request, messages.ERROR, msg)

        return self.render_to_response({'form': form})


class QueryUniqueCodesView(ServiceTemplateView):
    """Handle a ``go.services.vouchers.unique_codes.forms.UniqueCodeQueryForm``
    submission.
    """

    FORM_TITLE = _("Query unique codes")
    SUBMIT_TEXT = _("Go")

    template_base = 'unique_codes'
    view_name = 'query'
    path_suffix = 'query'

    def _get_form_config(self, request, **extra_config):
        form_config = {
            'title': self.FORM_TITLE,
            'submit_text': self.SUBMIT_TEXT,
            'as_modal': request.GET.get('as_modal', False),
        }
        form_config.update(extra_config)
        return form_config

    def get(self, request):
        unique_code_pool = unique_codes_pool_or_404(
            request.user_api, request.GET.get('unique_code_pool_key', None))

        form = UniqueCodeQueryForm(
            config=self._get_form_config(request),
            service_def=self.service_def,
            unique_code_pool=unique_code_pool)

        return self.render_to_response({'form': form})

    def post(self, request):
        unique_code_pool = unique_codes_pool_or_404(
            request.user_api, request.GET.get('unique_code_pool_key', None))

        form = UniqueCodeQueryForm(
            request.POST,
            config=self._get_form_config(request),
            service_def=self.service_def,
            unique_code_pool=unique_code_pool)

        if form.is_valid():
            form.submit_query()
            if request.is_ajax():
                messages = [message.encode('utf-8') for message in
                            form.messages]

                return HttpResponse(json.dumps(messages),
                                    mimetype="application/json")
        else:
            msg = _("Please correct the errors below and try again.")
            if request.is_ajax():
                return HttpResponse(json.dumps(form.errors_as_json()),
                                    mimetype="application/json",
                                    status=400)
            else:
                messages.add_message(request, messages.ERROR, msg)

        return self.render_to_response({'form': form})


class ServiceViewDefinition(ServiceViewDefinitionBase):
    """View definition for the Unique Codes service"""

    views = (
        IndexView,
        AddUniqueCodePoolView,
        ImportUniqueCodesView,
        QueryUniqueCodesView,
    )
