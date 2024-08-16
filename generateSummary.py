import json
import openai
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


# configuring openAI access
openai.api_key = OPENAI_API_KEY
# openai.api_key = os.getenv('OPENAI_API_KEY')
client = openai.OpenAI()  # creating an OpenAI client instance


def ask_openai(openai_client, system_prompt, user_prompt):
    """calls openai"""
    try:
        completion = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
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
        product_list = [record['Intended_Product__c'] for record in result['records'] if record['Intended_Product__c']]
        return ', '.join(product_list) if product_list else "no products found"
    else:
        return "no products found"


def query_campaign_history(leadID):
    """queries the 5 most recent campaigns lead engaged with"""
    if leadID:  # check if ID has been received
        # set up
        fields = "Campaign.Intended_Product__c, Campaign.CreatedDate, Campaign.Name"
        obj = "CampaignMember"
        condition = f"LeadId = '{leadID}'"
        querySOQL = f"SELECT {fields} FROM {obj} WHERE {condition} ORDER BY CreatedDate DESC LIMIT 5"
        result = sf.query(querySOQL)  # query products list (will not return repeated product names)
        if result['records']:
            return result['records']  # return campaign history
        else:
            return {"error": "no campaign history found"}
    else:
        return {"error": "no campaign history found"}


def query_lead_data(leadID):
    """queries Salesforce lead data"""
    if leadID:  # check if ID has been received
        # set up
        fields_list = [
            "Name",
            "Title",
            "Company",
            "Email",
            "Phone",
            "SDR_Agents__c",
            "NumberOfEmployees__c",
            "SegmentName__r.Name",
            "Status",
            "LeadSource",
            "Description",
            "Lead_Entry_Source__c",
            "Most_Recent_Campaign_Associated_Date__c",
            "Most_Recent_Campaign_Description__c",
            "Most_Recent_Campaign__c",
            "Most_Recent_Campaign__r.Name",
            "Most_Recent_Campaign__r.Intended_Product__c",
            "Most_Recent_Campaign__r.Description",
            "Notes__c"
        ]
        # Join fields into a single string
        fields = ", ".join(fields_list)
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


def format_user_prompt(lead_data=None, campaign_history=None):
    """Formats lead data or campaign history into a compact string for the user prompt."""
    if lead_data:  # formatting string for lead_data json
        return (
            f"Title: {lead_data.get('Title', 'N/A')}, "
            f"Company: {lead_data.get('Company', 'N/A')}, "
            f"Number of Employees: {lead_data.get('NumberOfEmployees__c', 'N/A')}, "
            f"Status: {lead_data.get('Status', 'N/A')}, "
            f"Segment: {lead_data.get('Segment_Master_c.Name', 'N/A')}, "
            f"Lead Source: {lead_data.get('LeadSource', 'N/A')}, "
            f"Description: {lead_data.get('Description', 'N/A')}, "
            f"Lead Entry Source: {lead_data.get('Lead_Entry_Source__c', 'N/A')}, "
            f"Recent Campaign Date: {lead_data.get('Most_Recent_Campaign_Associated_Date__c', 'N/A')}, "
            f"Recent Campaign Description: {lead_data.get('Most_Recent_Campaign_Description__c', 'N/A')}, "
            f"Recent Campaign: {lead_data.get('Most_Recent_Campaign__c', 'N/A')}, "
            f"Recent Campaign Name: {lead_data.get('Most_Recent_Campaign__r.Name', 'N/A')}, "
            f"Recent Campaign Product: {lead_data.get('Most_Recent_Campaign__r.Intended_Product__c', 'N/A')}, "
            f"Notes: {lead_data.get('Notes__c', 'N/A')}"
        )
    elif campaign_history:  # formatting string for campaign_history json
        history_entries = []
        for entry in campaign_history:
            campaign = entry.get('Campaign', {})
            history_entries.append(
                f"Campaign Name: {campaign.get('Name', 'N/A')}, "
                f"Product: {campaign.get('Intended_Product__c', 'N/A')}, "
                f"Date: {campaign.get('CreatedDate', 'N/A')}"
            )
        return " | ".join(history_entries)

    return "No data available"


