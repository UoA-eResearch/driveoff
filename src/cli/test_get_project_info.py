"""This module contains the GetProjectInfo class."""
import json
from argparse import Namespace, ArgumentParser
from datetime import date, datetime, timedelta
from unittest.mock import patch
import requests

from ceradmin_cli.api_client import eresearch_project
from ceradmin_cli.api_client.eresearch_project import ProjectDBApi
from ceradmin_cli.command.role import ListRoleAssignmentRoCrate
from ceradmin_cli.models.project import Project
from ceradmin_cli.models.project_action import ProjectAction
from ceradmin_cli.models.project_status import ProjectStatus
from ceradmin_cli.utility.utilities import datestring_to_date
from ceradmin_cli.utils import (format_parameters, get_dict_properties,
                                get_dict_properties_rocrate, get_next_code, get_person_id,
                                get_project_id, resource_id_parenthesized)

# Argument parsing for pid and drive_id
parser = ArgumentParser(description="Fetch project info and send data to the API.")
parser.add_argument("pid", type=int, help="The project ID (pid) to fetch.")
args = parser.parse_args()

# Initialize the API client
api_client = ProjectDBApi.from_config(environment='test')

# Inject api_client into eresearch_project dynamically
eresearch_project.api_client = api_client

project: dict = api_client.get_project(pid=args.pid, expand=['codes', 'status', 'services'])

# Display basic info
columns = [
    'id', 'title', 'description', 'division', 'codes', 'status',
    'start_date', 'end_date', 'next_review_date', 'last_modified',
    'requirements', 'services', 'members'
]

# Get the project data and apply formatting for JSON serialization
data = get_dict_properties_rocrate(project, columns, formatters=None)
#print(json.dumps(data, indent=4))

# Prepare ListRoleAssignmentRoCrate with mock parsed_args for listing project members
parsed_args = Namespace(person=None, project=args.pid, closed=False)
lister = ListRoleAssignmentRoCrate(eresearch_project, None)
column_names, persons_data = lister.take_action(parsed_args)
column_names=resource_id_parenthesized('person', column_names)
# Combine keys with person data
combined_persons_data = []
for item in persons_data:
    # Create a dictionary for each data item, pairing each key with its corresponding value
    entry = dict(zip(column_names, item))
    combined_persons_data.append(entry)
        
data['members'] = combined_persons_data
# Transforming the data
# Change codes to retain structure with only necessary details
data['codes'] = [
    {
        "code": code['code'],
        "href": code['href'],
        "id": code['id']
    }
    for code in data['codes']['items']
]
# Transforming the identities
for member in data["members"]:
    member["person.identities"]["items"] = [
        item for item in member["person.identities"]["items"]
        if not item["username"].endswith("@auckland.ac.nz")
    ]
data_json_strings = json.dumps(data, indent=4)
"""
# Mock the requests.post function to simulate a POST request without sending
with patch("requests.post") as mock_post:
    mock_post.return_value.status_code = 200  # Simulate success response
    mock_post.return_value.json.return_value = {"message": "Success"}

    response = requests.post("http://localhost:8000", json=data)
    print(response.json())  # Output: {'message': 'Success'}
"""

# Define the URL
"""
url = "http://localhost:8000"
headers = {'Content-Type': 'application/json',
        'x-api-key': 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'}
params = {"drive_id": data['services']['research_drive']['name']}
# Send the POST request
try:
    response = requests.post(url, json = data, params=params, headers=headers)
    # Check for successful request
    if response.status_code == 200:
        print("Request was successful:", response.json())  # Print JSON response
    else:
        print(f"Request failed with status code {response.status_code}: {response.text}")

except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")
"""
with open(f"project_data_{args.pid}.json", 'w') as json_file:
    json.dump(data, json_file, indent=4)
