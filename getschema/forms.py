from django import forms
from django.forms import ModelForm

class LoginForm(forms.Form):
	environment = forms.CharField(required=False);
	access_token = forms.CharField(required=False)
	instance_url = forms.CharField(required=False)
	org_id = forms.CharField(required=False)
	include_field_usage = forms.BooleanField(required=False)
	include_managed_objects = forms.BooleanField(required=False)