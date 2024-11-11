import os
from dotenv import load_dotenv
import json
import requests
from argparse import ArgumentParser, Namespace
from ceradmin_cli.api_client import eresearch_project
from ceradmin_cli.api_client.eresearch_project import ProjectDBApi
from ceradmin_cli.command.role import ListRoleAssignmentRoCrate
from ceradmin_cli.utils import get_dict_properties_rocrate, resource_id_parenthesized

# Load environment variables from .env file
load_dotenv()
API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")

class ProjectInfoHandler:
    """Fetch project information and save it to a JSON file."""
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
            {"code": code['code'], "href": code['href'], "id": code['id']}
            for code in data['codes']['items']
        ]
        for member in data["members"]:
            member["person.identities"]["items"] = [
                item for item in member["person.identities"]["items"]
                if not item["username"].endswith("@auckland.ac.nz")
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
        self.save_data_to_file(transformed_data, args.pid)
        
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

    # Define headers and parameters if POST is needed
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': API_KEY
    }
    params = {"drive_id": data['services']['research_drive']['name']}

    # Optional: Post the data if required
    response = ProjectInfoHandler.post_data(data, API_URL, headers=headers, params=params)
    if response:
        print("API responded with:", response)