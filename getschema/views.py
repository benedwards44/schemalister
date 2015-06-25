from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from getschema.models import Schema, Object, Field, Debug
from getschema.forms import LoginForm
from django.conf import settings
from getschema.tasks import get_objects_and_fields
import json	
import requests
import datetime
from time import sleep
import uuid
from xlsxwriter.workbook import Workbook

try:
	import cStringIO as StringIO
except ImportError:
	import StringIO

def index(request):
	
	if request.method == 'POST':

		login_form = LoginForm(request.POST)

		if login_form.is_valid():

			environment = login_form.cleaned_data['environment']

			oauth_url = 'https://login.salesforce.com/services/oauth2/authorize'
			if environment == 'Sandbox':
				oauth_url = 'https://test.salesforce.com/services/oauth2/authorize'

			oauth_url = oauth_url + '?response_type=code&client_id=' + settings.SALESFORCE_CONSUMER_KEY + '&redirect_uri=' + settings.SALESFORCE_REDIRECT_URI + '&scope=api&state='+ environment
			
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
		environment = request.GET.get('state')
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
			error_message = auth_response['error'] + ' - ' + auth_response['error_description']
		else:
			access_token = auth_response['access_token']
			instance_url = auth_response['instance_url']
			user_id = auth_response['id'][-18:]
			org_id = auth_response['id'][:-19]
			org_id = org_id[-18:]

			# get username of the authenticated user
			r = requests.get(instance_url + '/services/data/v' + str(settings.SALESFORCE_API_VERSION) + '.0/sobjects/User/' + user_id + '?fields=Username', headers={'Authorization': 'OAuth ' + access_token})
			query_response = json.loads(r.text)
			username = query_response['Username']

			# get the org name of the authenticated user
			r = requests.get(instance_url + '/services/data/v' + str(settings.SALESFORCE_API_VERSION) + '.0/sobjects/Organization/' + org_id + '?fields=Name', headers={'Authorization': 'OAuth ' + access_token})
			org_name = json.loads(r.text)['Name']

		login_form = LoginForm(initial={'environment': environment, 'access_token': access_token, 'instance_url': instance_url, 'org_id': org_id})	

	# Run after user selects logout or get schema
	if request.POST:

		login_form = LoginForm(request.POST)

		if login_form.is_valid():

			environment = login_form.cleaned_data['environment']
			access_token = login_form.cleaned_data['access_token']
			instance_url = login_form.cleaned_data['instance_url']
			org_id = login_form.cleaned_data['org_id']

			if 'logout' in request.POST:

				r = requests.post(instance_url + '/services/oauth2/revoke', headers={'content-type':'application/x-www-form-urlencoded'}, data={'token': access_token})
				return HttpResponseRedirect('/logout?instance_prefix=' + instance_url.replace('https://','').replace('.salesforce.com',''))

			if 'get_schema' in request.POST:

				# Create schema record
				schema = Schema()
				schema.random_id = uuid.uuid4()
				schema.created_date = datetime.datetime.now()
				schema.org_id = org_id
				schema.org_name = org_name
				schema.access_token = access_token
				schema.instance_url = instance_url
				schema.status = 'Running'
				schema.save()

				# Queue job to run async
				try:
					get_objects_and_fields.delay(schema)
				except:
					# If fail above, wait 5 seconds and try again. Not ideal but should work for now
					sleep(5)
					try:
						get_objects_and_fields.delay(schema)
					except Exception as error:
						# Sleep another 5
						sleep(5)
						schema.status = 'Error'
						schema.error = error
						schema.save()

				return HttpResponseRedirect('/loading/' + str(schema.random_id))

	return render_to_response('oauth_response.html', RequestContext(request,{'error': error_exists, 'error_message': error_message, 'username': username, 'org_name': org_name, 'login_form': login_form}))

# AJAX endpoint for page to constantly check if job is finished
def job_status(request, schema_id):

	schema = get_object_or_404(Schema, random_id = schema_id)

	response_data = {
		'status': schema.status,
		'error': schema.error
	}

	return HttpResponse(json.dumps(response_data), content_type = 'application/json')

