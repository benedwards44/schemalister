from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView, RedirectView
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'getschema.views.index', name='index'),
    url(r'^oauth_response/$', 'getschema.views.oauth_response', name='oauth_response'),
    url(r'^schema/(?P<schema_id>[0-9A-Za-z_\-]+)/$', 'getschema.views.view_schema', name='view_schema'),
    url(r'^logout/$', 'getschema.views.logout', name='logout'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^job_status/(?P<schema_id>[0-9A-Za-z_\-]+)/$', 'getschema.views.job_status'),
    url(r'^loading/(?P<schema_id>[0-9A-Za-z_\-]+)/$', 'getschema.views.loading'),
    url(r'^delete_schema/(?P<schema_id>[0-9A-Za-z_\-]+)/$', 'getschema.views.delete_schema', name='delete_schema'),
)
