import json
import pandas as pd  # show data in a dataframe (original form: list)
from simple_salesforce import Salesforce, SalesforceLogin, SFType


# configure login information
loginInfo = json.load(open('login.json'))
username = loginInfo['username']
password = loginInfo['password']
security_token = loginInfo['security_token']
domain = 'login'

# connect to Salesforce securely (no risk of username, pw, token exposure)
session_id, instance = SalesforceLogin(username=username, password=password, security_token=security_token, domain=domain)
sf = Salesforce(instance=instance, session_id=session_id)

# get Salesforce org information (for personal confirmation that we've securely connected)
for element in dir(sf):
    if not element.startswith("_"):
        if isinstance(getattr(sf, element), str):
            print('Property Name: {0} ;Value: {1}'.format(element, getattr(sf, element)))

# get Salesforce metadata (for personal confirmation that we've securely connected)
metadata_org = sf.describe()
print(metadata_org['maxBatchSize'])  # max number of records
df_sobjects = pd.DataFrame(metadata_org['sobjects'])  # create data frame for sobjects
df_sobjects.to_csv('org metadata info.csv', index=False)  # convert to csv file to make viewable

# get fields for a specific object: provide API NAME (goto object manager)
project = SFType('__name__', session_id, instance)  # creating project instance
project_metadata = project.describe()  # accessing data
df_project_metadata = pd.DataFrame(project_metadata.get('fields'))  # getting fields

# query SOQL
# to test query:
# 1. developer console
# 2. query editor, write query and see records
querySOQL = """ADD SOQL query"""
testing = sf.query(querySOQL)
print(testing)  # will print as a dictionary