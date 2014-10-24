import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template import RequestContext, loader
from xhtml2pdf import pisa


from go.billing.models import Statement


@login_required
def statement_view(request, statement_id=None):
    """Send a PDF version of the statement with the given
       ``statement_id`` to the user's browser.
    """
    statement = get_object_or_404(
        Statement, pk=statement_id, account__user=request.user)

    response = HttpResponse(mimetype='application/pdf')
    filename = "%s (%s).pdf" % (statement.title,
                                statement.from_date.strftime('%B %Y'))

    response['Content-Disposition'] = 'attachment; filename=%s' % (filename,)

    template = loader.get_template('billing/invoice.html')
    line_item_list = statement.lineitem_set.all()
    context = RequestContext(request, {'item_list': line_item_list})
    html_result = template.render(context)

    pisa.CreatePDF(html_result, dest=response, link_callback=link_callback)

    return response


# Convert HTML URIs to absolute system paths so xhtml2pdf can access those
# resources
def link_callback(uri, rel):
    # use short variable names
    sUrl = settings.STATIC_URL    # Typically /static/
    sRoot = settings.STATIC_ROOT  # Typically /home/userX/project_static/
    mUrl = settings.MEDIA_URL     # Typically /static/media/
    mRoot = settings.MEDIA_ROOT   # Typically /home/userX/project_static/media/

    # convert URIs to absolute system paths
    if uri.startswith(mUrl):
        path = os.path.join(mRoot, uri.replace(mUrl, ""))
    elif uri.startswith(sUrl):
        path = os.path.join(sRoot, uri.replace(sUrl, ""))

    # make sure that file exists
    if not os.path.isfile(path):
            raise Exception(
                'media URI must start with %s or %s' % (sUrl, mUrl))
    return path
