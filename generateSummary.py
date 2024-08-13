import json
import openai
import requests
import os
from simple_salesforce import Salesforce, SalesforceLogin
from config import OPENAI_API_KEY


# configure login information: LOCAL
loginInfo = json.load(open('virtual_env/login.json'))
username = loginInfo['username']
password = loginInfo['password']
security_token = loginInfo['security_token']
domain = 'login'

# # configure login information: VERCEL DEPLOYMENT
# username = os.getenv('SFDC_USERNAME')
# password = os.getenv('SFDC_PW')
# security_token = os.getenv('SFDC_SECURITY_TOKEN')
# domain = 'login'
# if not all([username, password, security_token]):
#     raise ValueError("Salesforce credentials are not fully set. Please check environment variables.")

# connect to Salesforce securely (no risk of username, pw, token exposure)
session_id, instance = SalesforceLogin(username=username,
                                       password=password,
                                       security_token=security_token,
                                       domain=domain)
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
# openai.api_key = os.getenv('OPENAI_API_KEY')
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


def query_product_list():
    """queries a list of all the RC products in SFDC"""
    querySOQL = "SELECT Intended_Product__c FROM Campaign GROUP BY Intended_Product__c"
    result = sf.query(querySOQL)  # query products list (will not return repeated product names)
    if result['records']:
        product_list = [record['Intended_Product__c'] for record in result['records']]  # generating list of products
        return ', '.join(product_list)
    else:
        return "no products found"


def query_lead_data(leadID):
    """queries Salesforce lead data"""
    if leadID:  # check if ID has been received
        obj = "Lead"
        condition = f"Id = '{leadID}'"
        querySOQL = f"SELECT {fields} FROM {obj} WHERE {condition}"
        result = sf.query(querySOQL)  # query data
        if result['records']:
            return result['records'][0]  # return lead data
        else:
            return {"error": "no records found"}
    else:
        return {"error": "no records found"}


def summarize_section(section_title, lead_data, products=None):
    """generates an AI driven summary for a given section:
    1. product interest (use AI to infer)
    2. where and why they are a lead (use data)
    3. history of interactions (use data)
    4. sales enablement hook (creatively curated for lead)"""
    # background knowledge/ context for pre-processing
    documentation = (
        "You are an AI assistant that helps sales teams understand and engage with their leads effectively. "
        "Using the provided lead data, you will analyze and generate insights. Use the following documentation and "
        "sales process flows to ensure that your responses are insightful, relevant,and tailored to the sales funnel stages. "
        "1. Lead Flow and Sales Funnel "
        "- lead statuses: "
        "   - X. Suspect: the initial stage where leads are part of the total addressable market. "
        "   - X. Open: Early interest is shown, but the lead has not been qualified. "
        "   - 1. New: Leads are ready for initial sales contact through email or phone. "
    )
    section_prompts = {
        "Product Interest": (
            f"Here is a list of all the products that RingCentral has to offer: {products}. "
            "Do external research on the lead's company background, including recent news, "
            "industry, and business model, and suggest which RingCentral product(s) the lead might "
            "be most interested in. Create a bulleted list of the/ these product(s) with a brief "
            "explanation that connects the company's needs with the features of the suggested product(s). "
            "Use the lead's industry context and past product interest data from similar companies where it "
            "is applicable/ available."
        ),
        "Where and Why": (
            "Assess the lead's journey in the sales funnel. Highlight your findings in a bulleted list, "
            "deep diving into where this lead is in the sales funnel and why they are at this stage. "
            "Reference the appropriate lead statuses (e.g. X. Suspect, 1. New, 2. Contacted) and the influence "
            "of recent campaigns/ interactions. "
        ),
        "Historical Relationship": (
            "Provide a bulleted list of the lead's historical relationship with RingCentral. This "
            "should include changes in lead status, past interactions, and any key activities noted. "
            "Highlight patterns or significant events that have influence the lead's current status. "
        ),
        "Sales Enablement Hook": (
            "Develop a compelling sales enablement hook based on the lead's company profile, recent activities, "
            "and historical interactions with RingCentral. This hook should be creative, leverage recent industry trends "
            "or company news, and directly address potential pain points or needs identified in the lead's history. "
            "Ensure that the hook aligns with the specific sales stage and aims to move the lead further down the funnel. "
        ),
    }

    system_prompt = documentation + section_prompts.get(section_title, "Invalid section title")  # select correct system prompt
    user_prompt = json.dumps(lead_data)  # lead data

    return ask_openai(client, system_prompt, user_prompt)


def query_and_summarize_lead(leadID):
    """completes summary response for lead data"""
    lead_data = query_lead_data(leadID)  # get lead data for user prompt
    if "error" in lead_data:  # query failed
        return lead_data

    products = query_product_list()  # get list of product for product interest section

    # define sections for summary and storage container for AI responses
    sections = ["Product Interest", "Where and Why", "Historical Relationship", "Sales Enablement Hook"]
    summary_dict = {}

    for section in sections:  # traverse each section and create summary for each
        if section == "Product Interest":  # pass in products list
            summary = summarize_section(section, lead_data, products=products)
        else:
            summary = summarize_section(section, lead_data)  # create summary for current section
        summary_dict[section] = summary  # store in summary dictionary

    # include general information about lead
    for field in ["Name", "Company", "Title", "Email", "Phone", "Status"]:
        summary_dict[field] = lead_data.get(field, '')

    return summary_dict
