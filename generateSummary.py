import json
import openai
import requests
from simple_salesforce import Salesforce, SalesforceLogin
from config import OPENAI_API_KEY


# configure login information
loginInfo = json.load(open('virtual_env/login.json'))
username = loginInfo['username']
password = loginInfo['password']
security_token = loginInfo['security_token']
domain = 'login'

# connect to Salesforce securely (no risk of username, pw, token exposure)
session_id, instance = SalesforceLogin(username=username, password=password, security_token=security_token, domain=domain)
sf = Salesforce(instance=instance, session_id=session_id)

# Fields to query
fields_list = [
    'Id', 
    'Name', 
    'Company', 
    'Title', 
    'Email', 
    'Phone', 
    'Status', 
    'LeadSource', 
    'Description', 
    'Lead_Score__c', 
    'Campaign_Member_Target_Segment__c', 
    'Campaign_Member_Type__c', 
    'Campaign_Product__c', 
    'MostRecentCampaign__c', 
    'Most_Recent_Campaign_Associated_Date__c', 
    'Most_Recent_Campaign_Description__c', 
    'Most_Recent_Campaign_Member_Status__c', 
    'Most_Recent_Campaign__c', 
    'Primary_Campaign__c', 
    'Sales_Campaign__c', 
    '(SELECT Field, CreatedDate, NewValue, OldValue FROM Histories)', 
    'Most_Recent_Campaign__r.IsActive', 
    'Most_Recent_Campaign__r.StartDate', 
    'Most_Recent_Campaign__r.Status', 
    'Most_Recent_Campaign__r.EndDate'
]

# Join fields into a single string
fields = ", ".join(fields_list)

# debugging connection errors
print(f"OpenAI library version: {openai.__version__}")
print(f"API Key (first 5 chars): {OPENAI_API_KEY[:5]}...")
try:
    response = requests.get("https://api.openai.com/v1/engines",
                            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"})
    print(f"OpenAI API response status: {response.status_code}")
    print(f"OpenAI API response: {response.text[:100]}...")  # Print first 100 chars
except requests.RequestException as request_error:
    print(f"Error reaching OpenAI API: {request_error}")


# configuring openAI access
openai.api_key = OPENAI_API_KEY
client = openai.OpenAI()  # creating an OpenAI client instance


def ask_openai(openai_client, system_prompt, user_prompt):
    """calls openai"""
    try:
        completion = openai_client.chat.completions.create(
            model="gpt-4",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": f"Here is the SFDC lead data: {user_prompt}"
                }
            ]
        )
        return completion.choices[0].message.content
    # debugging
    except Exception as openai_error:
        return f"Unexpected error: {openai_error}"


def query_and_summarize_lead(leadID):
    """queries Salesforce and creates an AI summary:
    1. product interest (inferred)
    2. where and why they are a lead (using data)
    3. history of interactions (using data)
    4. sales enablement hook (creatively curated for lead according to information)
    """
    if leadID:  # check if ID has been recieved 
        obj = "Lead"
        condition = f"Id = '{leadID}'"
        querySOQL = f"SELECT {fields} FROM {obj} WHERE {condition}"
        result = sf.query(querySOQL)  # query data

        if result['records']:
            lead_data = result['records'][0]  # isolating lead data 
            user_prompt = json.dumps(lead_data)
            system_prompt = (
                "You are an AI assistant that helps sales teams understand their leads. "
                "Using the provided lead data, provide the following information in clearly marked sections:\n"
                "- Product Interest: Write a 1-2 sentences explaining which RingCentral product the lead might be "
                "interested in based on the "
                "provided data and a brief explanation why.\n "
                "- Where and Why: Write 2-3 sentences about where and why the lead is a lead using the fields: "
                "LeadSource, "
                "Description, Lead_Score__c, Campaign_Member_Target_Segment__c, "
                "Campaign_Member_Type__c, Campaign_Product__c, MostRecentCampaign__c, "
                "Most_Recent_Campaign_Associated_Date__c, "
                "Most_Recent_Campaign_Description__c, Most_Recent_Campaign_Member_Status__c, Most_Recent_Campaign__c, "
                "Primary_Campaign__c, Sales_Campaign__c, "
                "Most_Recent_Campaign__r.IsActive, Most_Recent_Campaign__r.StartDate, Most_Recent_Campaign__r.Status, "
                "Most_Recent_Campaign__r.EndDate.\n "
                "- Historical Relationship: Write a 1-2 sentence summary of the historical relationship with the "
                "lead using the fields: Description and (SELECT Field, CreatedDate, NewValue, OldValue FROM "
                "Histories).\n "
                "- Sales Enablement Hook: Create a creative and curated sales enablement hook that a sales rep can "
                "use to convert the lead into a customer. \n"
            )

            # Generate summary using OpenAI
            summary = ask_openai(client, system_prompt, user_prompt)
            print(summary)
            return parse_summary(summary)
        else:
            return {"error": "No records found"}
    else:
        return {"error:" "No records found"}


def parse_summary(summary):
    """Parses the summary text into a dictionary with specific sections"""
    sections = ["Product Interest", "Where and Why", "Historical Relationship", "Sales Enablement Hook"]
    summary_dict = {section: "" for section in sections}
    summary_lines = summary.split("\n")  # split by line

    current_section = None

    for line in summary_lines:
        line = line.strip()
        # Check if the line contains any section header
        if any(section in line for section in sections):
            current_section = next(section for section in sections if section in line)
        elif current_section:
            # Add line to the current section in the dictionary
            if summary_dict[current_section]:
                summary_dict[current_section] += " " + line
            else:
                summary_dict[current_section] = line

    return summary_dict
