from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView, RedirectView
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'schemalister.views.index', name='index'),
    url(r'^oauth_response/$', 'schemalister.views.oauth_response', name='oauth_response'),
    url(r'^schema/(?P<schema_id>\d+)/$', 'schemalister.views.view_schema', name='view_schema'),
    url(r'^logout/$', 'schemalister.views.logout', name='logout'),
    url(r'^admin/', include(admin.site.urls)),
)
