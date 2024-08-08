import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import generateSummary

# Configure Flask application
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Query SOQL and generate AI summary
@app.route('/query_lead', methods=['POST'])
def query_lead():
    """Query lead using lead ID and create AI summary"""
    leadID = request.json.get('lead_id')  # Lead ID from js message request
    if leadID:  # Lead ID has been received
        summary = generateSummary.query_and_summarize_lead(leadID)
        return jsonify(summary)
    return jsonify({'error': 'Lead ID not provided'}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
