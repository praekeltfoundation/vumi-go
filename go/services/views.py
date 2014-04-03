from django.core.files.uploadhandler import TemporaryFileUploadHandler
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from go.base.utils import get_service_view_definition


@login_required
def index(request):
    """Render the services index page"""
    # TODO: Replace this with something better.
    from go.config import _VUMI_INSTALLED_SERVICES
    return render(request, 'services/index.html', {
        'installed_services': _VUMI_INSTALLED_SERVICES})


@login_required
@csrf_exempt
def service(request, service_type, path_suffix=None):
    """Delegate request handling to the view definition of the given
    ``service_type``.
    """
    # Force uploaded files to be written to a temporary file on disk
    request.upload_handlers = [TemporaryFileUploadHandler()]
    return _service(request, service_type, path_suffix)


def _service(request, service_type, path_suffix=None):
    view_def = get_service_view_definition(service_type)
    view = view_def.get_view(path_suffix)
    return view(request)
