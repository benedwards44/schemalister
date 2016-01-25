from __future__ import absolute_import
from celery import Celery
from django.conf import settings
import os
import datetime
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schemalister.settings')

app = Celery('tasks', broker=os.environ.get('REDISTOGO_URL', 'redis://localhost'))

from getschema.models import Schema, Object, Field, Debug
from django.conf import settings
from suds.client import Client
import json	
import requests

@app.task
def get_objects_and_fields(schema): 

	instance_url = schema.instance_url
	org_id = schema.org_id
	access_token = schema.access_token

	# List of standard objects to include
	standard_objects = (
		'Account',
		'Activity',
		'Asset',
		'Campaign',
		'CampaignMember',
		'Case',
		'Contact',
		'ContentVersion',
		'Contract',
		'Event',
		'ForecastingAdjustment',
		'ForecastingQuota',
		'KnowledgeArticle',
		'Lead',
		'Opportunity',
		'OpportunityCompetitor',
		'OpportunityLineItem',
		'Order',
		'OrderItem',
		'Pricebook2',
		'PricebookEntry',
		'Product2',
		'Quote',
		'QuoteLineItem',
		'Solution',
		'Task',
		'User',
	)

	# Describe all sObjects
	all_objects = requests.get(
		instance_url + '/services/data/v' + str(settings.SALESFORCE_API_VERSION) + '.0/sobjects/', 
		headers={
			'Authorization': 'Bearer ' + access_token, 
			'content-type': 'application/json'
		}
	)

	try:

		if 'sobjects' in all_objects.json():

			# Moved logic to metadata API to get field names for fields
			metadata_client = Client('https://schemalister.herokuapp.com/static/metadata-' + str(settings.SALESFORCE_API_VERSION) + '.wsdl.xml')
			
			# URL for metadata API
			metadata_url = instance_url + '/services/Soap/m/' + str(settings.SALESFORCE_API_VERSION) + '.0/' + org_id
			
			# Set location for the client
			metadata_client.set_options(location = metadata_url)

			# Set the header for the client
			session_header = metadata_client.factory.create("SessionHeader")
			session_header.sessionId = access_token
			metadata_client.set_options(soapheaders = session_header)

			# List of names of the objects to query
			object_list = []

			# Count how many objects left
			loop_counter = 0;

			for sObject in all_objects.json()['sobjects']:

				if sObject['name'] in standard_objects or sObject['name'].endswith('__c'):

					# Create object record
					new_object = Object()
					new_object.schema = schema
					new_object.api_name = sObject['name']
					new_object.label = sObject['label']
					new_object.save()

					# Append the object to the list to query
					object_list.append(sObject['name'])

					# Run the metadata query only if the list has reached 10 (the max allowed to query)
					# at one time, or if there is less than 10 components left to query 
					if len(object_list) >= 10 or (len(all_objects.json()['sobjects']) - loop_counter) <= 10:

						# Query for the sobjects
						try:

							sobjects_result = metadata_client.service.readMetadata('CustomObject', object_list)

							# Query for the objects
							for sobject in sobjects_result[0]:

								if 'fields'in sobject:

									# Loop through fields
									for field in sobject.fields:

										if 'fullName' in field and 'label' in field:

											# Create field
											new_field = Field()
											new_field.object = new_object
											new_field.api_name = field.fullName
											new_field.label = field.label

											if 'description'in field:
												new_field.description = field['description']

											if 'inlineHelpText' in field:
												new_field.help_text = field['inlineHelpText']

											# If a formula field, set to formula and add the return type in brackets
											if 'calculated' in field and (field['calculated'] == True or field['calculated'] == 'true'):
												new_field.data_type = 'Formula (' + field['type'] + ')'

											# lookup field
											elif field['type'] == 'reference':

												new_field.data_type = 'Lookup ('

												# Could be a list of reference objects
												for referenceObject in field['referenceTo']:
													new_field.data_type = new_field.data_type + referenceObject.title() + ', '

												# remove trailing comma and add closing bracket
												new_field.data_type = new_field.data_type[:-2]
												new_field.data_type = new_field.data_type + ')'

											# picklist values
											elif field['type'] == 'picklist' or field['type'] == 'multipicklist':

												new_field.data_type = field['type'].title() + ' ('

												# Add in picklist values
												for picklist in field.picklist['picklistValues']:
													new_field.data_type = new_field.data_type + picklist['label'] + ', '

												# remove trailing comma and add closing bracket
												new_field.data_type = new_field.data_type[:-2]
												new_field.data_type = new_field.data_type + ')'

											# if text field, add field length
											elif field['type'] == 'string' or field['type'] == 'textarea':

												new_field.data_type = field['type'].title()

												# Add the field length to the title
												if 'length' in field:
													new_field.data_type += ' (' + str(field['length']) + ')'

											# If number, currency or percent
											elif field['type'] == 'double' or field['type'] == 'percent' or field['type'] == 'currency':

												new_field.data_type = field['type'].title()

												# Add the length and precision
												if 'precision' in field and 'scale' in field:

													# Determine the length
													length = int(field['precision']) - int(field['scale'])

													# Add length and scale to the field type
													new_field.data_type += ' (' + str(length) + ',' + str(field['scale']) + ')'

											else:
												new_field.data_type = field['type'].title()

											new_field.save()

						except:
							pass
							
						# Clear the object list now
						object_list = []

					# Increment the count
					loop_counter = loop_counter + 1

			schema.status = 'Finished'

		else:

			schema.status = 'Error'
			schema.error = 'There was no objects returned from the query'

			debug = Debug()
			debug.debug = all_objects.text
			debug.save()

	except Exception as error:
		schema.status = 'Error'
		schema.error = traceback.format_exc()
	
	schema.finished_date = datetime.datetime.now()
	schema.save()

	return str(schema.id)