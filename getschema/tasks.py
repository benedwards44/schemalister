from __future__ import absolute_import
from celery import Celery
from django.conf import settings
import os
import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schemalister.settings')

app = Celery('tasks', broker=os.environ.get('REDISTOGO_URL', 'redis://localhost'))

from getschema.models import Schema, Object, Field, Debug
from django.conf import settings
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

			for sObject in all_objects.json()['sobjects']:

				if sObject['name'] in standard_objects or sObject['name'].endswith('__c'):

					# Create object record
					new_object = Object()
					new_object.schema = schema
					new_object.api_name = sObject['name']
					new_object.label = sObject['label']
					new_object.save()

					# query for fields in the object
					all_fields = requests.get(instance_url + sObject['urls']['describe'], headers={'Authorization': 'Bearer ' + access_token, 'content-type': 'application/json'})

					# Loop through fields
					for field in all_fields.json()['fields']:

						# Create field
						new_field = Field()
						new_field.object = new_object
						new_field.api_name = field['name']
						new_field.label = field['label']
						new_field.help_text = field['inlineHelpText']

						# lookup field
						if field['type'] == 'reference':
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
							for picklist in field['picklistValues']:
								new_field.data_type = new_field.data_type + picklist['label'] + ', '

							# remove trailing comma and add closing bracket
							new_field.data_type = new_field.data_type[:-2]
							new_field.data_type = new_field.data_type + ')'

						# everything else	
						else:
							new_field.data_type = field['type'].title()

						new_field.save()

			schema.status = 'Finished'

		else:

			schema.status = 'Error'
			schema.error = 'There was no objects returned from the query'

			debug = Debug()
			debug.debug = all_objects.text
			debug.save()


	except Exception as error:
		schema.status = 'Error'
		schema.error = error
	
	schema.finished_date = datetime.datetime.now()
	schema.save()

	return str(schema.id)