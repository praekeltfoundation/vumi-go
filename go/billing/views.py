from decimal import Decimal
from itertools import groupby as _groupby

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.template import RequestContext, loader

from go.billing import settings
from go.billing.models import Statement


def groupby(values, fn):
    values = sorted(values, key=fn)
    return [(k, list(g)) for k, g in _groupby(values, fn)]


def ensure_decimal(v):
    return v if v is not None else Decimal('0.0')


def totals_from_items(items):
    if not items:
        return {
            'cost': Decimal('0.0'),
            'credits': Decimal('0.0')
        }
    else:
        return {
            'cost': sum(ensure_decimal(item.cost) for item in items),
            'credits': sum(ensure_decimal(item.credits) for item in items),
        }


def sections_from_items(all_items):
    all_items = sorted(all_items, key=lambda d: d.channel)
    sections = groupby(all_items, lambda line: line.channel)

    sections = [{
        'name': name,
        'totals': totals_from_items(items),
        'items': list(sorted(items, key=lambda d: d.description)),
    } for name, items in sections]

    return sections


def billers_from_items(all_items):
    billers = [{
        'name': name,
        'channel_type': items[0].channel_type,
        'sections': sections_from_items(items)
    } for name, items in groupby(all_items, lambda d: d.billed_by)]

    system_biller = next(
        (b for b in billers if b['name'] == settings.SYSTEM_BILLER_NAME),
        None)

    if system_biller is not None:
        billers.remove(system_biller)
        billers.append(system_biller)

    return billers


@login_required
def statement_view(request, statement_id=None):
    statement = get_object_or_404(Statement, pk=statement_id)
    items = list(statement.lineitem_set.all())

    if not (request.user.is_staff or
            statement.account.user == request.user):
        raise Http404

    template = loader.get_template('billing/invoice.html')

    context = RequestContext(request, {
        'statement': statement,
        'totals': totals_from_items(items),
        'billers': billers_from_items(items),
        'contact_details': settings.STATEMENT_CONTACT_DETAILS,
    })

    html_result = template.render(context)
    return HttpResponse(html_result)
