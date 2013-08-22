from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages

from go.router.forms import NewRouterForm
from go.base.utils import get_router_view_definition, router_or_404


ROUTERS_PER_PAGE = 12


@login_required
def index(request):
    # grab the fields from the GET request
    user_api = request.user_api

    routers = sorted(user_api.active_routers(), key=lambda r: r.name)

    paginator = Paginator(routers, ROUTERS_PER_PAGE)
    try:
        page = paginator.page(request.GET.get('p', 1))
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    return render(request, 'router/dashboard.html', {
        'routers': routers,
        'paginator': paginator,
        'pagination_params': '',
        'page': page,
    })


@login_required
def router(request, router_key, path_suffix):
    router = router_or_404(request.user_api, router_key)
    view_def = get_router_view_definition(router.router_type, router)
    view = view_def.get_view(path_suffix)
    return view(request, router)


@login_required
def new_router(request):
    if request.method == 'POST':
        form = NewRouterForm(request.user_api, request.POST)
        if form.is_valid():
            router_type = form.cleaned_data['router_type']

            view_def = get_router_view_definition(router_type)
            router = request.user_api.new_router(
                router_type, name=form.cleaned_data['name'],
                description=form.cleaned_data['description'], config={},
                extra_inbound_endpoints=list(
                    view_def.extra_static_inbound_endpoints),
                extra_outbound_endpoints=list(
                    view_def.extra_static_outbound_endpoints),
            )
            messages.info(request, 'Conversation created successfully.')

            # Get a new view_def with a conversation object in it.
            view_def = get_router_view_definition(
                router.router_type, router)

            next_view = 'show'
            if view_def.is_editable:
                next_view = 'edit'

            return redirect(view_def.get_view_url(
                next_view, router_key=router.key))
    else:
        form = NewRouterForm(request.user_api)
    return render(request, 'router/new.html', {
        'router_form': form,
    })