# Page for user to wait for job to run
def loading(request, schema_id):

	schema = get_object_or_404(Schema, random_id = schema_id)

	# If finished already (unlikely) direct to schema view
	if schema.status == 'Finished':

		# Return URL when job is finished
		return_url = '/schema/' + str(schema.random_id) + '/'

		# If no header is in URL, keep it there
		if request.GET.noheader == '1':
			return_url += '?noheader=1'

		return HttpResponseRedirect(return_url)
	else:
		return render_to_response('loading.html', RequestContext(request, {'schema': schema}))	

def view_schema(request, schema_id):

	# Pass the schema to the page but delete it after view - it's not nice to store Orgs data models
	schema = get_object_or_404(Schema, random_id = schema_id)

	return render_to_response('schema.html', RequestContext(request,{'schema': schema}))


def export(request, schema_id):
	""" 
		Generate a XLSX file for download
	"""

	# Query for schema
	schema = get_object_or_404(Schema, random_id = schema_id)

	# Generate output string
	output = StringIO.StringIO()

	# Create workbook
	book = Workbook(output)

	# Set up bold format
	bold = book.add_format({'bold': True})

	# create a sheet for each object
	for obj in schema.sorted_objects():

		# Create sheet
		sheet = book.add_worksheet(obj.api_name[:31])	   

		# Write column headers
		sheet.write(0, 0, 'Field Label', bold)
		sheet.write(0, 1, 'API Name', bold)
		sheet.write(0, 2, 'Type', bold)

		for index, field in enumerate(obj.sorted_fields()):

			#sheet.write(0, 0, field.label)
			pass

	# Close the book
	book.close()
	
	# construct response
	output.seek(0)
	response = HttpResponse(output.read(), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
	response['Content-Disposition'] = "attachment; filename=schema.xlsx"

	return response

def delete_schema(request, schema_id):

	try:
		schema = Schema.objects.get(random_id = schema_id)
		schema.delete()
	except:
		pass

	return HttpResponse('Record deleted')

def logout(request):

	# Determine logout url based on environment
	instance_prefix = request.GET.get('instance_prefix')
		
	return render_to_response('logout.html', RequestContext(request, {'instance_prefix': instance_prefix}))


@csrf_exempt
def auth_details(request):
	"""
		RESTful endpoint to pass authentication details
	"""

	try:

		request_data = json.loads(request.body)

		# Check for all required fields
		if 'org_id' not in request_data or 'access_token' not in request_data or 'instance_url' not in request_data:

			response_data = {
				'status': 'Error',
				'success':  False,
				'error_text': 'Not all required fields were found in the message. Please ensure org_id, access_token and instance_url are all passed in the payload'
			}

		# All fields exist. Start job and send response
		else:

			# create the schema record to store results
			schema = Schema()
			schema.random_id = uuid.uuid4()
			schema.created_date = datetime.datetime.now()
			schema.org_id = request_data['org_id']
			schema.access_token = request_data['access_token']
			schema.instance_url = request_data['instance_url']
			schema.status = 'Running'

			# get the org name of the authenticated user
			r = requests.get(schema.instance_url + '/services/data/v' + str(settings.SALESFORCE_API_VERSION) + '.0/sobjects/Organization/' + schema.org_id + '?fields=Name', headers={'Authorization': 'OAuth ' + schema.access_token})
			schema.org_name = json.loads(r.text)['Name']

			# Save the schema
			schema.save()

			# Run job
			get_objects_and_fields.delay(schema)

			# Build response 
			response_data = {
				'job_url': 'https://schemalister.herokuapp.com/loading/' + str(schema.random_id) + '/?noheader=1',
				'status': 'Success',
				'success': True
			}

	except Exception as error:

		# If there is an error, raise exception and return
		response_data = {
			'status': 'Error',
			'success':  False,
			'error_text': str(error)
		}
	
	return HttpResponse(json.dumps(response_data), content_type = 'application/json')
