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

    url = schema.instance_url + '/services/data/v' + str(settings.SALESFORCE_API_VERSION) + '.0/tooling/query/?q=SELECT+Id+FROM+' + object_name

    if object_name in ['ApexClass','ApexPage','ApexComponent','ApexTrigger']:
        url += '+WHERE+NamespacePrefix=null'

    records = requests.get(
        url, 
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

        if 'Name' in record_json and 'FullName' in record_json:

            # Iterate over each field to determine if it's included in a layout
            for field in all_fields:

                # Get all required values
                full_name = record_json['FullName']
                object_name = get_object_name(full_name, component_name, record_json)
                record_string = get_record_string(record_json, component_name)
                field_name = get_field_name(field, component_name)

                # See if the field exists in the metadata
                if (field.object.api_name == object_name or not object_name) and field_name in record_string:
                    create_field_usage(field, component_name, record_json['Name'])



def get_object_name(full_name, component_name, record_json):
    """
    Returns the object name for the given Metadata component
    """
    object_name = None

    if component_name == 'Layout':
        object_name = full_name.split('-')[0]

    elif component_name in ['WorkflowRule','WorkflowFieldUpdate','WorkflowOutboundMessage']:
        object_name = full_name.split('.')[0]

    elif component_name == 'Flow':
        object_name = record_json.get('Metadata').get('processMetadataValues')[0].get('value').get('stringValue')

    elif component_name == 'ApexTrigger':
        object_name = record_json.get('TableEnumOrId', None)

    return object_name



def get_record_string(record_json, component_name):
    """
    Returns the record string to see if the field exists inside it
    """

    record_string = ''

    try:

        if component_name == 'Layout':
            record_string = json.dumps(record_json['Metadata']['layoutSections'])

        elif component_name == 'WorkflowRule':
            if record_json['Metadata'].get('formula'):
                record_string = record_json['Metadata'].get('formula')
            else:
                record_string = json.dumps(record_json['Metadata']['criteriaItems'])

        elif component_name == 'WorkflowFieldUpdate': 
            record_string = json.dumps(record_json['Metadata'])

        elif component_name == 'WorkflowOutboundMessage':
            record_string = json.dumps(record_json['Metadata']['fields'])

        elif component_name == 'EmailTemplate':
            subject = str(record_json['Metadata'].get('subject',''))
            text_content = str(record_json['Metadata'].get('textOnly',''))
            record_string = subject + ' ' + text_content

        elif component_name == 'Flow':
            record_string = json.dumps(record_json['Metadata'])

        elif component_name in ['ApexClass', 'ApexTrigger']:
            record_string = record_json.get('Body','')

        elif component_name in ['ApexPage','ApexComponent']:
            record_string = record_json.get('Markup','')

    except:
        pass

    return record_string


def get_field_name(field, component_name):
    """
    Get the field name to check for in the component
    """
    if component_name == 'EmailTemplate':
        # Eg {!Contact.FirstName}
        return '{!%s.%s}' % (field.object.api_name, field.api_name)
    elif component_name in ['ApexClass','ApexComponent','ApexPage','ApexTrigger']:
        # Prepend field names with a . to isolate anything that could be a field. Eg. Account.Name 
        return '.%s' % field.api_name
    return field.api_name



def create_field_usage(field, type, name):
    """
    Create the field usage record
    """

    component_type_to_name = {
        'ApexClass': 'Apex Class',
        'ApexComponent': 'VisualForce Component',
        'ApexTrigger': 'Apex Trigger',
        'ApexPage': 'VisualForce Page',
        'EmailTemplate': 'Email Template',
        'Flow': 'Flow',
        'Layout': 'Page Layout',
        'WorkflowRule': 'Workflow',
        'WorkflowFieldUpdate': 'Field Update',
        'WorkflowOutboundMessage': 'Outbound Message'
    }

    field_usage = FieldUsage()
    field_usage.field = field
    field_usage.type = component_type_to_name[type]
    field_usage.name = name
    field_usage.save()


def build_usage_display(all_fields):
    """
    For each field, build the display to save against the field.
    """

    for field in all_fields:

        # Save to the field
        field.field_usage_display = get_usage_display(field)
        field.field_usage_display_text = get_usage_display(field, is_html=False)
        field.save()


def get_usage_display(field, is_html=True):
    """
    Get the HTML content to display
    """
    usage_display = ''
    usage_display = write_usage_to_field(usage_display, field.page_layout_usage(), 'Page Layouts', is_html)
    usage_display = write_usage_to_field(usage_display, field.workflow_usage(), 'Workflows', is_html)
    usage_display = write_usage_to_field(usage_display, field.field_update_usage(), 'Field Updates', is_html)
    usage_display = write_usage_to_field(usage_display, field.outbound_messages_usage(), 'Outbound Messages', is_html)
    usage_display = write_usage_to_field(usage_display, field.flow_usage(), 'Flows', is_html)
    usage_display = write_usage_to_field(usage_display, field.email_template_usage(), 'Email Templates', is_html)
    usage_display = write_usage_to_field(usage_display, field.classes_usage(), 'Apex Classes', is_html)
    usage_display = write_usage_to_field(usage_display, field.triggers_usage(), 'Apex Triggers', is_html)
    usage_display = write_usage_to_field(usage_display, field.components_usage(), 'VisualForce Pages', is_html)
    usage_display = write_usage_to_field(usage_display, field.pages_usage(), 'VisualForce Components', is_html)
    return usage_display




def write_usage_to_cell(usage_list, is_html=False):
    """
    Take a cell and write the usage for that field to it
    """
    usage_cell = ''
    if usage_list:
        if is_html:
            for usage in usage_list:
                usage_cell += '<li>' + usage + '</li>\n'
        else:
            for usage in usage_list:
                usage_cell += '- ' + usage + '\n'
    return usage_cell


def write_usage_to_field(usage_display, usage_list, label, is_html):
    """
    Build the list of usage for the display field
    """

    if usage_list:

        if is_html:
            usage_display += '<strong>%s</strong>\n' % label
            usage_display += '<ul class="usage-list">\n'
            usage_display += write_usage_to_cell(usage_list, is_html=True)
            usage_display += '</ul>'
        else:
            if label != 'Page Layouts':
                usage_display += '\n'
            usage_display += label + '\n'
            usage_display += write_usage_to_cell(usage_list, is_html=False)

    return usage_display