def summarize_section(section_title, lead_data, products, campaign_history, previous_responses):
    """generates an AI driven summary for a given section:
    1. product interest (use AI to infer)
    2. where and why they are a lead (use data)
    3. history of interactions (use data)
    4. sales enablement hook (creatively curated for lead)"""

    # background knowledge/ context for pre-processing
    documentation = (
        "You are an AI assistant that helps the RingCentral sales teams understand and "
        "engage with their leads effectively. Using the provided lead data, you will analyze and "
        "generate insights. Use the following field value documentation "
        "to ensure that your responses are insightful, relevant,and tailored to the sales funnel stages. "
        "- Status: "
        "   - X. Suspect: the initial stage where leads are part of the total addressable market. "
        "   - X. Open: Early interest is shown, but the lead has not been qualified. "
        "   - 1. New: Leads are ready for initial sales contact through email or phone. "
        "   - 1.5. Call out: Leads are actively engaged by the sales team. "
        "   - 2. Contacted: Leads have been contacted and are being nurtured. "
        "   - 0. Downgraded: Leads that are not currently viable but may be revisited. "
        "   - .5. Re-New: Downgraded leads that have been re-engaged. "
        "- leadSource: how a lead enters the RingCentral system."
        "- Description: additional description describing the lead."
        "- Lead_Entry_Source__c: specific source of entry where lead entered the RingCentral system. "
        "- Campaign_Product__c: product being advertised for campaign. "
        "- Most_Recent_Campaign_Associated_Date__c: date lead entered campaign. "
        "- Most_Recent_Campaign_Description__c: brief description of campaign. "
        "- Most_Recent_Campaign_c: campaign last advertised to lead. "
        "- Campaign History: list of the most recent campaigns along with the products advertised in those campaigns. "
        "- Most_Recent_Campaign_r.Description: full description of most recent campaign. "
        "- Notes__c: additional information on lead. "
    )

    # define system prompts based on section for requests
    section_prompts = {
        "Product Interest": (
            f"Here is a list of all the products that RingCentral has to offer: {products}. "
            "1. Do research on each RingCentral product and identify their "
            "individual value propositions and functions. "
            "2. Do external research on the lead's company background, including recent news, "
            "industry, and business model, and suggest which RingCentral product(s) the lead might "
            "be most interested in. "
            "3. Use the leadSource, Lead_Entry_Source, most recent campaign information, and campaign product to "
            "create a bulleted list of 1-2 products the lead may be interested in. Provide a brief "
            "explanation that connects the lead company's needs with the features of the suggested product(s). "
            "Additionally use the lead's industry context, company size, company location, and "
            "past product interest data from similar companies where it is applicable/ available."
        ),
        "Where and Why": (
            "Assess the lead's journey by looking at their Status and most recent campaign information. "
            "Deep diving into where this lead came from, "
            "why they entered the RingCentral system, and their current relationship with RingCentral. "
            "Use the Description and Notes__c if relevant. "
            "Summarize these points in three bullets: where, why, and current. "
        ),
        "Historical Relationship": (
            "Provide a bulleted list of the lead's historical relationship with RingCentral. Identify a pattern"
            ", a consistent interest in a certain part of the RingCentral business/ product or "
            "anything that stands out. "
        ),
        "Sales Enablement Hook": (
            "Develop a compelling sales enablement hook. This hook should be creative, leverage recent industry "
            "trends or company news, and directly address potential pain points or needs identified by the lead. "
        ),
    }

    # select system prompt for request
    system_prompt = documentation + section_prompts.get(section_title, "Invalid section title")

    # format data as string for user prompt
    if section_title == "Product Interest" or section_title == "Where and Why":
        user_prompt = format_user_prompt(lead_data=lead_data)
    elif section_title == "Historical Relationship":
        user_prompt = format_user_prompt(campaign_history=campaign_history)
    elif section_title == "Sales Enablement Hook":
        user_prompt = "\n".join(previous_responses.values())
    else:
        user_prompt = "No relevant data available."

    return ask_openai(client, system_prompt, user_prompt)


def query_and_summarize_lead(leadID):
    """completes summary response for lead data"""
    products = query_product_list()  # get list of product for product interest section
    campaign_history = query_campaign_history(leadID)  # get lead campaign history

    if "error" in campaign_history:  # query failed
        return campaign_history

    lead_data = query_lead_data(leadID)  # get lead data for user prompt
    if "error" in lead_data:  # query failed
        return lead_data

    # define sections for summary and storage container for AI responses
    sections = ["Product Interest", "Where and Why", "Historical Relationship", "Sales Enablement Hook"]
    summary_dict = {}
    previous_responses = {"Company": f"{lead_data.get('Company', '')}"}

    for section in sections:  # traverse each section and create summary for each
        summary = summarize_section(section, lead_data, products, campaign_history, previous_responses)
        summary_dict[section] = summary  # store in summary dictionary
        previous_responses[section] = summary  # store previous responses for sales enablement hook

    # include general information about lead
    for field in ["Name", "Company", "Title", "Email", "Phone", "Status"]:
        summary_dict[field] = lead_data.get(field, '')

    return summary_dict
