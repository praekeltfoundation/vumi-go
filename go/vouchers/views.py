from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from go.vouchers.models import AirtimeVoucherPool, UniqueCodePool
from go.vouchers.forms import AirtimeVoucherPoolForm


@login_required
def voucher_list(request):
    """Display a list of Airtime Vouchers and Unique Codes"""

    airtime_voucher_pool_form = None
    if request.method == 'POST':
        if 'upload-airtime-vouchers' in request.POST:
            airtime_voucher_pool_form = AirtimeVoucherPoolForm(
                request.POST, request.FILES, user=request.user)

            if airtime_voucher_pool_form.is_valid():
                airtime_voucher_pool_form.save()
                return redirect('vouchers:voucher_list')

    airtime_voucher_pool_list = AirtimeVoucherPool.objects.filter(
        user=request.user)

    unique_code_pool_list = UniqueCodePool.objects.filter(
        user=request.user)

    if not airtime_voucher_pool_form:
        airtime_voucher_pool_form = AirtimeVoucherPoolForm(
            user=request.user)

    return render(request, 'vouchers/voucher_list.html', {
        'airtime_voucher_pool_list': airtime_voucher_pool_list,
        'airtime_voucher_pool_form': airtime_voucher_pool_form,
        'unique_code_pool_list': unique_code_pool_list,
    })
