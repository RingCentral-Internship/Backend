# Backend


**Purpose**
A Chrome extension designed for RingCentral sales representatives to streamline the process of gathering and learning about Salesforce (SFDC) leads. This extension will help sales reps quickly familiarize themselves with key details about each lead, highlight and suggest talking points for engagement, and simplify the overall sales process, making it more efficient and effective.

**Description**
API endpoint to make:
- queries to SFDC for lead data
- calls to OpenAI for lead summary generation

**Lead Summary Battle Card**
- sections:
   - lead general info (name, company, email, phone, status, company title, segment, SM employees)
   - product interest (RC product would show must interest in)
   - where and why (where the lead entered RC system and why they are a lead)
   - historical relationship (relevant engagement/ patterns with RC and duplicate leads/ opportunities)
   - sales enablement hook (talking points to sell RC product)
 
**Configuration/ Run Instructions**
- local build:
   - config.py: Provide OpenAI API key
   - create a virtual environment and install necessary dependencies
   - virtual_env/login.json: Provide SFDC login credentials (username, password, and security token)
- vercel deployment (not yet deployed):
   - use os environment variables for API key and SFDC credentials
   - vercel.json-- get all pip dependencies
- to run:
  - activate virtual environment
  - export OpenAI API key
  - run python3 app.py (will run on local 5000 server)
- testing without frontend:
  - can run testing.py by replacing JSON POST request info (endpoint must be running locally)
  - can run on postman (JSON POST request structure is provided in testing.py) 

**Tech Stack**
- Programming Language: Python
- Web Framework: Flask (what allows program to be an API endpoint)
   - handles communication between frontend and backend (request handling and response sending)
- Libraries: 
   - Integration: SFDC (simple-salesforce library)
      - query lead data from SFDC
   - AI driven lead summaries: OpenAI API (model: GPT-3.5-turbo)
- Data Handling: JSON (responses and SFDC queries are returned in a JSON structured format)

**File Description**
- app.py: API endpoint configuration and routing
- config.py: OpenAI API Key setup
- generateSummary.py: SFDC integration configuration, OpenAI API configuration, OpenAI request functions, query function (duplicate leads/ opportunities, SFDC RC products, SFDC lead campaign history, SDFDC lead data)
- testing.py: test program locally (replace "lead_id" as needed)
- virtual_env/login.json: SFDC login credentials for local build
