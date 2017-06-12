from django.conf import settings

from .models import FieldUsage

import requests
import json



def get_headers_for_schema(schema):
    return {
        'Authorization': 'Bearer ' + schema.access_token, 
        'Content-Type': 'application/json'
    }


def get_urls_for_object(schema, object_name):
    """
    For a given object type, get the list of describe URLs
    """

    records = requests.get(
        schema.instance_url + '/services/data/v' + str(settings.SALESFORCE_API_VERSION) + '.0/tooling/query/?q=SELECT+Id+FROM+' + object_name, 
        headers=get_headers_for_schema(schema)
    )

    record_urls = []

    if 'records' in records.json():
        # Iterate over the list of objects
        for record in records.json()['records']:
            record_url = schema.instance_url + record['attributes']['url']
            record_urls.append(record_url)

    return record_urls


def get_usage_for_component(all_fields, schema, component_name):
    """
    Get the usage for the specific component
    """

    # Get Metadata for each record for the component
    for url in get_urls_for_object(schema, component_name):

        # Get the metadata for the layout
        record_result = requests.get(url, headers=get_headers_for_schema(schema))

        # Convert to json object
        record_json = record_result.json()

        if 'FullName' in record_json:

            # Iterate over each field to determine if it's included in a layout
            for field in all_fields:

                # Get all required values
                full_name = record_json['FullName']
                object_name = get_object_name(full_name, component_name)
                record_string = get_record_string(record_json, component_name)
                field_name = get_field_name(field, component_name)

                # See if the field exists in the metadata
                if (field.object.api_name == object_name or not object_name) and field_name in record_string:
                    create_field_usage(field, component_name, record_json['Name'])



def get_object_name(full_name, component_name):
    """
    Returns the object name for the given Metadata component
    """
    if component_name == 'Layout':
        return full_name.split('-')[0]
    elif component_name in ['WorkflowRule','WorkflowFieldUpdate']:
        return full_name.split('.')[0]
    return None



def get_record_string(record_json, component_name):
    """
    Returns the record string to see if the field exists inside it
    """

    record_string = None

    if component_name == 'Layout':
        record_string = json.dumps(record_json['Metadata']['layoutSections'])

    elif component_name == 'WorkflowRule':
        if record_json['Metadata'].get('formula'):
            record_string = record_json['Metadata'].get('formula')
        else:
            record_string = json.dumps(record_json['Metadata']['criteriaItems'])

    elif component_name == 'WorkflowFieldUpdate': 
        record_string = json.dumps(record_json['Metadata'])

    elif component_name == 'EmailTemplate':
        record_string = record_json.get('Subject','') + ' ' + record_json['Metadata'].get('textOnly','')

    return record_string


def get_field_name(field, component_name):
    """
    Get the field name to check for in the component
    """
    if component_name == 'EmailTemplate':
        return '{!%s.%s}' % (field.object.api_name, field.api_name)
    return field.api_name



def create_field_usage(field, type, name):
    """
    Create the field usage record
    """

    component_type_to_name = {
        'EmailTemplate': 'Email Template',
        'Layout': 'Page Layout',
        'WorkflowRule': 'Workflow',
        'WorkflowFieldUpdate': 'Field Update'
    }

    field_usage = FieldUsage()
    field_usage.field = field
    field_usage.type = component_type_to_name[type]
    field_usage.name = name
    field_usage.save()


