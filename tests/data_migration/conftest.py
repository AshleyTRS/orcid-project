"""
Pytest configuration and fixtures for data migration tests.

Provides shared fixtures for mocking MongoDB collections with mongomock.
"""
import pytest
from unittest.mock import Mock, MagicMock
from pymongo.errors import DuplicateKeyError


def make_mock_collection():
    """
    Create an in-memory mock of a MongoDB collection.
    
    Returns a MagicMock that simulates basic MongoDB collection operations.
    Each call returns an independent collection.
    """
    collection = MagicMock()
    
    # Store documents in memory
    collection._documents = {}
    collection._next_id = 1
    collection._indexes = {}
    
    def find_side_effect(filter_dict=None, projection=None):
        """Mock find operation."""
        if filter_dict is None:
            filter_dict = {}
        results = []
        for doc_id, doc in collection._documents.items():
            matches = True
            for key, value in filter_dict.items():
                if key not in doc:
                    matches = False
                    break
                if isinstance(value, dict):
                    # Handle match operators like $exists, $ne, etc.
                    if "$exists" in value:
                        if value["$exists"] and key not in doc:
                            matches = False
                        elif not value["$exists"] and key in doc:
                            matches = False
                    elif "$ne" in value:
                        if doc[key] == value["$ne"]:
                            matches = False
                    elif "$type" in value:
                        type_name = value["$type"]
                        if type_name == "array" and not isinstance(doc.get(key), list):
                            matches = False
                else:
                    if doc.get(key) != value:
                        matches = False
            
            if matches:
                if projection:
                    projected_doc = {"_id": doc.get("_id")}
                    for proj_key in projection:
                        if proj_key in doc:
                            projected_doc[proj_key] = doc[proj_key]
                    results.append(projected_doc)
                else:
                    results.append(doc)
        
        return results
    
    def insert_one_side_effect(document):
        """Mock insert_one operation."""
        if "_id" not in document:
            document["_id"] = collection._next_id
            collection._next_id += 1
        
        # Check for duplicate key error on unique indexes
        for index_name, index_spec in collection._indexes.items():
            if index_spec.get("unique"):
                for field in index_spec["fields"]:
                    for existing_doc in collection._documents.values():
                        if (field in document and field in existing_doc and 
                            document[field] == existing_doc[field]):
                            raise DuplicateKeyError("Duplicate key error")
        
        collection._documents[document["_id"]] = document
        result = Mock()
        result.inserted_id = document["_id"]
        return result
    
    def update_one_side_effect(filter_dict, update_dict, upsert=False):
        """Mock update_one operation."""
        docs = find_side_effect(filter_dict)
        
        if docs:
            doc_to_update = collection._documents[docs[0]["_id"]]
            if "$set" in update_dict:
                doc_to_update.update(update_dict["$set"])
            result = Mock()
            result.modified_count = 1
            return result
        elif upsert:
            new_doc = filter_dict.copy()
            if "$set" in update_dict:
                new_doc.update(update_dict["$set"])
            insert_one_side_effect(new_doc)
            result = Mock()
            result.modified_count = 0
            result.upserted_id = new_doc["_id"]
            return result
        else:
            result = Mock()
            result.modified_count = 0
            return result
    
    def count_documents_side_effect(filter_dict):
        """Mock count_documents operation."""
        return len(find_side_effect(filter_dict))
    
    def aggregate_side_effect(pipeline):
        """Mock aggregate operation for basic pipelines."""
        docs = list(collection._documents.values())
        results = []
        
        for stage in pipeline:
            if "$match" in stage:
                docs = [d for d in docs if all(
                    d.get(k) == v for k, v in stage["$match"].items()
                )]
            elif "$unwind" in stage:
                field = stage["$unwind"]
                new_docs = []
                for doc in docs:
                    if field in doc and isinstance(doc[field], list):
                        for item in doc[field]:
                            new_doc = doc.copy()
                            new_doc[field] = item
                            new_docs.append(new_doc)
                docs = new_docs
            elif "$group" in stage:
                # Basic grouping support
                groups = {}
                group_id = stage["$group"]["_id"]
                for doc in docs:
                    key = doc.get(group_id)
                    if key not in groups:
                        groups[key] = {"_id": key}
                    groups[key].update({
                        k: v for k, v in stage["$group"].items() if k != "_id"
                    })
                docs = list(groups.values())
        
        return docs
    
    def create_index_side_effect(index_spec, **kwargs):
        """Mock create_index operation."""
        index_name = kwargs.get("name", str(index_spec))
        collection._indexes[index_name] = {
            "fields": [field[0] for field in index_spec],
            "unique": kwargs.get("unique", False)
        }
        return index_name
    
    def index_information_side_effect():
        """Mock index_information operation."""
        return collection._indexes
    
    def drop_index_side_effect(index_name):
        """Mock drop_index operation."""
        if index_name in collection._indexes:
            del collection._indexes[index_name]

    def set_path(document, path, value):
        """Assign a value at a dotted path such as 'contributors.0.orcid_id'."""
        parts = path.split(".")
        target = document
        for part in parts[:-1]:
            target = target[int(part)] if isinstance(target, list) else target.setdefault(part, {})
        last = parts[-1]
        if isinstance(target, list):
            target[int(last)] = value
        else:
            target[last] = value

    def bulk_write_side_effect(operations, ordered=True):
        """Mock bulk_write for UpdateOne operations with $set (dotted paths supported)."""
        modified = 0
        for operation in operations:
            matches = find_side_effect(operation._filter)
            if not matches:
                continue
            document = collection._documents[matches[0]["_id"]]
            for path, value in operation._doc.get("$set", {}).items():
                set_path(document, path, value)
            modified += 1
        result = Mock()
        result.modified_count = modified
        return result

    # Attach mock implementations
    collection.find.side_effect = find_side_effect
    collection.insert_one.side_effect = insert_one_side_effect
    collection.update_one.side_effect = update_one_side_effect
    collection.count_documents.side_effect = count_documents_side_effect
    collection.aggregate.side_effect = aggregate_side_effect
    collection.create_index.side_effect = create_index_side_effect
    collection.index_information.side_effect = index_information_side_effect
    collection.drop_index.side_effect = drop_index_side_effect
    collection.bulk_write.side_effect = bulk_write_side_effect

    return collection


