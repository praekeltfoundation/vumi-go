from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from go.vouchers.models import AirtimeVoucherPool, UniqueCodePool
from go.vouchers.forms import AirtimeVoucherPoolForm, AirtimeVoucherImportForm


def _render_voucher_list(
        request, template_name='vouchers/voucher_list.html',
        *args, **kwargs):
    context = {}
    context.update(kwargs)
    if 'airtime_voucher_pool_list' not in context:
        context['airtime_voucher_pool_list'] = \
            AirtimeVoucherPool.objects.filter(user=request.user)

    if 'airtime_voucher_pool_form' not in context:
        context['airtime_voucher_pool_form'] = AirtimeVoucherPoolForm()

    if 'airtime_voucher_import_form' not in context:
        context['airtime_voucher_import_form'] = AirtimeVoucherImportForm()

    if 'unique_code_pool_list' not in context:
        context['unique_code_pool_list'] = \
            UniqueCodePool.objects.filter(user=request.user)

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
    airtime_voucher_pool = get_object_or_404(AirtimeVoucherPool, id=pool_id)
    if request.method == 'POST':
        airtime_voucher_import_form = AirtimeVoucherImportForm(
            request.POST, request.FILES, instance=airtime_voucher_pool)

        if airtime_voucher_import_form.is_valid():
            airtime_voucher_import_form.save()
            return redirect('vouchers:voucher_list')

        return _render_voucher_list(
            request, airtime_voucher_import_form=airtime_voucher_import_form)
    else:
        return redirect('vouchers:voucher_list')
