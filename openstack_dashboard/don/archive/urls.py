from django.conf.urls import patterns
from django.conf.urls import url
from don.archive.views \
    import ArchiveView
from . import views

urlpatterns = patterns(
    '',
    # url(r'^dbview/',DBView.as_view() , name='dbview'),
    url(r'^dbview/', views.dbview, name='dbview'),
    url(r'^$', ArchiveView.as_view(), name='index'),

)
