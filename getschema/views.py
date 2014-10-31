from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.http import HttpResponseRedirect
from getschema.models import Schema, Object, Field, Debug
from getschema.forms import LoginForm
from django.conf import settings
from suds.client import Client
import json	
import requests

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
			r = requests.get(instance_url + '/services/data/v' + api_version + '.0/sobjects/User/' + user_id + '?fields=Username', headers={'Authorization': 'OAuth ' + access_token})
			query_response = json.loads(r.text)
			username = query_response['Username']

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

				# instantiate the metadata WSDL
				partner_client = Client('http://schemalister.herokuapp.com/static/partner32.wsdl.xml')

				partner_url = instance_url + '/services/Soap/u/' + str(api_version) + '.0/' + org_id

				# set the metadata url based on the login result
				partner_client.set_options(location = partner_url)

				# set the session id from the login result
				session_header = partner_client.factory.create("SessionHeader")
				session_header.sessionId = access_token
				partner_client.set_options(soapheaders = session_header)
				
				# create the schema record to store results
				schema = Schema()
				schema.org_id = org_id
				schema.api_version = str(api_version) + '.0'
				schema.save()

				standard_objects = (
					'Account',
					'AccountContactRole',
					'Activity',
					'Asset',
					'Campaign',
					'CampaignMember',
					'Case',
					'CaseContactRole',
					'Contact',
					'ContentVersion',
					'Contract',
					'ContractContactRole',
					'Event',
					'ForecastingAdjustment',
					'ForecastingQuota',
					'Lead',
					'Opportunity',
					'OpportunityCompetitor',
					'OpportunityContactRole',
					'OpportunityLineItem',
					'Order',
					'OrderItem',
					'PartnerRole',
					'Pricebook2',
					'PricebookEntry',
					'Product2',
					'Quote',
					'QuoteLineItem',
					'Site',
					'SocialPersona',
					'Solution',
					'Task',
					'User',
				)

				object_list = []
				loop_counter = 0

				sf_object_list = partner_client.service.describeGlobal().sobjects

				# Build list of objects
				for sf_object in sf_object_list:

					# only add standard objects listed or custom objects
					if sf_object.name in standard_objects or sf_object.name.endswith('__c'):
						object_list.append(sf_object.name)

					# Can only query 10 objects at a time
					if len(object_list) == 100 or (len(sf_object_list) - loop_counter) <= 100:

						for object in partner_client.service.describeSObjects(object_list):

							new_object = Object()
							new_object.schema = schema
							new_object.api_name = object.name
							try:
								new_object.label = object.label
							# skip record if no label
							except:
								continue

							new_object.save()

							try:

								for field in object.fields:

									new_field = Field()
									new_field.object = new_object
									new_field.api_name = field.name

									try:
										new_field.label = field.label
									except:
										new_field.label = field.name
									
									try:

										new_field.data_type = field.type.title()

										if new_field.data_type == 'Picklist' or new_field.data_type == 'Multipicklist':

											new_field.data_type = new_field.data_type + ' ('

											for picklist_value in field.picklistValues:
												new_field.data_type = new_field.data_type + picklist_value.label + ', '

											new_field.data_type = new_field.data_type[:-2]
											new_field.data_type = new_field.data_type + ')'

										elif new_field.data_type == 'Reference':

											new_field.data_type = 'Lookup ('

											for reference_to in field.referenceTo:
												new_field.data_type = new_field.data_type + reference_to + ', '

											new_field.data_type = new_field.data_type[:-2]
											new_field.data_type = new_field.data_type + ')'

									except:
										pass

									new_field.save()

							# object with no fields - may as well delete
							except:
								new_object.delete()

						object_list = []

					loop_counter = loop_counter + 1

				return HttpResponseRedirect('/schema/' + str(schema.id))

	return render_to_response('oauth_response.html', RequestContext(request,{'error': error_exists, 'error_message': error_message, 'username': username, 'login_form': login_form}))

def view_schema(request, schema_id):

	# Pass the schema to the page but delete it after view - it's not nice to store Orgs data models
	schema = get_object_or_404(Schema, pk=schema_id)
	#schema_for_delete = Schema.objects.get(pk=schema_id)
	#if(fm.elements['Email'].value.indexOf("tquila.com") == -1 && fm.elements['Email'].value.indexOf("salesforce.com") == -1){ArErrMsg['Email']="Please enter a valid email address";}schema_for_delete.delete()

	return render_to_response('schema.html', RequestContext(request,{'schema': schema}))

def logout(request):

	# Determine logout url based on environment
	environment = request.GET.get('environment')

	if 'Production' in environment:
		logout_url = 'https://login.salesforce.com'
	else:
		logout_url = 'https://test.salesforce.com'
		
	return render_to_response('logout.html', RequestContext(request, {'logout_url': logout_url}))

