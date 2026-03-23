"""
Co-authorship Network API Server

This script provides a Flask-based API server for serving co-authorship network data
and the frontend visualization interface.

API Endpoints:
- GET /api/coauthorship?startYear=<int>&endYear=<int>: Returns co-authorship network data
- GET /: Serves the frontend visualization page
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import os
import traceback
from src.db.MongoConnection import MongoConnection
from src.coauthorship import get_coauthorship_data

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder='../templates')

@app.route('/api/coauthorship')
def coauthorship_api():
    """
    API endpoint for retrieving co-authorship network data.

    Query Parameters:
        startYear (int): Starting year for filtering publications (default: 2000)
        endYear (int): Ending year for filtering publications (default: 2023)

    Returns:
        JSON response with nodes and edges data
    """
    try:
        start_year = int(request.args.get('startYear', 2020))
        end_year = int(request.args.get('endYear', 2025))

        print(f"API called with startYear={start_year}, endYear={end_year}")

        # Validate year range
        if start_year > end_year:
            return jsonify({"error": "startYear must be less than or equal to endYear"}), 400
        if start_year < 1900 or end_year > 2100:
            return jsonify({"error": "Years must be between 1900 and 2100"}), 400

        # Connect to database
        mongo_uri = os.getenv("MONGO_CONN")
        db_name = os.getenv("DB_NAME")
        if not mongo_uri or not db_name:
            print("ERROR: Database configuration missing")
            return jsonify({"error": "Database configuration missing"}), 500

        print("Connecting to database...")
        mongo = MongoConnection(mongo_uri, db_name)
        try:
            print("Running aggregation...")
            data = get_coauthorship_data(mongo.db, start_year, end_year)
            print(f"Found {len(data['nodes'])} nodes, {len(data['edges'])} edges")
            return jsonify(data)
        except Exception as agg_error:
            print(f"[ERROR] Aggregation failed: {str(agg_error)}")
            traceback.print_exc()
            raise
        finally:
            try:
                mongo.close()
            except:
                pass

    except ValueError as e:
        print(f"[ERROR] ValueError: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": "Invalid year parameters"}), 400
    except Exception as e:
        print(f"[ERROR] Unexpected exception: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/')
def index():
    """
    Serve the frontend visualization page.
    """
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)