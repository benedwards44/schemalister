from celery import Celery
settings.configure()

app = Celery('tasks', broker='amqp://wujccfeo:HUmpKc-z8lMHC2lNkE8pK0CP1-ImzAIv@bunny.cloudamqp.com/wujccfeo')

from getschema.models import Debug

@app.task
def add(x, y):
	debug = Debug()
	debug.debug = 'HELLO'
	debug.save()
	return x + y

"""
@app.task
def get_objects_and_fields(instance_url, api_version, org_id, access_token): 

	# create the schema record to store results
	schema = Schema()
	schema.org_id = org_id
	schema.api_version = str(api_version) + '.0'
	schema.status = 'Running'

	# get the org name of the authenticated user
	r = requests.get(instance_url + '/services/data/v' + str(api_version) + '.0/sobjects/Organization/' + org_id + '?fields=Name', headers={'Authorization': 'OAuth ' + access_token})
	schema.org_name = json.loads(r.text)['Name']

	schema.save()

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
		instance_url + '/services/data/v' + str(api_version) + '.0/sobjects/', 
		headers={
			'Authorization': 'Bearer ' + access_token, 
			'content-type': 'application/json'
		}
	)

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
	schema.save()

	return str(schema.id)
"""