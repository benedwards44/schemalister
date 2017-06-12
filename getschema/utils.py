from django.conf import settings

import requests
import json


def get_urls_for_object(schema, object_name):
    """
    For a given object type, get the list of describe URLs
    """

    records = requests.get(
        schema.instance_url + '/services/data/v' + str(settings.SALESFORCE_API_VERSION) + '.0/tooling/query/?q=SELECT+Id+FROM+' + object_name, 
        headers={
            'Authorization': 'Bearer ' + schema.access_token, 
            'content-type': 'application/json'
        }
    )

    record_urls = []

    if 'records' in records.json():
        # Iterate over the list of objects
        for record in records.json()['records']:
            record_url = schema.instance_url + record['attributes']['url']
            record_urls.append(record_url)

    return record_urls


