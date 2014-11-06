from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseRedirect
from getschema.models import Schema, Object, Field, Debug
from getschema.forms import LoginForm
from django.conf import settings
from getschema.tasks import get_objects_and_fields
import json	
import requests
from time import sleep

def index(request):
	
	if request.method == 'POST':

		login_form = LoginForm(request.POST)

		if login_form.is_valid():

			environment = login_form.cleaned_data['environment']
			api_version = login_form.cleaned_data['api_version']

			oauth_url = 'https://login.salesforce.com/services/oauth2/authorize'
			if environment == 'Sandbox':
				oauth_url = 'https://test.salesforce.com/services/oauth2/authorize'

			oauth_url = oauth_url + '?response_type=code&client_id=' + settings.SALESFORCE_CONSUMER_KEY + '&redirect_uri=' + settings.SALESFORCE_REDIRECT_URI + '&state='+ environment + str(api_version)
			
			return HttpResponseRedirect(oauth_url)
	else:
		login_form = LoginForm()

	return render_to_response('index.html', RequestContext(request,{'login_form': login_form}))

def oauth_response(request):

	error_exists = False
	error_message = ''
	username = ''
	org_name = ''

	# On page load
	if request.GET:

		oauth_code = request.GET.get('code')
		environment = request.GET.get('state')[:-2]
		api_version = request.GET.get('state')[-2:]
		access_token = ''
		instance_url = ''
		org_id = ''

		if 'Production' in environment:
			login_url = 'https://login.salesforce.com'
		else:
			login_url = 'https://test.salesforce.com'
		
		r = requests.post(login_url + '/services/oauth2/token', headers={ 'content-type':'application/x-www-form-urlencoded'}, data={'grant_type':'authorization_code','client_id': settings.SALESFORCE_CONSUMER_KEY,'client_secret':settings.SALESFORCE_CONSUMER_SECRET,'redirect_uri': settings.SALESFORCE_REDIRECT_URI,'code': oauth_code})
		auth_response = json.loads(r.text)

		if 'error_description' in auth_response:
			error_exists = True
			error_message = auth_response['error_description']
		else:
			access_token = auth_response['access_token']
			instance_url = auth_response['instance_url']
			user_id = auth_response['id'][-18:]
			org_id = auth_response['id'][:-19]
			org_id = org_id[-18:]

			# get username of the authenticated user
			r = requests.get(instance_url + '/services/data/v' + api_version + '.0/sobjects/User/' + user_id + '?fields=Username', headers={'Authorization': 'OAuth ' + access_token})
			query_response = json.loads(r.text)
			username = query_response['Username']

			# get the org name of the authenticated user
			r = requests.get(instance_url + '/services/data/v' + api_version + '.0/sobjects/Organization/' + org_id + '?fields=Name', headers={'Authorization': 'OAuth ' + access_token})
			org_name = json.loads(r.text)['Name']

		login_form = LoginForm(initial={'environment': environment, 'api_version': api_version, 'access_token': access_token, 'instance_url': instance_url, 'org_id': org_id})	

	# Run after user selects logout or get schema
	if request.POST:

		login_form = LoginForm(request.POST)

		if login_form.is_valid():

			environment = login_form.cleaned_data['environment']
			api_version = login_form.cleaned_data['api_version']
			access_token = login_form.cleaned_data['access_token']
			instance_url = login_form.cleaned_data['instance_url']
			org_id = login_form.cleaned_data['org_id']

			if 'logout' in request.POST:

				if 'Production' in environment:
					login_url = 'https://login.salesforce.com'
				else:
					login_url = 'https://test.salesforce.com'

				r = requests.post(login_url + '/services/oauth2/revoke', headers={'content-type':'application/x-www-form-urlencoded'}, data={'token': access_token})
				return HttpResponseRedirect('/logout?environment=' + environment)

			if 'get_schema' in request.POST:

				# Create schema record
				schema = Schema()
				schema.org_id = org_id
				schema.api_version = str(api_version) + '.0'
				schema.org_name = org_name
				schema.status = 'Running'
				schema.save()

				# Queue job to run async
				try:
					get_objects_and_fields.delay(schema, instance_url, api_version, org_id, access_token)
				except:
					# If fail above, wait 5 seconds and try again. Not ideal but should work for now
					sleep(5)
					try:
						get_objects_and_fields.delay(schema, instance_url, api_version, org_id, access_token)
					except:
						# Sleep another 5
						sleep(5)
						get_objects_and_fields.delay(schema, instance_url, api_version, org_id, access_token)

				return HttpResponseRedirect('/loading/' + str(schema.id))

	return render_to_response('oauth_response.html', RequestContext(request,{'error': error_exists, 'error_message': error_message, 'username': username, 'org_name': org_name, 'login_form': login_form}))

# AJAX endpoint for page to constantly check if job is finished
def job_status(request, schema_id):
	schema = get_object_or_404(Schema, pk=schema_id)
	return HttpResponse(schema.status + ':' + schema.error)

# Page for user to wait for job to run
def loading(request, schema_id):

	schema = get_object_or_404(Schema, pk=schema_id)

	# If finished already (unlikely) direct to schema view
	if schema.status == 'Finished':
		return HttpResponseRedirect('/schema/' + str(schema.id))
	else:
		return render_to_response('loading.html', RequestContext(request, {'schema': schema}))	

def view_schema(request, schema_id):
	# Pass the schema to the page but delete it after view - it's not nice to store Orgs data models
	schema = get_object_or_404(Schema, pk=schema_id)
	return render_to_response('schema.html', RequestContext(request,{'schema': schema}))

def delete_schema(request, schema_id):

	try:
		schema = Schema.objects.get(pk = schema_id)
		schema.delete()
	except:
		pass

	return HttpResponse('Record deleted')

def logout(request):

	# Determine logout url based on environment
	environment = request.GET.get('environment')

	if 'Production' in environment:
		logout_url = 'https://login.salesforce.com'
	else:
		logout_url = 'https://test.salesforce.com'
		
	return render_to_response('logout.html', RequestContext(request, {'logout_url': logout_url}))

