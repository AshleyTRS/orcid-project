from flask import Flask, abort, jsonify, render_template, request
from flask_cors import CORS
from src.analytics.aggregations import (
    all_authors_details_paginated,
    all_works_details_paginated,
    publications_per_year,
    top_keywords,
    value_counts
)
from src.analytics.author_profile import (
    get_author_facets, get_author_profile, get_author_works, is_affiliated_author, is_valid_orcid
)
from src.coauthorship.coauthorship_aggregator import CoauthorshipAggregator
from src.coauthorship.constellation import get_constellation
from src.coauthorship.models import NetworkData, Node, Edge
from src.db.MongoConnection import MongoConnection
import os
from dotenv import load_dotenv

load_dotenv()

mongo_uri = os.getenv("MONGO_CONN")
db_name = os.getenv("DB_NAME")
mongo = MongoConnection(mongo_uri, db_name)

app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), '..', '..', 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), '..', '..', 'static'))
CORS(app)  # Enable CORS for API requests

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/network')
def network_view():
    """Co-authorship network visualization page."""
    return render_template('network.html')

@app.route('/network/collaboration')
def collaboration_view():
    """
    Details of the constellation (connected co-author group) around one researcher,
    opened by clicking a node on the network page. Takes the network's filters plus orcid.
    """
    if not is_valid_orcid(request.args.get('orcid', '')):
        abort(404)
    return render_template('collaboration.html')

@app.route('/json_view')
def json_view():
    """Raw JSON viewer for /api/coauthorship."""
    return render_template('json_results.html')

def _search_params():
    """Read the shared search parameters: q (free text) and repeated institute values."""
    query = request.args.get('q', '').strip()[:200] or None
    institutes = [name for name in request.args.getlist('institute') if name.strip()] or None
    return query, institutes

def _optional_int(name):
    """Read an optional integer query parameter; raises ValueError if it is not an integer."""
    value = request.args.get(name)
    return int(value) if value not in (None, '') else None

@app.route('/author/<orcid_id>')
def author_view(orcid_id):
    """Author profile page; details and works are loaded by the page from the API."""
    if not is_valid_orcid(orcid_id):
        abort(404)
    return render_template('author.html', orcid_id=orcid_id)

@app.route('/author/<orcid_id>/works')
def author_works_view(orcid_id):
    """An author's works filtered by topic, type, year and open access (filters live in the URL)."""
    if not is_valid_orcid(orcid_id):
        abort(404)
    return render_template('author_works.html', orcid_id=orcid_id)

def _author_filters():
    """
    Read the author works filters: repeated topic and type values, year_from,
    year_to and oa=1. Raises ValueError if a year is not an integer.
    """
    clean = lambda name: [v.strip()[:300] for v in request.args.getlist(name) if v.strip()][:50]
    return {
        "topics": clean('topic'),
        "types": clean('type'),
        "oa": request.args.get('oa') == '1',
        "year_from": _optional_int('year_from'),
        "year_to": _optional_int('year_to'),
    }

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"})

