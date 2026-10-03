"""
Co-authorship Network API Server

This script provides a Flask-based API server for serving co-authorship network data
and the frontend visualization interface.

API Endpoints:
- GET /api/coauthorship?startYear=<int>&endYear=<int>: Returns co-authorship network data
- GET /api/stats?startYear=<int>&endYear=<int>: Returns network statistics
- GET /: Serves the frontend visualization page
"""

import sys
from pathlib import Path

# Add project root and src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import os
import traceback
import logging

from src.coauthorship.coauthorship_aggregator import CoauthorshipAggregator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__, template_folder='../templates')


class DatabaseConfig:
    """Database configuration manager"""
    
    @staticmethod
    def get_connection():
        """
        Get MongoDB connection from environment variables.
        
        Returns:
            MongoDB database connection
            
        Raises:
            ValueError: If required environment variables are missing
        """
        mongo_uri = os.getenv("MONGO_CONN")
        db_name = os.getenv("DB_NAME")
        
        if not mongo_uri or not db_name:
            raise ValueError("Database configuration missing. "
                           "Please set MONGO_CONN and DB_NAME environment variables.")
        
        # avoid circular dependencies
        try:
            from src.db.MongoConnection import MongoConnection
        except ImportError:
            # Fallback for different project structures
            from pymongo import MongoClient
            client = MongoClient(mongo_uri)
            return client[db_name]
        
        mongo = MongoConnection(mongo_uri, db_name)
        return mongo


@app.route('/api/coauthorship')
def coauthorship_api():
    """
    API endpoint for retrieving co-authorship network data.

    Query Parameters:
        startYear (int): Starting year for filtering publications (default: 2020)
        endYear (int): Ending year for filtering publications (default: 2026)

    Returns:
        JSON response with nodes and edges data
        
    Example response:
        {
            "nodes": [
                {"id": "0000-0001-2345-6789", "publications": 5},
                ...
            ],
            "edges": [
                {"source": "0000-0001-2345-6789", "target": "0000-0002-3456-7890", "weight": 3},
                ...
            ]
        }
    """
    try:
        # Parse and validate parameters
        start_year = int(request.args.get('startYear', 2020))
        end_year = int(request.args.get('endYear', 2026))

        logger.info(f"API called with startYear={start_year}, endYear={end_year}")

        # Validate year range
        if start_year > end_year:
            return jsonify({"error": "startYear must be less than or equal to endYear"}), 400

        if start_year < 1900 or end_year > 2100:
            return jsonify({"error": "Years must be between 1900 and 2100"}), 400

        # Get database connection
        mongo = DatabaseConfig.get_connection()
        
        try:
            # Create aggregator and get data
            aggregator = CoauthorshipAggregator(mongo.db if hasattr(mongo, 'db') else mongo)
            data = aggregator.get_network_data(start_year, end_year)
            
            logger.info(f"Successfully generated network: {len(data['nodes'])} nodes, {len(data['edges'])} edges")
            
            return jsonify(data)
            
        finally:
            # Clean up connection
            if hasattr(mongo, 'close'):
                mongo.close()

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({"error": str(e)}), 400
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/api/stats')
def network_stats_api():
    """
    API endpoint for retrieving network statistics.

    Query Parameters:
        startYear (int): Starting year for filtering publications
        endYear (int): Ending year for filtering publications

    Returns:
        JSON response with network statistics
        
    Example response:
        {
            "total_nodes": 150,
            "total_edges": 320,
            "total_collaborations": 450,
            "solo_authors": 25,
            "start_year": 2020,
            "end_year": 2026
        }
    """
    try:
        start_year = int(request.args.get('startYear', 2020))
        end_year = int(request.args.get('endYear', 2026))

        logger.info(f"Stats API called with startYear={start_year}, endYear={end_year}")

        if start_year > end_year:
            return jsonify({"error": "startYear must be less than or equal to endYear"}), 400
        if start_year < 1900 or end_year > 2100:
            return jsonify({"error": "Years must be between 1900 and 2100"}), 400

        mongo = DatabaseConfig.get_connection()
        
        try:
            aggregator = CoauthorshipAggregator(mongo.db if hasattr(mongo, 'db') else mongo)
            network_data = aggregator.get_network_data(start_year, end_year)
            
            # Calculate statistics
            from src.coauthorship.network_builder import CoauthorshipNetworkBuilder
            from src.coauthorship.models import NetworkData, Node, Edge
            
            nodes = [Node(**n) for n in network_data['nodes']]
            edges = [Edge(**e) for e in network_data['edges']]
            network = NetworkData(nodes=nodes, edges=edges)
            
            stats = network.get_stats()
            stats['start_year'] = start_year
            stats['end_year'] = end_year
            
            return jsonify(stats)
            
        finally:
            if hasattr(mongo, 'close'):
                mongo.close()

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({"error": str(e)}), 400
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/')
def index():
    """
    Serve the frontend visualization page.
    """
    return render_template('index.html')


@app.route('/network')
def network_view():
    """
    Serve the co-authorship network visualization page.
    """
    return render_template('network.html')


@app.route('/json_view')
def json_view():
    """
    Serve a simple page returning raw API JSON from /api/coauthorship.
    """
    return render_template('json_results.html')


@app.route('/health')
def health_check():
    """
    Health check endpoint.
    
    Returns:
        JSON response indicating service health
    """
    return jsonify({
        "status": "healthy",
        "service": "coauthorship-network-api"
    })


if __name__ == '__main__':
    logger.info("Starting Co-authorship Network API Server")
    app.run(debug=True, host='0.0.0.0', port=5000)
