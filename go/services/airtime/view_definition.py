import json
import csv

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from django.contrib import messages

from go.services.view_definition import (ServiceView,
                                         ServiceTemplateView,
                                         ServiceViewDefinitionBase)

from go.services.airtime import settings
from go.services.airtime.forms import VoucherPoolForm, VoucherQueryForm
from go.services.airtime.utils import voucher_pool_or_404, VoucherService


class IndexView(ServiceTemplateView):
    """Render the Airtime Voucher service page"""

    view_name = 'index'
    path_suffix = None

    def get(self, request):
        voucher_pool_store = request.user_api.airtime_voucher_pool_store
        paginator = Paginator(voucher_pool_store.list_voucher_pools(),
                              settings.VOUCHER_POOLS_PER_PAGE)

        try:
            page = paginator.page(request.GET.get('p', 1))
        except PageNotAnInteger:
            page = paginator.page(1)
        except EmptyPage:
            page = paginator.page(paginator.num_pages)

        return self.render_to_response({
            'paginator': paginator, 'page': page})


class AddVoucherPoolView(ServiceTemplateView):
    """Handle a ``go.services.airtime.forms.VoucherPoolForm`` submission"""

    FORM_TITLE = _("Upload airtime vouchers")
    SUBMIT_TEXT = _("Upload vouchers")

    view_name = 'add'
    path_suffix = 'add'

    def _get_form_config(self, request, **extra_config):
        form_config = {
            'as_modal': request.GET.get('as_modal', False),
            'form_title': self.FORM_TITLE,
            'submit_text': self.SUBMIT_TEXT
        }
        form_config.update(extra_config)
        return form_config

    def get(self, request):
        form = VoucherPoolForm(user_api=request.user_api)
        return self.render_to_response({
            'form': form,
            'form_config': self._get_form_config(request)})

    def post(self, request):
        form = VoucherPoolForm(request.POST, request.FILES,
                               user_api=request.user_api)

        if form.is_valid():
            form.import_vouchers()
            msg = _("Airtime vouchers imported successfully.")
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

        return self.render_to_response({
            'form': form,
            'form_config': self._get_form_config(request)})


class ImportVouchersView(ServiceTemplateView):
    """Handle a ``go.services.airtime.forms.VoucherPoolForm`` submission"""

    FORM_TITLE = _("Upload airtime vouchers")
    SUBMIT_TEXT = _("Upload vouchers")

    view_name = 'import'
    path_suffix = 'import'

    def _get_form_config(self, request, **extra_config):
        form_config = {
            'as_modal': request.GET.get('as_modal', False),
            'form_title': self.FORM_TITLE,
            'submit_text': self.SUBMIT_TEXT
        }
        form_config.update(extra_config)
        return form_config

    def get(self, request):
        voucher_pool = voucher_pool_or_404(
            request.user_api, request.GET.get('voucher_pool_key', None))

        form = VoucherPoolForm(user_api=request.user_api,
                               voucher_pool=voucher_pool)

        return self.render_to_response({
            'form': form,
            'form_config': self._get_form_config(request)})

    def post(self, request):
        voucher_pool = voucher_pool_or_404(
            request.user_api, request.GET.get('voucher_pool_key', None))

        form = VoucherPoolForm(request.POST, request.FILES,
                               user_api=request.user_api,
                               voucher_pool=voucher_pool)

        if form.is_valid():
            form.import_vouchers()
            msg = _("Airtime vouchers imported successfully.")
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

        return self.render_to_response({
            'form': form,
            'form_config': self._get_form_config(request)})


class ExportVouchersView(ServiceView):
    """View to export all vouchers in a pool to a CSV file"""

    view_name = 'export'
    path_suffix = 'export'

    def get(self, request):
        voucher_pool = voucher_pool_or_404(
            request.user_api, request.GET.get('voucher_pool_key', None))

        response = HttpResponse(mimetype='text/csv')
        filename = "%s.csv" % (voucher_pool.name,)
        response['Content-Disposition'] = 'attachment; filename=%s' % (filename,)

        writer = csv.writer(response)
        headings = settings.FILE_FORMAT
        writer.writerow(headings)
        voucher_service = VoucherService()
        voucher_list = voucher_service.export_vouchers(voucher_pool)
        for voucher in voucher_list:
            writer.writerow([
                voucher.get(headings[0], ''),
                voucher.get(headings[1], ''),
                voucher.get(headings[2], '')])

        return response


class QueryVouchersView(ServiceTemplateView):
    """Handle a ``go.services.airtime.forms.VoucherQueryForm`` submission"""

    FORM_TITLE = _("Query airtime vouchers")
    SUBMIT_TEXT = _("Go")

    view_name = 'query'
    path_suffix = 'query'

    def _get_form_config(self, request, **extra_config):
        form_config = {
            'as_modal': request.GET.get('as_modal', False),
            'form_title': self.FORM_TITLE,
            'submit_text': self.SUBMIT_TEXT
        }
        form_config.update(extra_config)
        return form_config

    def get(self, request):
        voucher_pool = voucher_pool_or_404(
            request.user_api, request.GET.get('voucher_pool_key', None))

        return self.render_to_response({
            'form': VoucherQueryForm(voucher_pool=voucher_pool),
            'form_config': self._get_form_config(request)})

    def post(self, request):
        voucher_pool = voucher_pool_or_404(
            request.user_api, request.GET.get('voucher_pool_key', None))

        form = VoucherQueryForm(request.POST, voucher_pool=voucher_pool)
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

        return self.render_to_response({
            'form': form,
            'form_config': self._get_form_config(request)})


class ServiceViewDefinition(ServiceViewDefinitionBase):
    """View definition for the Airtime Vouchers service"""

    views = (
        IndexView,
        AddVoucherPoolView,
        ImportVouchersView,
        ExportVouchersView,
        QueryVouchersView,
    )
