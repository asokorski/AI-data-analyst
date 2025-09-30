import oracledb as cx_Oracle
import yaml
import os

#customer to be provided as an input
#query to be provided as output from SqlCoder

#loading the yaml with credentials
def load_db_credentials():
    credentials_path = os.path.join(os.path.dirname(__file__), "database_credentials.yaml")
    with open(credentials_path, "r") as file:
        return yaml.safe_load(file) #loads yaml as dictionary

db_credentials = load_db_credentials()

def execute_query(customer, query):
    try:
        credentials = db_credentials.get(customer.lower()) #depending on the customer
        if not credentials:
            return False, f"Unknown customer: {customer}"

        with cx_Oracle.connect(user=credentials["username"], password=credentials["password"], dsn=credentials["dsn"]) as connection:
            cursor = connection.cursor()
            cursor.execute(query)
            result = cursor.fetchall()
        return True, result
    
    except cx_Oracle.DatabaseError as error:
        return False, str(error)