@pytest.fixture
def mock_collection():
    """An in-memory mock collection (see make_mock_collection)."""
    return make_mock_collection()


@pytest.fixture
def mock_collection_factory():
    """Factory for tests that need several independent mock collections."""
    return make_mock_collection


@pytest.fixture
def sample_orcid_documents():
    """Sample ORCID profile documents for testing."""
    return [
        {
            "_id": 1,
            "orcid_id": "0000-0001-2345-6789",
            "given_names": "John",
            "family_names": "Smith",
            "institution_names": ["University of Technology", "Research Institute"]
        },
        {
            "_id": 2,
            "orcid_id": "0000-0002-3456-7890",
            "given_names": "Jane",
            "family_names": "Doe-Anderson",
            "institution_names": ["State University"]
        },
        {
            "_id": 3,
            "orcid_id": "0000-0003-4567-8901",
            "given_names": "Robert",
            "family_names": "Johnson",
            "institution_names": []
        }
    ]


@pytest.fixture
def sample_works_documents():
    """Sample works documents for testing."""
    return [
        {
            "_id": 1,
            "orcid_id": "0000-0001-2345-6789",
            "put_code": "12345",
            "title": "Study on Machine Learning",
            "journal_title": "AI Journal",
            "publication_year": 2023,
            "type": "journal-article",
            "external_ids": [
                {"type": "doi", "value": "10.1000/xyz123"},
                {"type": "pmid", "value": "12345678"}
            ],
            "contributors": [
                {"normalized_name": "jane doe anderson", "tokens": ["jane", "doe", "anderson"]},
                {"normalized_name": "robert johnson", "tokens": ["robert", "johnson"]}
            ]
        },
        {
            "_id": 2,
            "orcid_id": "0000-0002-3456-7890",
            "put_code": "12346",
            "title": "Novel COVID-19 Treatment",
            "journal_title": "Medical Science",
            "publication_year": 2022,
            "type": "journal-article",
            "external_ids": [
                {"type": "doi", "value": "10.2000/abc456"}
            ],
            "contributors": [
                {"normalized_name": "john smith", "tokens": ["john", "smith"]}
            ]
        },
        {
            "_id": 3,
            "orcid_id": "0000-0003-4567-8901",
            "put_code": "12347",
            "title": "Conference Paper on Data Science",
            "journal_title": None,
            "publication_year": 2024,
            "type": "conference-paper",
            "external_ids": [],
            "contributors": []
        }
    ]


@pytest.fixture
def sample_metadata_documents():
    """Sample works_metadata documents from OpenAlex enrichment."""
    return [
        {
            "_id": 1,
            "doi": "10.1000/xyz123",
            "source": "openalex",
            "concepts": [
                {"display_name": "Machine Learning", "score": 0.95},
                {"display_name": "Artificial Intelligence", "score": 0.87}
            ],
            "keywords": ["machine learning", "neural networks", "AI"],
            "topics": [
                {"display_name": "Deep Learning", "scored": 0.89}
            ]
        },
        {
            "_id": 2,
            "doi": "10.2000/abc456",
            "source": "openalex",
            "concepts": [
                {"display_name": "COVID-19", "score": 0.92},
                {"display_name": "Virology", "score": 0.85},
                {"display_name": "Immunology", "score": 0.78}
            ],
            "keywords": ["pandemic", "virus", "vaccine"],
            "topics": [
                {"display_name": "Infectious Disease", "scored": 0.88}
            ]
        }
    ]


@pytest.fixture
def populate_mock_collection(mock_collection, sample_orcid_documents, 
                             sample_works_documents, sample_metadata_documents):
    """
    Fixture to populate mock collections with sample data.
    
    Returns a dictionary of pre-populated collections.
    """
    def _populate(collection_type):
        """Populate a specific collection type."""
        if collection_type == "orcids":
            for doc in sample_orcid_documents:
                mock_collection.find.side_effect.keywords = {"call_list": []}
                # Directly add to _documents instead
                mock_collection._documents[doc["_id"]] = doc
        elif collection_type == "works":
            for doc in sample_works_documents:
                mock_collection._documents[doc["_id"]] = doc
        elif collection_type == "metadata":
            for doc in sample_metadata_documents:
                mock_collection._documents[doc["_id"]] = doc
        return mock_collection
    
    return _populate
