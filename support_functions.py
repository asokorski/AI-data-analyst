import yaml
import os

#console colors
jade_color = "\033[92m"
reset_color = "\033[0m"

#paths for profile and table_cards
jade_directory = os.path.dirname(os.path.abspath(__file__))
profile_path = os.path.join(jade_directory, "profile")
table_cards_path = os.path.join(jade_directory, "table_cards")

#loading the yaml with credentials
def load_db_credentials():
    credentials_path = os.path.join(os.path.dirname(__file__), "database_credentials.yaml")
    with open(credentials_path, "r") as file:
        return yaml.safe_load(file) #loads yaml as dictionary
    
db_credentials = load_db_credentials()