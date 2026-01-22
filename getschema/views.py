from django.shortcuts import render, get_object_or_404
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

from . import utils

from xlsxwriter.workbook import Workbook
from io import BytesIO

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

    return render(request, 'index.html', {'login_form': login_form})

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
            r = requests.get(instance_url + '/services/data/v' + settings.SALESFORCE_API_VERSION + '.0/sobjects/User/' + user_id + '?fields=Username', headers={'Authorization': 'OAuth ' + access_token})
            query_response = json.loads(r.text)
            username = query_response['Username']

            # get the org name of the authenticated user
            r = requests.get(instance_url + '/services/data/v' + settings.SALESFORCE_API_VERSION + '.0/sobjects/Organization/' + org_id + '?fields=Name', headers={'Authorization': 'OAuth ' + access_token})
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
                schema.include_field_usage = login_form.cleaned_data['include_field_usage']
                schema.include_managed_objects = login_form.cleaned_data['include_managed_objects']
                schema.status = 'Running'
                schema.save()

                # Queue job to run async
                try:
                    get_objects_and_fields.delay(schema.id)
                except:
                    # If fail above, wait 5 seconds and try again. Not ideal but should work for now
                    sleep(5)
                    try:
                        get_objects_and_fields.delay(schema.id)
                    except Exception as error:
                        schema.status = 'Error'
                        schema.error = error
                        schema.save()

                return HttpResponseRedirect('/loading/' + str(schema.random_id))

    return render(
        request, 
        'oauth_response.html',
        {
            'error': error_exists, 
            'error_message': error_message, 
            'username': username, 
            'org_name': org_name, 
            'login_form': login_form
        }
    )

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
        if 'noheader' in request.GET:
            if request.GET.noheader == '1':
                return_url += '?noheader=1'

        return HttpResponseRedirect(return_url)
    else:
        return render(
            request, 
            'loading.html',
            {'schema': schema}
        )
          

def view_schema(request, schema_id):

    # Pass the schema to the page but delete it after view - it's not nice to store Orgs data models
    schema = get_object_or_404(Schema, random_id = schema_id)

    return render(
        request, 
        'schema.html',
        {'schema': schema}
    )


def export(request, schema_id):
    """ 
        Generate a XLSX file for download
    """

    # Query for schema
    schema = get_object_or_404(Schema, random_id = schema_id)

    single_tab = request.GET.get('singleTab')

    try:

        # Generate output string
        output = BytesIO()

        # Create workbook
        book = Workbook(output, {'in_memory': True})

        # Set up bold format
        bold = book.add_format({'bold': True})

        # List of unique names, as 31 characters is the limit for an object
        # and the worksheets names must be unique
        unique_names = []
        unique_count = 1

        # This puts the objects on different worksheets
        if not single_tab:

            # create a sheet for each object
            for obj in schema.sorted_objects_api():

                # strip api name
                api_name = obj.api_name[:29]

                # If the name exists 
                if api_name in unique_names:

                    # Add count integer to name
                    api_name_unique = api_name + str(unique_count)

                    unique_count += 1

                else:
                    api_name_unique = api_name

                # add name to list
                unique_names.append(api_name)

                # Create sheet
                sheet = book.add_worksheet(api_name_unique)    

                # Write column headers
                sheet.write(0, 0, 'Field Label', bold)
                sheet.write(0, 1, 'API Name', bold)
                sheet.write(0, 2, 'Type', bold)
                sheet.write(0, 3, 'Help Text', bold)
                sheet.write(0, 4, 'Formula', bold)
                sheet.write(0, 5, 'Attributes', bold)

                # If the usage needs to be included, add the columns
                if schema.include_field_usage:
                    sheet.write(0, 6, 'Field Usage', bold)

                # Iterate over fields in object
                for index, field in enumerate(obj.sorted_fields()):

                    # Set start row
                    row = index + 1

                    # Write fields to row
                    sheet.write(row, 0, field.label)
                    sheet.write(row, 1, field.api_name)
                    sheet.write(row, 2, field.data_type)
                    sheet.write(row, 3, field.help_text)
                    sheet.write(row, 4, field.formula)
                    sheet.write(row, 5, field.attributes)

                    if schema.include_field_usage:
                        sheet.write(row, 6, field.field_usage_display_text)

        # This puts all fields on the one worksheet
        else:

            # Create sheet
            sheet = book.add_worksheet('Schema')   

            # Write column headers
            sheet.write(0, 0, 'Object', bold)
            sheet.write(0, 1, 'Field Label', bold)
            sheet.write(0, 2, 'API Name', bold)
            sheet.write(0, 3, 'Type', bold)
            sheet.write(0, 4, 'Help Text', bold)
            sheet.write(0, 5, 'Formula', bold)
            sheet.write(0, 6, 'Attributes', bold)

            # If the usage needs to be included, add the columns
            if schema.include_field_usage:
                sheet.write(0, 7, 'Field Usage', bold)

            # Set start row
            row = 1

            # create a sheet for each object
            for obj in schema.sorted_objects_api():

                # Iterate over fields in object
                for index, field in enumerate(obj.sorted_fields()):

                    # Write fields to row
                    sheet.write(row, 0, obj.api_name)
                    sheet.write(row, 1, field.label)
                    sheet.write(row, 2, field.api_name)
                    sheet.write(row, 3, field.data_type)
                    sheet.write(row, 4, field.help_text)
                    sheet.write(row, 5, field.formula)
                    sheet.write(row, 6, field.attributes)

                    if schema.include_field_usage:
                        sheet.write(row, 7, field.field_usage_display_text)

                    row += 1

        # Close the book
        book.close()

        # construct response
        output.seek(0)
        response = HttpResponse(output.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response['Content-Disposition'] = "attachment; filename=schema_%s.xlsx" % schema.org_id

        return response

    except Exception as ex:

        return HttpResponse(ex)

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
        
    return render(
        request, 
        'logout.html',
        {'instance_prefix': instance_prefix}
    )


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
            r = requests.get(schema.instance_url + '/services/data/v' + settings.SALESFORCE_API_VERSION + '.0/sobjects/Organization/' + schema.org_id + '?fields=Name', headers={'Authorization': 'OAuth ' + schema.access_token})
            schema.org_name = json.loads(r.text)['Name']

            # Save the schema
            schema.save()

            # Run job
            get_objects_and_fields.delay(schema.id)

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
