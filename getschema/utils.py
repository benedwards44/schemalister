from django.conf import settings

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




def get_usage_layouts(all_fields, schema):
    """
    Get all layout usage for the field
    """

    headers={
        'Authorization': 'Bearer ' + schema.access_token, 
        'content-type': 'application/json'
    }

    # Get a list of page layouts
    record_urls = get_urls_for_object(schema, 'Layout')

    # Get the metadatafor each laout
    for url in record_urls:

        # Get the metadata for the layout
        record_result = requests.get(url, headers=get_headers_for_schema(schema))

        # Convert to json object
        record_json = record_result.json()

        if 'FullName' in record_json:

            # Iterate over each field to determine if it's included in a layout
            for field in all_fields:

                layout_full_name = record_json['FullName']
                layout_object_name = layout_full_name.split('-')[0]

                # Convert all layout columns to a string
                layout_fields_string = json.dumps(record_json['Metadata']['layoutSections'])

                # If field object matches the layout object, and the field is in one of the columns
                if field.object.api_name == layout_object_name and field.api_name in layout_fields_string:
                    create_field_usage(field, 'Page Layout', record_json['Name'])



def get_usage_workflows(all_fields, schema):
    """
    Get all workflow usage
    """

    # Get a list of page layouts
    record_urls = get_urls_for_object(schema, 'WorkflowRule')

    # Get the metadatafor each laout
    for url in record_urls:

        # Get the metadata for the layout
        record_result = requests.get(url, headers=get_headers_for_schema(schema))

        # Convert to json object
        record_json = record_result.json()

        if 'FullName' in record_json:

            workflow_full_name = record_json['FullName']
            workflow_object_name = workflow_full_name.split('.')[0]

            # If a formula workflow
            if record_json['Metadata'].get('formula'):
                workflow_criteria_string = record_json['Metadata'].get('formula')
            else:
                workflow_criteria_string = json.dumps(record_json['Metadata']['criteriaItems'])

            if field.object.api_name == workflow_object_name and field.api_name in workflow_criteria_string:
                create_field_usage(field, 'Workflow', record_json['Name'])


def create_field_usage(field, type, name):

    field_usage = FieldUsage()
    field_usage.field = field
    field_usage.type = type
    field_usage.name = name
    field_usage.save()
