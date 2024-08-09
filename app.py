import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import generateSummary
import os

# Configure Flask application
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


# checking that config and login files are present
@app.route('/check_files', methods=['GET'])
def check_files():
    config_present = os.path.exists('config.py')
    login_present = os.path.exists('virtual_env/login.json')
    return jsonify({
        'config_present': config_present,
        'login.json_present': login_present
    })


# Query SOQL and generate AI summary
@app.route('/query_lead', methods=['POST'])
def query_lead():
    """Query lead using lead ID and create AI summary"""
    try:
        leadID = request.json.get('lead_id')  # Lead ID from js message request
        if leadID:  # Lead ID has been received
            summary = generateSummary.query_and_summarize_lead(leadID)
            if summary:  # summary was created successfully
                print(jsonify(summary))
                return jsonify(summary)
            else:  # summary had generation error
                return jsonify({'error': 'Lead ID not provided'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
