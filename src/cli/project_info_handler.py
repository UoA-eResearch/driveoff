# Fetch project information and post it to an API endpoint.
import json
import requests
from argparse import ArgumentParser, Namespace
from ceradmin_cli.api_client import eresearch_project
from ceradmin_cli.api_client.eresearch_project import ProjectDBApi
from ceradmin_cli.command.role import ListRoleAssignmentRoCrate
from ceradmin_cli.utils import get_dict_properties_rocrate, resource_id_parenthesized

class ProjectInfoHandler:
    """Fetch project information from project database and save it to a JSON file."""
    def __init__(self, environment: str='test') -> None:
        # Initialize the API client
        self.api_client = ProjectDBApi.from_config(environment=environment)
        eresearch_project.api_client = self.api_client

    def parse_args(self) -> Namespace:
        """Argument parsing for pid"""
        parser = ArgumentParser(description="Fetch project info.")
        parser.add_argument("pid", type=int, help="The project ID (pid) to fetch.")
        return parser.parse_args()

    def get_project_data(self, pid: int) -> dict:
        """Retrieve project data"""
        project = self.api_client.get_project(pid=pid, expand=['codes', 'status', 'services'])
        columns = [
            'id', 'title', 'description', 'division', 'codes', 'status',
            'start_date', 'end_date', 'next_review_date', 'last_modified',
            'requirements', 'services', 'members'
        ]
        project_data = get_dict_properties_rocrate(project, columns, formatters=None)
        return project_data

    def fetch_member_data(self, pid: int) -> list:
        """Retrieve project member data"""
        parsed_args = Namespace(person=None, project=pid, closed=False)
        lister = ListRoleAssignmentRoCrate(eresearch_project, None)
        column_names, persons_data = lister.take_action(parsed_args)
        column_names = resource_id_parenthesized('person', column_names)
        
        # Combine keys with person data
        combined_persons_data = [
            dict(zip(column_names, item)) for item in persons_data
        ]
        return combined_persons_data

    def transform_data(self, data: dict) -> dict:
        """Transform and filter data as needed"""
        data['codes'] = [
            {"code": code.get('code'), "href": code.get('href'), "id": code.get('id')}
            for code in data.get('codes', {}).get('items', [])
        ]
        for member in data.get("members", []):
            member.get("person.identities", {})["items"] = [
                item for item in member.get("person.identities", {}).get("items", [])
                if not item.get("username", "").endswith("@auckland.ac.nz")
            ]
        return data

    def save_data_to_file(self, data: dict, pid: int) -> None:
        """Save data to a JSON file"""
        with open(f"project_data_{pid}.json", 'w') as json_file:
            json.dump(data, json_file, indent=4)

    def run(self) -> dict:
        """Run the main functionality"""
        args = self.parse_args()
        data = self.get_project_data(args.pid)
        data['members'] = self.fetch_member_data(args.pid)
        transformed_data = self.transform_data(data)
        # Save the transformed data to a file
        #self.save_data_to_file(transformed_data, args.pid)
        return transformed_data

    @staticmethod
    def post_data(data: dict, url: str, headers=None, params=None) -> dict:
        """Posts JSON data to the specified API endpoint."""
        try:
            post_response = requests.post(url, json=data, headers=headers, params=params)
            post_response.raise_for_status()  # Raises an error for bad responses
            print("POST request succeeded:", post_response.json())
            return post_response.json()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred during the POST request: {e}")
            return None
    
# Run the main functionality if executed directly
if __name__ == "__main__":
    handler = ProjectInfoHandler()
    data = handler.run()  # Run and get transformed data
    print(data)
    
    # Define headers and parameters if POST is needed
    # api_url = "http://localhost:8000"
    # headers = {'Content-Type': 'application/json',
    #         'x-api-key': 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'}

    # # Check if 'services' key exists in the data
    # if isinstance(data['services']['research_drive'], list) and len(data['services']['research_drive']) > 0:
    #     # Loop through each dictionary in the 'research_drive' list
    #     for drive in data['services']['research_drive']:
    #         # Check if 'name' key exists in each dictionary
    #         if 'name' in drive:
    #             # Process each drive as needed, for example, by setting up params
    #             params = {"drive_id": drive['name']}
    #             print(f"Processing drive with ID: {params['drive_id']}")
    #             response = ProjectInfoHandler.post_data(data, api_url, headers, params=params)
    #             if response:
    #                 print(f"POST succeeded for drive ID {params['drive_id']}:", response)
    #             else:
    #                 print(f"POST failed for drive ID {params['drive_id']}")
