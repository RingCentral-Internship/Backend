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


def query_duplicates(leadID, email):
    """queries all duplicate leads"""

    querySOQL = f"SELECT Id FROM LEAD WHERE Email = '{email}' AND Id != '{leadID}'"
    result = sf.query(querySOQL)  # query all duplicate lead ids
    if result['totalSize'] > 0:  # duplicates were found-- add to dictionary
        return [record['Id'] for record in result['records'] if record['Id'].strip() != leadID]
    else:  # no duplicates found
        return "No duplicates found"


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


def summarize_section(section_title, lead_data, products, campaign_history, previous_responses, user_input=None):
    """generates an AI driven summary for a given section:
    1. product interest (use AI to infer)
    2. where and why they are a lead (use data)
    3. history of interactions (use data)
    4. sales enablement hook (creatively curated for lead)"""

    # background knowledge/ context for pre-processing
    documentation = (
        "You are an AI assistant that helps the RingCentral sales reps understand and "
        "engage with their leads effectively. Using the provided lead data, you will analyze and "
        "generate insights. Your goal is to help RingCentral sales reps sell and convert leads into opportunities. "
        "Use the following field value documentation "
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
        "- Campaign History: 5 most recent campaigns along with the products advertised in those campaigns. "
        "- Most_Recent_Campaign_r.Description: full description of most recent campaign. "
        "- Notes__c: additional information on lead. "
        "Generate concise bullet points summarizing key details. "
        "Each point should be one sentence or less, focusing only on essential information for "
        "quick reference by a sales rep. "
        "Make sure that the information is direct/ to the point, and relevant to what a sales rep "
        "may want to know when talking/ engaging with a lead. The information/ insights you provide "
        "should be quick and easy to read (does not need to be full complete sentences-- sales reps"
        "should be able to glance at information and understand what to address with lead immediately). "
        "Sales reps need to be able to look at the generated insights/ inferences "
        "and make quick decisions for how they will engage/ sell the RingCentral business. "
    )

    # define RC products and their plans/ pricing
    RC_products = {
        "Here is a list of all the products offered by RingCentral along with the possible plans "
        "and pricing that comes with each product. For each : "
        "- Phone Systems: "
        "   - Product: RingEX-- includes a core plan, advanced plan (most popular), and ultra plan (best value) "
        "      - features included: "
        "         - business phone system: AI cloud calling (easy to deploy and to use across all devices) "
        "         - personal AI assistant: real time AI note taking during calls "
        "             - personalizes insights"
        "             - crafts messages "
        "         - enhanced business SMS: business texting optimized for deliver-ability "
        "         - messaging: team collaboration, chat, and file sharing "
        "         - video meetings: AI meetings with whiteboard and recording "
        "         - cloud faxing: easy, secure digital faxing from any device "
        "   - RingSense AI for RingEX-- need to join wait-list "
        "- Contact Center: "
        "   - Product: RingCX powered by RingSense AI "
        "      - features included: "
        "         - omnichannel: customer engagement across voice and 20+ digital channel with built in AI "
        "         - workforce engagement management: AI quality/ workforce management, conversation analytics"
        "         - outbound: dynamic outbound contact center with built-in campaign management "
        "   - Product: RingCentral Contact Center Enterprise "
        "- Video: "
        "   - Product: Video Pro "
        "   - Product: Video Pro+ "
        "   - Product: Webinar-- large meeting and webinars made effortless with AI "
        "   - Product: Rooms-- video enabled conference rooms and meeting spaces with one click join "
        "- Events: "
        "   - Product: Events-- all in one, AI powered event management for virtual, hybrid, and in person events  "
        "- Sales Intelligence: "
        "   - RingSense for Sales-- AI sales and conversation intelligence; boosts team collaboration and strategy  "
        "Do research on each RingCentral product and identify their "
        "individual value propositions and functions. Additionally, do research on the different RingCentral "
        "Plans and Pricing offered for these products. "
    }

    # define system prompts based on section for requests
    section_prompts = {
        "Product Interest": (
            f"{RC_products} "
            # f"Here is a list of all the products that RingCentral has to offer: {products}. "
            "Do external research on the lead's company background, including recent news, "
            "industry, and business model, and suggest which RingCentral product(s) the lead might "
            "be most interested in. "
            "Using all the collected information and the lead data-- "
            "leadSource, Lead_Entry_Source, most recent campaign information, and campaign product-- "
            "come up with 1-2 RingCentral products (choose from the ones listed tagged 'Product: <Product name>') "
            "the lead may be interested in. "
            "In bullet points, provide the following information for each RingCentral product: "
            "- **Product**: <Product name> "
            "- **Recommended Pricing Plan**: <ideal pricing plan (only provide this bullet if applicable)> "
            "- **Why**: <one sentence reasoning a sales rep could use to advertise "
            "and cater the product towards  the lead. Make sure to connect the lead company's needs with "
            "the features of the suggested product(s). "
            "Be sure to use the lead's industry context, company size, company location, and "
            "past product interest data from similar companies where it is applicable/ available> "
            "NOTE: Ensure that each bullet is not overwhelmed with information. Remember to get "
            "straight to the point (do not use full sentences, insights provided should just be notes for a sales "
            "rep to use when engaging with the lead). "
            "NOTE: Your response should only include the information about the RingCentral product "
            "the lead may be interested in. Do not provide any additional information in your response. "
        ),
        "Where and Why": (
            "Assess the lead's journey by looking at their Status and most recent campaign information. "
            "Use the Description and Notes__c if relevant. "
            "Summarize the following information about the lead in three bullets: "
            "- **Where**: <where the start of the lead's journey with RingCentral began> "
            "- **Why**: <why the lead entered the RingCentral system>  "
            "- **Current**: <their current relationship with RingCentral>"
        ),
        "Historical Relationship": (
            "Provide a bulleted rundown (no more than 2-4 bullets) of the lead's historical relationship with "
            "RingCentral. Identify a pattern, a consistent interest in a certain part of the RingCentral business/ "
            "product or anything that stands out with the campaign history provided "
            "(use specific campaign names and products). "
            "Provided will be 5 (if applicable) most recent campaigns the lead engaged with. "
        ),
        "Sales Enablement Hook": (
            "Develop a compelling sales enablement hook. This hook should be creative, leverage recent industry "
            "trends or company news, and directly address potential pain points or needs identified by the lead. "
            "The hook should be in the form of a bulleted list (no more than 3 bullets) that highlights "
            "talking points the sales rep could use. Remember to get "
            "straight to the point (do not use full sentences, insights provided should just be notes for a sales "
            "rep to use when engaging with the lead). "
            "Make sure that talking points are applicable to the most recent news on the lead's company "
            "or pain points. Be specific with the recent updates/ pain points about the company and relate them "
            "to how RingCentral can provide a solution for them. "
            "NOTE: your response should only include the sales enablement hook. "
            "Do not provide any additional information. "
        ),
        "Ask more": (
            "Respond to the sales rep's inquiries about the lead. "
            "If questions about the company arise, conduct external research. "
            "For questions regarding specific detail about the lead, rely on the provided lead data "
            "and campaign history to offer insightful responses. However, do not fabricate any information-- "
            "stick strictly to the data you have. It's acceptable to inform the user if you do not have access to "
            "certain requested information. "
            "It's also important to disclose that the information you're working with is limited. "
            "The details you can share with the user include: "
            "lead name, company name, lead's title at the company, contact information, "
            "SDR agents, company size, segment name, lead status, lead source, lead entry source, "
            "information about the most recent campaign the lead engaged with, and the five most recently "
            "attended campaigns. "
            "Any other information is beyond your current knowledge. "
            f"Here is the lead data and campaign history: "
            f"{format_user_prompt(lead_data=lead_data)} {format_user_prompt(campaign_history=campaign_history)}"
        )
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
    elif section_title == "Ask more":
        user_prompt = user_input
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

    # add duplicate lead IDs to response
    summary_dict["Duplicate Leads"] = query_duplicates(leadID, lead_data.get("Email", ""))

    return summary_dict
