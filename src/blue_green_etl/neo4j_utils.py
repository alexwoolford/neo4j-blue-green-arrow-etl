"""
Shared utilities for Neo4j operations.
"""
import neo4j


def get_driver(config: dict):
    """
    Create a Neo4j driver from configuration.
    
    Args:
        config: Configuration dictionary with 'neo4j' section containing:
            - host: Neo4j host
            - bolt_port: Bolt port (default 7687)
            - user: Username
            - password: Password
    
    Returns:
        Neo4j driver instance
    """
    neo4j_url = f"bolt://{config['neo4j']['host']}:{config['neo4j']['bolt_port']}"
    return neo4j.GraphDatabase.driver(
        neo4j_url,
        auth=neo4j.basic_auth(config['neo4j']['user'], config['neo4j']['password'])
    )

