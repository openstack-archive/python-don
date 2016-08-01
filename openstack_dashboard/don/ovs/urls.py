from django.conf.urls import patterns
from django.conf.urls import url

from don.ovs.views \
    import IndexView

from . import views


urlpatterns = patterns(
    '',
    url(r'^view/', views.view, name='view'),
    url(r'^collect/', views.collect, name='collect'),
    url(r'^ping/', views.ping, name='ping'),
    url(r'^analyze/', views.analyze, name='analyze'),
    url(r'^status/', views.get_status, name='get_status'),
    url(r'^$', IndexView.as_view(), name='index'),
)
