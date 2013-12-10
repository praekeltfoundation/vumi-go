import csv

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse

from go.vouchers import settings
from go.vouchers.models import VoucherPool
from go.vouchers.forms import (
    AirtimeVoucherPoolForm,
    AirtimeVoucherImportForm,
    AirtimeVoucherQueryForm)

from go.vouchers.services import AirtimeVoucherService


def _render_voucher_list(
        request, template_name='vouchers/voucher_list.html',
        *args, **kwargs):
    """Render the Voucher List page.

    Ensure all required context names are supplied.
    """
    context = {}
    context.update(kwargs)
    if 'airtime_voucher_pool_list' not in context:
        airtime_voucher_pool_list = VoucherPool.objects.filter(
            user=request.user, pool_type=VoucherPool.POOL_TYPE_AIRTIME)

        context['airtime_voucher_pool_list'] = airtime_voucher_pool_list

    if 'airtime_voucher_pool_form' not in context:
        context['airtime_voucher_pool_form'] = AirtimeVoucherPoolForm()

    if 'airtime_voucher_import_form' not in context:
        context['airtime_voucher_import_form'] = AirtimeVoucherImportForm()

    if 'airtime_voucher_query_form' not in context:
        context['airtime_voucher_query_form'] = AirtimeVoucherQueryForm()

    if 'unique_code_pool_list' not in context:
        unique_code_pool_list = VoucherPool.objects.filter(
            user=request.user, pool_type=VoucherPool.POOL_TYPE_UNIQUE_CODE)

        context['unique_code_pool_list'] = unique_code_pool_list

    return render(request, template_name, context)


@login_required
def voucher_list(request):
    """Display a list of Airtime Vouchers and Unique Codes"""
    return _render_voucher_list(request)


@login_required
def airtime_voucher_pool_add(request):
    """Handle a ``go.vouchers.forms.AirtimeVoucherPoolForm`` submission"""
    if request.method == 'POST':
        airtime_voucher_pool_form = AirtimeVoucherPoolForm(
            request.POST, request.FILES, user=request.user)

        if airtime_voucher_pool_form.is_valid():
            airtime_voucher_pool_form.save()
            return redirect('vouchers:voucher_list')

        return _render_voucher_list(
            request, airtime_voucher_pool_form=airtime_voucher_pool_form)

    else:
        return redirect('vouchers:voucher_list')


@login_required
def airtime_voucher_pool_import(request, pool_id):
    """Handle a ``go.vouchers.forms.AirtimeVoucherImportForm`` submission"""
    voucher_pool = get_object_or_404(VoucherPool, id=pool_id,
                                     user=request.user)

    if request.method == 'POST':
        airtime_voucher_import_form = AirtimeVoucherImportForm(
            request.POST, request.FILES, instance=voucher_pool)

        if airtime_voucher_import_form.is_valid():
            airtime_voucher_import_form.save()
            return redirect('vouchers:voucher_list')

        return _render_voucher_list(
            request, airtime_voucher_import_form=airtime_voucher_import_form)
    else:
        return redirect('vouchers:voucher_list')


@login_required
def airtime_voucher_pool_export(request, pool_id):
    """Return the vouchers in the pool with the given `pool_id` in a
    CSV file.
    """
    voucher_pool = get_object_or_404(VoucherPool, id=pool_id,
                                     user=request.user)

    response = HttpResponse(mimetype='text/csv')
    filename = "%s.csv" % (voucher_pool.pool_name,)
    response['Content-Disposition'] = 'attachment; filename=%s' % (filename,)

    writer = csv.writer(response)
    headings = settings.AIRTIME_VOUCHER_FILE_FORMAT
    writer.writerow(headings)
    voucher_service = AirtimeVoucherService()
    voucher_list = voucher_service.export_vouchers(voucher_pool)
    for voucher in voucher_list:
        writer.writerow([
            voucher.get(headings[0], ''),
            voucher.get(headings[1], ''),
            voucher.get(headings[2], '')])

    return response


@login_required
def airtime_voucher_pool_query(request, pool_id):
    """Query the pool with the given `pool_id`"""
    voucher_pool = get_object_or_404(VoucherPool, id=pool_id,
                                     user=request.user)

    airtime_voucher_query_form = AirtimeVoucherQueryForm(request.GET)
    if airtime_voucher_query_form.is_valid():
        airtime_voucher_query_form.query(voucher_pool)

    return _render_voucher_list(
        request, airtime_voucher_query_form=airtime_voucher_query_form)
