from itertools import groupby as _groupby

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.template import RequestContext, loader

from go.billing import settings
from go.billing.models import Statement


def groupby(values, fn):
    return sorted([(k, list(g)) for k, g in _groupby(values, fn)])


def totals_from_items(items):
    return {
        'cost': sum(item.cost for item in items),
        'credits': sum(item.credits for item in items),
    }


def channels_from_items(all_items):
    return [{
        'name': name,
        'items': sorted(items, key=lambda d: d.description),
        'totals': totals_from_items(items)
    } for name, items in groupby(all_items, lambda line: line.channel)]


def billers_from_items(all_items):
    return [{
        'name': name,
        'channel_type': items[0].channel_type,
        'channels': channels_from_items(items)
    } for name, items in groupby(all_items, lambda d: d.billed_by)]


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
