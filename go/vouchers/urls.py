from django.conf.urls.defaults import patterns, url

from go.vouchers import views

urlpatterns = patterns(
    '',
    url(r'^$', views.voucher_list, name='voucher_list'),
    url(r'^airtime/add$', views.airtime_voucher_pool_add,
        name='airtime_add'),
    url(r'^airtime/import/(?P<pool_id>\d+)/$',
        views.airtime_voucher_pool_import,
        name='airtime_import'),
)
