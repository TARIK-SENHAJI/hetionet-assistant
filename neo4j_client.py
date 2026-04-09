from neo4j import GraphDatabase
import config

class Neo4jClient:
    # Client for interacting with Neo4j database

    def __init__(self, uri=None, username=None, password=None):
        # Initialize Neo4j connection with credentials from config or parameters
        self.uri = uri or config.NEO4J_URI
        self.username = username or config.NEO4J_USERNAME
        self.password = password or config.NEO4J_PASSWORD
        self.driver = None

    def connect(self):
        # Establish connection to Neo4j database
        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password)
        )

    def close(self):
        # Close database connection
        if self.driver:
            self.driver.close()

    def execute_query(self, cypher_query):
        # Execute Cypher query and return triplets as list of dicts
        triplets = []

        try:
            with self.driver.session() as session:
                result = session.run(cypher_query)
                records = list(result)

                for record in records:
                    try:
                        if 'n' in record.keys() and 'r' in record.keys() and 'm' in record.keys():
                            n = record['n']
                            m = record['m']
                            r = record['r']

                            s_name = self._extract_name(n)
                            d_name = self._extract_name(m)
                            r_type = self._extract_type(r)

                            if s_name and d_name:
                                triplets.append({
                                    'source': s_name,
                                    'relation': r_type,
                                    'destination': d_name
                                })
                    except Exception:
                        continue

        except Exception as e:
            raise Exception(f"Database error: {str(e)}")

        return triplets

    def _extract_name(self, node):
        # Extract name from node
        if hasattr(node, 'get'):
            return node.get('name', str(node))
        elif 'name' in node:
            return node['name']
        return str(node)

    def _extract_type(self, relationship):
        # Le driver Neo4j utilise l'attribut .type
        if hasattr(relationship, 'type'):
            return relationship.type
            
        # Fallback de sécurité
        if hasattr(relationship, 'get'):
            return relationship.get('type', 'RELATED')
        elif isinstance(relationship, dict) and 'type' in relationship:
            return relationship['type']
            
        return 'RELATED'

    def test_connection(self):
        # True if connection successful, False otherwise

        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                record = result.single()
                return record["test"] == 1
        except Exception:
            return False


# Global client instance
_client_instance = None


def get_neo4j_client():
    # Neo4jClient instance
    global _client_instance
    if _client_instance is None:
        _client_instance = Neo4jClient()
        _client_instance.connect()
    return _client_instance