@app.route('/api/authors')
def get_authors():
    """
    Get paginated authors list.
    
    Query Parameters:
        page (int): Page number, 1-indexed (default: 1)
        limit (int): Number of results per page, 1-100 (default: 50)
        q (str): Optional search text matched against author names and ORCID iD
        institute (str, repeatable): Optional institute names to filter by
    
    Response:
        {
            "data": [...],
            "page": int,
            "has_next": bool,
            "total": int
        }
    """
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        
        # Validate params
        page = max(1, page)
        limit = max(1, min(limit, 100))
        query, institutes = _search_params()
        
        result = all_authors_details_paginated(
            mongo.db, page=page, limit=limit, query=query, institutes=institutes
        )
        return jsonify(result)
    except ValueError:
        return jsonify({"error": "Invalid page or limit parameter"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/authors/<orcid_id>')
def get_author(orcid_id):
    """
    Get one author's profile and summary statistics.

    Response:
        {
            "orcid_id": str, "name": str, "observed_names": [str], "institutions": [str],
            "orcid_works_count": int,
            "stats": {"works": int, "open_access": int, "coauthors": int,
                      "first_year": int, "last_year": int},
            "per_year": [{"year": int, "count": int}],
            "topics": [{"value": str, "count": int}],
            "types": [{"value": str, "count": int}],
            "topics_total": int, "types_total": int
        }
    """
    if not is_valid_orcid(orcid_id):
        return jsonify({"error": "Invalid ORCID iD"}), 400
    try:
        profile = get_author_profile(mongo.db, orcid_id)
        if profile is None:
            return jsonify({"error": "Author not found"}), 404
        return jsonify(profile)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/authors/<orcid_id>/works')
def get_author_works_list(orcid_id):
    """
    Get one page of an author's unique works.

    Query Parameters:
        page (int): Page number, 1-indexed (default: 1)
        limit (int): Results per page, 1-100 (default: 20)
        sort (str): newest (default), oldest or title
        oa (int): 1 to return only open-access works
        topic (str, repeatable): only works with any of these topics
        type (str, repeatable): only works of any of these types
        year_from, year_to (int): publication year range, inclusive

    Response:
        {
            "data": [{"doi", "title", "publication_year", "type", "journal_title",
                      "contributors": [str], "is_oa": bool, "oa_url": str | null,
                      "oa_is_pdf": bool}],
            "page": int, "has_next": bool, "total": int
        }
    """
    if not is_valid_orcid(orcid_id):
        return jsonify({"error": "Invalid ORCID iD"}), 400
    try:
        if not is_affiliated_author(mongo.db, orcid_id):
            return jsonify({"error": "Author not found"}), 404
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        filters = _author_filters()
        result = get_author_works(
            mongo.db, orcid_id, page=page, limit=limit,
            sort=request.args.get('sort', 'newest'),
            open_access_only=filters["oa"],
            filters=filters
        )
        return jsonify(result)
    except ValueError:
        return jsonify({"error": "Invalid page, limit or year parameter"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/authors/<orcid_id>/facets')
def get_author_facets_list(orcid_id):
    """
    Every topic, type and year of an author's works with counts, for the filter sidebar.

    Query Parameters: topic, type, year_from, year_to, oa (as for /works).
    Each facet is counted with the other filters applied but not its own.

    Response:
        {
            "total": int,
            "topics": [{"value": str, "count": int}],
            "types": [{"value": str, "count": int}],
            "years": [{"year": int, "count": int}],
            "open_access": {"count": int, "total": int}
        }
    """
    if not is_valid_orcid(orcid_id):
        return jsonify({"error": "Invalid ORCID iD"}), 400
    try:
        if not is_affiliated_author(mongo.db, orcid_id):
            return jsonify({"error": "Author not found"}), 404
        return jsonify(get_author_facets(mongo.db, orcid_id, _author_filters()))
    except ValueError:
        return jsonify({"error": "Invalid year parameter"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/publications-per-year')
def get_publications_per_year():
    """
    Get publication counts by year.

    Query Parameters:
        start_year (int): optional start year (default: 1969)
        end_year (int): optional end year (default: current year)

    Returns:
        {
            "data": [
                {"year": 2020, "count": 120},
                {"year": 2021, "count": 150}
            ]
        }
    """
    try:
        # Pass only the bounds that were given, so omitted ones keep the function's
        # defaults (1969 and the current year) instead of becoming null
        bounds = {}
        for name in ('start_year', 'end_year'):
            value = _optional_int(name)
            if value is not None:
                bounds[name] = value

        result = publications_per_year(mongo.db, **bounds)
        return jsonify({"data": result})
    except ValueError:
        return jsonify({"error": "Invalid start_year or end_year parameter"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/works')
def get_works():
    """
    Get paginated works list.
    
    Query Parameters:
        page (int): Page number, 1-indexed (default: 1)
        limit (int): Number of results per page, 1-100 (default: 50)
        q (str): Optional search text matched against title, contributors and DOI
        start_year (int): Optional inclusive start year
        end_year (int): Optional inclusive end year
        keyword (str, repeatable): Optional keywords to filter by
        institute (str, repeatable): Optional institute names to filter by
    
    Response:
        {
            "data": [...],
            "page": int,
            "has_next": bool,
            "total": int
        }
    """
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        start_year = _optional_int('start_year')
        end_year = _optional_int('end_year')
        
        # Validate params
        page = max(1, page)
        limit = max(1, min(limit, 100))
        query, institutes = _search_params()
        keywords = [k for k in request.args.getlist('keyword') if k.strip()] or None
        
        result = all_works_details_paginated(
            mongo.db, page=page, limit=limit, query=query,
            start_year=start_year, end_year=end_year,
            keywords=keywords, institutes=institutes
        )
        return jsonify(result)
    except ValueError:
        return jsonify({"error": "Invalid page, limit or year parameter"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/keywords')
def get_keywords():
    """
    Get the most frequent work keywords.

    Query Parameters:
        limit (int): Number of keywords, 1-500 (default: 100)

    Response:
        { "data": [{ "keyword": "Computer science", "count": 812 }, ...] }
    """
    try:
        limit = max(1, min(int(request.args.get('limit', 100)), 500))
        return jsonify({"data": top_keywords(mongo.db, limit=limit)})
    except ValueError:
        return jsonify({"error": "Invalid limit parameter"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _value_counts_response(field_path, default_limit):
    """Shared handler for the filter-option endpoints below."""
    try:
        limit = max(1, min(int(request.args.get('limit', default_limit)), 500))
        return jsonify({"data": value_counts(mongo.db, field_path, limit=limit)})
    except ValueError:
        return jsonify({"error": "Invalid limit parameter"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/work-types')
def get_work_types():
    """
    Get work types with the number of unique works (by DOI) of each type.

    Response:
        { "data": [{ "value": "journal-article", "count": 9120 }, ...] }
    """
    return _value_counts_response("type", default_limit=100)

@app.route('/api/subjects')
def get_subjects():
    """
    Get subjects (OpenAlex topic fields) with the number of unique works in each.

    Response:
        { "data": [{ "value": "Computer Science", "count": 1820 }, ...] }
    """
    return _value_counts_response("topics.field.display_name", default_limit=100)

def _parse_year_range():
    """
    Read startYear/endYear query parameters (defaults 2020-2026).

    Raises:
        ValueError: If the values are not integers or the range is invalid
    """
    start_year = int(request.args.get('startYear', 2020))
    end_year = int(request.args.get('endYear', 2026))

    if start_year > end_year:
        raise ValueError("startYear must be less than or equal to endYear")
    if start_year < 1900 or end_year > 2100:
        raise ValueError("Years must be between 1900 and 2100")

    return start_year, end_year

def _list_param(name):
    """Read a repeatable query parameter, dropping blank values."""
    return [value for value in request.args.getlist(name) if value.strip()] or None

def _network_filters():
    """Read the optional co-authorship network filters (each repeatable)."""
    return {
        "types": _list_param('type'),
        "subjects": _list_param('subject'),
        "keywords": _list_param('keyword'),
        "institutes": _list_param('institute'),
    }

@app.route('/api/coauthorship')
def get_coauthorship():
    """
    Get co-authorship network data.

    Query Parameters:
        startYear (int): Starting year for filtering publications (default: 2020)
        endYear (int): Ending year for filtering publications (default: 2026)
        type (str, repeatable): Optional work types, e.g. journal-article
        subject (str, repeatable): Optional OpenAlex topic fields, e.g. Computer Science
        keyword (str, repeatable): Optional keywords
        institute (str, repeatable): Optional institute names

    Response:
        {
            "nodes": [{"id": "0000-0001-2345-6789", "publications": 5}, ...],
            "edges": [{"source": "...", "target": "...", "weight": 3}, ...]
        }
    """
    try:
        start_year, end_year = _parse_year_range()
        data = CoauthorshipAggregator(mongo.db).get_network_data(
            start_year, end_year, **_network_filters()
        )
        return jsonify(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/coauthorship/constellation')
def get_coauthorship_constellation():
    """
    Get the constellation around one researcher under the network filters.

    Query Parameters:
        orcid (str): The researcher whose constellation to describe (required)
        startYear, endYear, type, subject, keyword, institute: as for /api/coauthorship

    Response: see src.coauthorship.constellation.get_constellation
    """
    orcid_id = request.args.get('orcid', '')
    if not is_valid_orcid(orcid_id):
        return jsonify({"error": "Invalid ORCID iD"}), 400
    try:
        start_year, end_year = _parse_year_range()
        result = get_constellation(mongo.db, orcid_id, start_year, end_year, **_network_filters())
        if result is None:
            return jsonify({"error": "This researcher has no works matching these filters"}), 404
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def get_network_stats():
    """
    Get co-authorship network statistics.

    Query Parameters:
        startYear (int): Starting year for filtering publications (default: 2020)
        endYear (int): Ending year for filtering publications (default: 2026)
        type, subject, keyword, institute: Same optional filters as /api/coauthorship

    Response:
        {
            "total_nodes": int,
            "total_edges": int,
            "total_collaborations": int,
            "solo_authors": int,
            "start_year": int,
            "end_year": int
        }
    """
    try:
        start_year, end_year = _parse_year_range()
        data = CoauthorshipAggregator(mongo.db).get_network_data(
            start_year, end_year, **_network_filters()
        )

        network = NetworkData(
            nodes=[Node(**n) for n in data['nodes']],
            edges=[Edge(**e) for e in data['edges']]
        )
        stats = network.get_stats()
        stats['start_year'] = start_year
        stats['end_year'] = end_year
        return jsonify(stats)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
