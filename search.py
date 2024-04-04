from elasticsearch import Elasticsearch

# Assuming Elasticsearch is running on 'localhost' and default port '9200'
es = Elasticsearch("http://localhost:9200")

def create_index(index_name):
    # Create an Elasticsearch index if it does not exist
    if not es.indices.exists(index=index_name):
        es.indices.create(index=index_name)

def index_document(index_name, doc_type, document, id=None):
    # Index a document (event) into Elasticsearch
    es.index(index=index_name, doc_type=doc_type, id=id, body=document)

def search_events(query):
    # Search for events that match the query
    body = {
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["tags", "name", "description"]
            }
        },
        "sort": [
            { "rating": "desc" }
        ]
    }
    return es.search(index="events", body=body)