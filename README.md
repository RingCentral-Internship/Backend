**Sales Summary Battle Cards**

**Description**
API endpoint to make:
- queries to SFDC for lead data
- calls to OpenAI for lead summary generation

**Lead Summary Battle Card**
- sections:
   - lead general info (name, company, email, phone, status, company title)
   - product interest (RC product would show must interest in)
   - where and why (where the lead entered RC system and why they are a lead)
   - historical relationship (relevant engagement/ patterns with RC)
   - sales enablement hook (talking points to sell RC product)
 
**Configuration**
- local build:
   - config.py: Provide OpenAI API key
   - create a virtual environment and install necessary dependencies
   - virtual_env/login.json: Provide SFDC login credentials (username, password, and security token)
- vercel deployment:
   - use os environment variables for API key and SFDC credentials
   - vercel.json-- get all pip dependencies 
