from django.urls import path, include
from django.views.generic import TemplateView, RedirectView
from django.contrib import admin

from getschema import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('oauth_response/', views.oauth_response, name='oauth_response'),
    path('schema/<str:schema_id>/', views.view_schema, name='view_schema'),
    path('export/<str:schema_id>/', views.export, name='export'),
    path('logout/', views.logout, name='logout'),
    path('job_status/<str:schema_id>/', views.job_status),
    path('loading/<str:schema_id>/', views.loading),
    path('delete_schema/<str:schema_id>/', views.delete_schema, name='delete_schema'),
    path('auth_details/', views.auth_details),
]
