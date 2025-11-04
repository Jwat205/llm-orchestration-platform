"""
Neo4j adapter for graph storage operations.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

try:
    from neo4j import AsyncGraphDatabase, AsyncSession
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    AsyncGraphDatabase = None
    AsyncSession = None

class Neo4jAdapter:
    """Neo4j database adapter for graph operations."""
    
    def __init__(self, uri: str = "bolt://localhost:7687", 
                 username: str = "neo4j", password: str = "password"):
        self.logger = logging.getLogger(__name__)
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        
        if not NEO4J_AVAILABLE:
            self.logger.warning("Neo4j driver not available, adapter will use mock operations")
    
    async def connect(self):
        """Connect to Neo4j database"""
        if not NEO4J_AVAILABLE:
            self.logger.info("Mock Neo4j connection established")
            return
        
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password)
            )
            
            # Test connection
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 as test")
                await result.single()
            
            self.logger.info("Connected to Neo4j database")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Neo4j database"""
        if self.driver:
            await self.driver.close()
            self.logger.info("Disconnected from Neo4j database")
    
    async def create_entity(self, entity: Dict[str, Any]) -> bool:
        """Create entity in Neo4j"""
        if not NEO4J_AVAILABLE or not self.driver:
            self.logger.debug(f"Mock creating entity: {entity['id']}")
            return True
        
        try:
            async with self.driver.session() as session:
                query = """
                CREATE (n:Entity {id: $id, type: $type, properties: $properties, 
                                 created_at: $created_at, updated_at: $updated_at})
                RETURN n
                """
                
                result = await session.run(
                    query,
                    id=entity['id'],
                    type=entity['type'],
                    properties=json.dumps(entity['properties']),
                    created_at=entity['created_at'].isoformat() if isinstance(entity['created_at'], datetime) else entity['created_at'],
                    updated_at=entity['updated_at'].isoformat() if isinstance(entity['updated_at'], datetime) else entity['updated_at']
                )
                
                record = await result.single()
                return record is not None
                
        except Exception as e:
            self.logger.error(f"Error creating entity in Neo4j: {e}")
            return False
    
    async def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity from Neo4j"""
        if not NEO4J_AVAILABLE or not self.driver:
            # Mock entity data
            return {
                "id": entity_id,
                "type": "MockEntity",
                "properties": {"name": f"Mock Entity {entity_id}"},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        
        try:
            async with self.driver.session() as session:
                query = "MATCH (n:Entity {id: $id}) RETURN n"
                result = await session.run(query, id=entity_id)
                
                record = await result.single()
                if record:
                    node = record['n']
                    return {
                        "id": node['id'],
                        "type": node['type'],
                        "properties": json.loads(node['properties']) if node['properties'] else {},
                        "created_at": node['created_at'],
                        "updated_at": node['updated_at']
                    }
                
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting entity from Neo4j: {e}")
            return None
    
    async def update_entity(self, entity_id: str, entity: Dict[str, Any]) -> bool:
        """Update entity in Neo4j"""
        if not NEO4J_AVAILABLE or not self.driver:
            self.logger.debug(f"Mock updating entity: {entity_id}")
            return True
        
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (n:Entity {id: $id})
                SET n.type = $type, n.properties = $properties, n.updated_at = $updated_at
                RETURN n
                """
                
                result = await session.run(
                    query,
                    id=entity_id,
                    type=entity['type'],
                    properties=json.dumps(entity['properties']),
                    updated_at=entity['updated_at']
                )
                
                record = await result.single()
                return record is not None
                
        except Exception as e:
            self.logger.error(f"Error updating entity in Neo4j: {e}")
            return False
    
    async def delete_entity(self, entity_id: str) -> bool:
        """Delete entity from Neo4j"""
        if not NEO4J_AVAILABLE or not self.driver:
            self.logger.debug(f"Mock deleting entity: {entity_id}")
            return True
        
        try:
            async with self.driver.session() as session:
                # Delete entity and all its relationships
                query = """
                MATCH (n:Entity {id: $id})
                OPTIONAL MATCH (n)-[r]-()
                DELETE r, n
                RETURN count(n) as deleted
                """
                
                result = await session.run(query, id=entity_id)
                record = await result.single()
                
                return record and record['deleted'] > 0
                
        except Exception as e:
            self.logger.error(f"Error deleting entity from Neo4j: {e}")
            return False
    
    async def create_relationship(self, relationship: Dict[str, Any]) -> bool:
        """Create relationship in Neo4j"""
        if not NEO4J_AVAILABLE or not self.driver:
            self.logger.debug(f"Mock creating relationship: {relationship['id']}")
            return True
        
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (source:Entity {id: $source_id})
                MATCH (target:Entity {id: $target_id})
                CREATE (source)-[r:RELATIONSHIP {
                    id: $id, type: $type, properties: $properties,
                    strength: $strength, created_at: $created_at, updated_at: $updated_at
                }]->(target)
                RETURN r
                """
                
                result = await session.run(
                    query,
                    source_id=relationship['source_id'],
                    target_id=relationship['target_id'],
                    id=relationship['id'],
                    type=relationship['type'],
                    properties=json.dumps(relationship['properties']),
                    strength=relationship['strength'],
                    created_at=relationship['created_at'].isoformat() if isinstance(relationship['created_at'], datetime) else relationship['created_at'],
                    updated_at=relationship['updated_at'].isoformat() if isinstance(relationship['updated_at'], datetime) else relationship['updated_at']
                )
                
                record = await result.single()
                return record is not None
                
        except Exception as e:
            self.logger.error(f"Error creating relationship in Neo4j: {e}")
            return False
    
    async def get_relationship(self, relationship_id: str) -> Optional[Dict[str, Any]]:
        """Get relationship from Neo4j"""
        if not NEO4J_AVAILABLE or not self.driver:
            # Mock relationship data
            return {
                "id": relationship_id,
                "source_id": "mock_source",
                "target_id": "mock_target",
                "type": "MOCK_RELATIONSHIP",
                "properties": {},
                "strength": 1.0,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (source)-[r:RELATIONSHIP {id: $id}]->(target)
                RETURN r, source.id as source_id, target.id as target_id
                """
                
                result = await session.run(query, id=relationship_id)
                record = await result.single()
                
                if record:
                    rel = record['r']
                    return {
                        "id": rel['id'],
                        "source_id": record['source_id'],
                        "target_id": record['target_id'],
                        "type": rel['type'],
                        "properties": json.loads(rel['properties']) if rel['properties'] else {},
                        "strength": rel['strength'],
                        "created_at": rel['created_at'],
                        "updated_at": rel['updated_at']
                    }
                
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting relationship from Neo4j: {e}")
            return None
    
    async def search_entities(self, query: str, entity_types: Optional[List[str]] = None, 
                            limit: int = 100) -> List[Dict[str, Any]]:
        """Search entities in Neo4j"""
        if not NEO4J_AVAILABLE or not self.driver:
            # Mock search results
            return [{
                "id": f"mock_entity_{i}",
                "type": "MockEntity",
                "properties": {"name": f"Mock Entity {i}"},
                "relevance": 0.8
            } for i in range(min(3, limit))]
        
        try:
            async with self.driver.session() as session:
                type_filter = ""
                if entity_types:
                    type_filter = f"AND n.type IN {entity_types}"
                
                cypher_query = f"""
                MATCH (n:Entity)
                WHERE n.properties CONTAINS $query {type_filter}
                RETURN n
                LIMIT $limit
                """
                
                result = await session.run(cypher_query, query=query, limit=limit)
                
                entities = []
                async for record in result:
                    node = record['n']
                    entities.append({
                        "id": node['id'],
                        "type": node['type'],
                        "properties": json.loads(node['properties']) if node['properties'] else {},
                        "created_at": node['created_at'],
                        "updated_at": node['updated_at']
                    })
                
                return entities
                
        except Exception as e:
            self.logger.error(f"Error searching entities in Neo4j: {e}")
            return []
    
    async def get_entity_relationships(self, entity_id: str, 
                                     relationship_types: Optional[List[str]] = None,
                                     direction: str = "both") -> List[Dict[str, Any]]:
        """Get relationships for an entity"""
        if not NEO4J_AVAILABLE or not self.driver:
            # Mock relationships
            return [{
                "id": f"mock_rel_{i}",
                "source_id": entity_id if i % 2 == 0 else f"other_{i}",
                "target_id": f"other_{i}" if i % 2 == 0 else entity_id,
                "type": "MOCK_RELATIONSHIP",
                "properties": {},
                "strength": 0.8
            } for i in range(3)]
        
        try:
            async with self.driver.session() as session:
                if direction == "outgoing":
                    pattern = f"(n:Entity {{id: $entity_id}})-[r:RELATIONSHIP]->(target)"
                elif direction == "incoming":
                    pattern = f"(source)-[r:RELATIONSHIP]->(n:Entity {{id: $entity_id}})"
                else:  # both
                    pattern = f"(n:Entity {{id: $entity_id}})-[r:RELATIONSHIP]-(other)"
                
                type_filter = ""
                if relationship_types:
                    type_filter = f"AND r.type IN {relationship_types}"
                
                query = f"""
                MATCH {pattern}
                WHERE true {type_filter}
                RETURN r, startNode(r).id as source_id, endNode(r).id as target_id
                """
                
                result = await session.run(query, entity_id=entity_id)
                
                relationships = []
                async for record in result:
                    rel = record['r']
                    relationships.append({
                        "id": rel['id'],
                        "source_id": record['source_id'],
                        "target_id": record['target_id'],
                        "type": rel['type'],
                        "properties": json.loads(rel['properties']) if rel['properties'] else {},
                        "strength": rel['strength'],
                        "created_at": rel['created_at'],
                        "updated_at": rel['updated_at']
                    })
                
                return relationships
                
        except Exception as e:
            self.logger.error(f"Error getting entity relationships from Neo4j: {e}")
            return []
    
    async def get_subgraph(self, entity_ids: List[str], max_hops: int = 2) -> Dict[str, Any]:
        """Extract subgraph around given entities"""
        if not NEO4J_AVAILABLE or not self.driver:
            # Mock subgraph
            return {
                "entities": [{"id": eid, "type": "MockEntity", "properties": {}} for eid in entity_ids],
                "relationships": []
            }
        
        try:
            async with self.driver.session() as session:
                query = f"""
                MATCH (start:Entity)
                WHERE start.id IN $entity_ids
                CALL apoc.path.subgraphNodes(start, {{
                    maxLevel: $max_hops,
                    relationshipFilter: "RELATIONSHIP"
                }}) YIELD node
                WITH collect(DISTINCT node) as nodes
                MATCH (source)-[r:RELATIONSHIP]->(target)
                WHERE source IN nodes AND target IN nodes
                RETURN nodes, collect(r) as relationships
                """
                
                result = await session.run(query, entity_ids=entity_ids, max_hops=max_hops)
                record = await result.single()
                
                if record:
                    entities = []
                    for node in record['nodes']:
                        entities.append({
                            "id": node['id'],
                            "type": node['type'],
                            "properties": json.loads(node['properties']) if node['properties'] else {}
                        })
                    
                    relationships = []
                    for rel in record['relationships']:
                        relationships.append({
                            "id": rel['id'],
                            "type": rel['type'],
                            "properties": json.loads(rel['properties']) if rel['properties'] else {},
                            "strength": rel['strength']
                        })
                    
                    return {
                        "entities": entities,
                        "relationships": relationships
                    }
                
                return {"entities": [], "relationships": []}
                
        except Exception as e:
            self.logger.error(f"Error getting subgraph from Neo4j: {e}")
            return {"entities": [], "relationships": []}
    
    async def execute_cypher(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute raw Cypher query"""
        if not NEO4J_AVAILABLE or not self.driver:
            self.logger.debug(f"Mock executing Cypher query: {query}")
            return [{"result": "mock_result"}]
        
        try:
            async with self.driver.session() as session:
                result = await session.run(query, parameters or {})
                
                records = []
                async for record in result:
                    records.append(dict(record))
                
                return records
                
        except Exception as e:
            self.logger.error(f"Error executing Cypher query: {e}")
            raise
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        if not NEO4J_AVAILABLE or not self.driver:
            return {
                "entities": 100,
                "relationships": 250,
                "entity_types": {"MockEntity": 100},
                "relationship_types": {"MOCK_RELATIONSHIP": 250}
            }
        
        try:
            async with self.driver.session() as session:
                # Get entity count
                entity_result = await session.run("MATCH (n:Entity) RETURN count(n) as count")
                entity_count = (await entity_result.single())['count']
                
                # Get relationship count  
                rel_result = await session.run("MATCH ()-[r:RELATIONSHIP]->() RETURN count(r) as count")
                rel_count = (await rel_result.single())['count']
                
                return {
                    "entities": entity_count,
                    "relationships": rel_count
                }
                
        except Exception as e:
            self.logger.error(f"Error getting statistics from Neo4j: {e}")
            return {"entities": 0, "relationships": 0}
    
    async def update_statistics(self, stats: Dict[str, Any]):
        """Update stored statistics (Neo4j doesn't need this)"""
        pass
    
    async def health_check(self):
        """Perform health check"""
        if not NEO4J_AVAILABLE or not self.driver:
            return True
        
        try:
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 as health")
                await result.single()
            return True
        except Exception as e:
            self.logger.error(f"Neo4j health check failed: {e}")
            raise