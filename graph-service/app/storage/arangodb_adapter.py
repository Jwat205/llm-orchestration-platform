"""
ArangoDB Adapter for Graph Storage
Provides ArangoDB integration for multi-model graph storage with document and graph capabilities.
"""
import asyncio
from typing import List, Dict, Any, Optional, Union, Set
import logging
from dataclasses import dataclass
from enum import Enum
import json
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None
from urllib.parse import urljoin
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

class CollectionType(Enum):
    DOCUMENT = "document"
    EDGE = "edge"

@dataclass
class ArangoConfig:
    hosts: List[str]
    database: str
    username: str
    password: str
    use_ssl: bool = False
    verify_ssl: bool = True
    connection_timeout: int = 10
    request_timeout: int = 30
    max_connections: int = 100
    retry_attempts: int = 3
    retry_delay: float = 1.0

class ArangoDBAdapter:
    """ArangoDB adapter for multi-model graph storage"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = ArangoConfig(**config) if config else ArangoConfig(
            hosts=["http://localhost:8529"],
            database="graph_db",
            username="root",
            password=""
        )
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = ""
        self.auth_header = ""
        
        # Collection management
        self.collections: Dict[str, CollectionType] = {}
        
        # Connection pooling
        self.connector: Optional[aiohttp.TCPConnector] = None
        
        # Performance metrics
        self.metrics = {
            "requests_sent": 0,
            "requests_failed": 0,
            "total_response_time": 0.0,
            "avg_response_time": 0.0
        }
    
    async def initialize(self):
        """Initialize ArangoDB connection"""
        try:
            if not HAS_AIOHTTP:
                logger.error("aiohttp not available, cannot initialize ArangoDB adapter")
                raise ImportError("aiohttp is required for ArangoDB adapter")
            
            logger.info("Initializing ArangoDB adapter...")
            
            # Setup connection
            await self._setup_connection()
            
            # Test connection
            await self._test_connection()
            
            # Setup database and collections
            await self._setup_database()
            await self._setup_collections()
            
            logger.info("ArangoDB adapter initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing ArangoDB adapter: {e}")
            raise
    
    async def _setup_connection(self):
        """Setup HTTP connection to ArangoDB"""
        try:
            # Create connector with connection pooling
            self.connector = aiohttp.TCPConnector(
                limit=self.config.max_connections,
                limit_per_host=self.config.max_connections // len(self.config.hosts),
                ttl_dns_cache=300,
                use_dns_cache=True,
                ssl=self.config.verify_ssl if self.config.use_ssl else False
            )
            
            # Create session
            timeout = aiohttp.ClientTimeout(
                total=self.config.request_timeout,
                connect=self.config.connection_timeout
            )
            
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )
            
            # Setup authentication
            import base64
            credentials = f"{self.config.username}:{self.config.password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            self.auth_header = f"Basic {encoded_credentials}"
            
            # Use first host as primary
            self.base_url = self.config.hosts[0]
            
        except Exception as e:
            logger.error(f"Error setting up connection: {e}")
            raise
    
    async def _test_connection(self):
        """Test connection to ArangoDB"""
        try:
            url = urljoin(self.base_url, "/_api/version")
            
            async with self.session.get(url, headers={"Authorization": self.auth_header}) as response:
                if response.status == 200:
                    version_info = await response.json()
                    logger.info(f"Connected to ArangoDB version {version_info.get('version', 'unknown')}")
                else:
                    raise ConnectionError(f"Failed to connect to ArangoDB: {response.status}")
                    
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            raise
    
    async def _setup_database(self):
        """Setup database"""
        try:
            # Check if database exists
            url = urljoin(self.base_url, f"/_api/database/{self.config.database}")
            
            async with self.session.get(url, headers={"Authorization": self.auth_header}) as response:
                if response.status == 404:
                    # Create database
                    create_url = urljoin(self.base_url, "/_api/database")
                    data = {"name": self.config.database}
                    
                    async with self.session.post(
                        create_url,
                        headers={"Authorization": self.auth_header},
                        json=data
                    ) as create_response:
                        if create_response.status not in [200, 201]:
                            raise RuntimeError(f"Failed to create database: {create_response.status}")
                        
                        logger.info(f"Created database: {self.config.database}")
                elif response.status != 200:
                    raise RuntimeError(f"Database check failed: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error setting up database: {e}")
            raise
    
    async def _setup_collections(self):
        """Setup required collections"""
        try:
            # Define standard collections
            collections_to_create = {
                "entities": CollectionType.DOCUMENT,
                "relationships": CollectionType.EDGE,
                "concepts": CollectionType.DOCUMENT,
                "documents": CollectionType.DOCUMENT,
                "events": CollectionType.DOCUMENT
            }
            
            for collection_name, collection_type in collections_to_create.items():
                await self.create_collection(collection_name, collection_type)
                
        except Exception as e:
            logger.error(f"Error setting up collections: {e}")
            raise
    
    async def create_collection(self, name: str, collection_type: CollectionType) -> bool:
        """Create a collection"""
        try:
            # Check if collection exists
            url = urljoin(self.base_url, f"/_db/{self.config.database}/_api/collection/{name}")
            
            async with self.session.get(url, headers={"Authorization": self.auth_header}) as response:
                if response.status == 200:
                    # Collection exists
                    self.collections[name] = collection_type
                    return True
                elif response.status == 404:
                    # Create collection
                    create_url = urljoin(self.base_url, f"/_db/{self.config.database}/_api/collection")
                    
                    collection_data = {
                        "name": name,
                        "type": 3 if collection_type == CollectionType.EDGE else 2  # 3=edge, 2=document
                    }
                    
                    async with self.session.post(
                        create_url,
                        headers={"Authorization": self.auth_header},
                        json=collection_data
                    ) as create_response:
                        if create_response.status in [200, 201]:
                            self.collections[name] = collection_type
                            logger.info(f"Created collection: {name} ({collection_type.value})")
                            return True
                        else:
                            error_text = await create_response.text()
                            logger.error(f"Failed to create collection {name}: {error_text}")
                            return False
                else:
                    logger.error(f"Collection check failed for {name}: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error creating collection {name}: {e}")
            return False
    
    async def create_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Create entities in the graph"""
        if not entities:
            return []
        
        try:
            # Prepare documents for insertion
            documents = []
            for entity in entities:
                doc = entity.copy()
                
                # Ensure _key is set (ArangoDB document key)
                if "_key" not in doc and "id" in doc:
                    doc["_key"] = str(doc["id"]).replace("/", "_").replace(" ", "_")
                
                documents.append(doc)
            
            # Insert documents
            url = urljoin(self.base_url, f"/_db/{self.config.database}/_api/document/entities")
            
            created_ids = []
            
            # Process in batches to avoid request size limits
            batch_size = 1000
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                
                async with self.session.post(
                    url,
                    headers={"Authorization": self.auth_header},
                    json=batch
                ) as response:
                    
                    if response.status in [200, 201, 202]:
                        result = await response.json()
                        
                        if isinstance(result, list):
                            for item in result:
                                if not item.get("error"):
                                    created_ids.append(item.get("_id", item.get("_key")))
                        else:
                            if not result.get("error"):
                                created_ids.append(result.get("_id", result.get("_key")))
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to create entities batch: {error_text}")
            
            logger.info(f"Created {len(created_ids)} entities")
            return created_ids
            
        except Exception as e:
            logger.error(f"Error creating entities: {e}")
            return []
    
    async def create_relationships(self, relationships: List[Dict[str, Any]]) -> List[str]:
        """Create relationships in the graph"""
        if not relationships:
            return []
        
        try:
            # Prepare edge documents
            edges = []
            for rel in relationships:
                edge = rel.copy()
                
                # Ensure _from and _to are set with collection prefix
                if "_from" not in edge and "source_id" in edge:
                    edge["_from"] = f"entities/{edge['source_id']}"
                
                if "_to" not in edge and "target_id" in edge:
                    edge["_to"] = f"entities/{edge['target_id']}"
                
                # Set _key if not present
                if "_key" not in edge and "id" in edge:
                    edge["_key"] = str(edge["id"]).replace("/", "_").replace(" ", "_")
                
                edges.append(edge)
            
            # Insert edges
            url = urljoin(self.base_url, f"/_db/{self.config.database}/_api/document/relationships")
            
            created_ids = []
            
            # Process in batches
            batch_size = 1000
            for i in range(0, len(edges), batch_size):
                batch = edges[i:i + batch_size]
                
                async with self.session.post(
                    url,
                    headers={"Authorization": self.auth_header},
                    json=batch
                ) as response:
                    
                    if response.status in [200, 201, 202]:
                        result = await response.json()
                        
                        if isinstance(result, list):
                            for item in result:
                                if not item.get("error"):
                                    created_ids.append(item.get("_id", item.get("_key")))
                        else:
                            if not result.get("error"):
                                created_ids.append(result.get("_id", result.get("_key")))
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to create relationships batch: {error_text}")
            
            logger.info(f"Created {len(created_ids)} relationships")
            return created_ids
            
        except Exception as e:
            logger.error(f"Error creating relationships: {e}")
            return []
    
    async def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by ID"""
        try:
            # Try with collection prefix first
            if "/" not in entity_id:
                entity_id = f"entities/{entity_id}"
            
            url = urljoin(self.base_url, f"/_db/{self.config.database}/_api/document/{entity_id}")
            
            async with self.session.get(url, headers={"Authorization": self.auth_header}) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"Error getting entity {entity_id}: {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting entity {entity_id}: {e}")
            return None
    
    async def get_relationship(self, relationship_id: str) -> Optional[Dict[str, Any]]:
        """Get relationship by ID"""
        try:
            # Try with collection prefix first
            if "/" not in relationship_id:
                relationship_id = f"relationships/{relationship_id}"
            
            url = urljoin(self.base_url, f"/_db/{self.config.database}/_api/document/{relationship_id}")
            
            async with self.session.get(url, headers={"Authorization": self.auth_header}) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"Error getting relationship {relationship_id}: {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting relationship {relationship_id}: {e}")
            return None
    
    async def update_entity(self, entity_id: str, entity_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update entity"""
        try:
            # Try with collection prefix first
            if "/" not in entity_id:
                entity_id = f"entities/{entity_id}"
            
            url = urljoin(self.base_url, f"/_db/{self.config.database}/_api/document/{entity_id}")
            
            async with self.session.patch(
                url,
                headers={"Authorization": self.auth_header},
                json=entity_data
            ) as response:
                if response.status in [200, 201, 202]:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Error updating entity {entity_id}: {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error updating entity {entity_id}: {e}")
            return None
    
    async def delete_entity(self, entity_id: str) -> bool:
        """Delete entity"""
        try:
            # Try with collection prefix first
            if "/" not in entity_id:
                entity_id = f"entities/{entity_id}"
            
            url = urljoin(self.base_url, f"/_db/{self.config.database}/_api/document/{entity_id}")
            
            async with self.session.delete(url, headers={"Authorization": self.auth_header}) as response:
                if response.status in [200, 202]:
                    return True
                elif response.status == 404:
                    logger.warning(f"Entity {entity_id} not found for deletion")
                    return False
                else:
                    error_text = await response.text()
                    logger.error(f"Error deleting entity {entity_id}: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error deleting entity {entity_id}: {e}")
            return False
    
    async def execute_aql_query(self, query: str, bind_vars: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute AQL query"""
        try:
            url = urljoin(self.base_url, f"/_db/{self.config.database}/_api/cursor")
            
            query_data = {
                "query": query,
                "bindVars": bind_vars or {},
                "batchSize": 1000
            }
            
            results = []
            
            async with self.session.post(
                url,
                headers={"Authorization": self.auth_header},
                json=query_data
            ) as response:
                
                if response.status == 201:
                    result = await response.json()
                    results.extend(result.get("result", []))
                    
                    # Handle cursor for large result sets
                    cursor_id = result.get("id")
                    has_more = result.get("hasMore", False)
                    
                    while has_more and cursor_id:
                        cursor_url = urljoin(self.base_url, f"/_db/{self.config.database}/_api/cursor/{cursor_id}")
                        
                        async with self.session.put(
                            cursor_url,
                            headers={"Authorization": self.auth_header}
                        ) as cursor_response:
                            
                            if cursor_response.status == 200:
                                cursor_result = await cursor_response.json()
                                results.extend(cursor_result.get("result", []))
                                has_more = cursor_result.get("hasMore", False)
                            else:
                                break
                    
                    return results
                else:
                    error_text = await response.text()
                    logger.error(f"AQL query failed: {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error executing AQL query: {e}")
            return []
    
    async def find_entities(self, filters: Dict[str, Any], limit: int = 1000) -> List[Dict[str, Any]]:
        """Find entities with filters"""
        try:
            # Build AQL query
            conditions = []
            bind_vars = {}
            
            for key, value in filters.items():
                if isinstance(value, dict):
                    # Handle operators like {"$gt": 10}
                    for op, op_value in value.items():
                        if op == "$gt":
                            conditions.append(f"e.{key} > @{key}_gt")
                            bind_vars[f"{key}_gt"] = op_value
                        elif op == "$lt":
                            conditions.append(f"e.{key} < @{key}_lt")
                            bind_vars[f"{key}_lt"] = op_value
                        elif op == "$in":
                            conditions.append(f"e.{key} IN @{key}_in")
                            bind_vars[f"{key}_in"] = op_value
                else:
                    conditions.append(f"e.{key} == @{key}")
                    bind_vars[key] = value
            
            where_clause = " AND ".join(conditions) if conditions else "true"
            
            query = f"""
            FOR e IN entities
            FILTER {where_clause}
            LIMIT {limit}
            RETURN e
            """
            
            return await self.execute_aql_query(query, bind_vars)
            
        except Exception as e:
            logger.error(f"Error finding entities: {e}")
            return []
    
    async def find_relationships(self, source_id: Optional[str] = None, target_id: Optional[str] = None, 
                               relationship_type: Optional[str] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Find relationships with filters"""
        try:
            conditions = []
            bind_vars = {}
            
            if source_id:
                conditions.append("r._from == @source_id")
                bind_vars["source_id"] = f"entities/{source_id}" if "/" not in source_id else source_id
            
            if target_id:
                conditions.append("r._to == @target_id")
                bind_vars["target_id"] = f"entities/{target_id}" if "/" not in target_id else target_id
            
            if relationship_type:
                conditions.append("r.type == @rel_type")
                bind_vars["rel_type"] = relationship_type
            
            where_clause = " AND ".join(conditions) if conditions else "true"
            
            query = f"""
            FOR r IN relationships
            FILTER {where_clause}
            LIMIT {limit}
            RETURN r
            """
            
            return await self.execute_aql_query(query, bind_vars)
            
        except Exception as e:
            logger.error(f"Error finding relationships: {e}")
            return []
    
    async def get_entity_neighbors(self, entity_id: str, direction: str = "any", 
                                 max_depth: int = 1) -> List[Dict[str, Any]]:
        """Get neighboring entities"""
        try:
            if "/" not in entity_id:
                entity_id = f"entities/{entity_id}"
            
            direction_clause = {
                "outbound": "OUTBOUND",
                "inbound": "INBOUND",
                "any": "ANY"
            }.get(direction, "ANY")
            
            query = f"""
            FOR v, e, p IN 1..{max_depth} {direction_clause} @start_vertex relationships
            RETURN {{
                vertex: v,
                edge: e,
                path: p
            }}
            """
            
            bind_vars = {"start_vertex": entity_id}
            
            return await self.execute_aql_query(query, bind_vars)
            
        except Exception as e:
            logger.error(f"Error getting neighbors for {entity_id}: {e}")
            return []
    
    async def find_shortest_path(self, source_id: str, target_id: str) -> Optional[Dict[str, Any]]:
        """Find shortest path between two entities"""
        try:
            if "/" not in source_id:
                source_id = f"entities/{source_id}"
            if "/" not in target_id:
                target_id = f"entities/{target_id}"
            
            query = """
            FOR v, e IN OUTBOUND SHORTEST_PATH @source TO @target relationships
            RETURN {vertex: v, edge: e}
            """
            
            bind_vars = {
                "source": source_id,
                "target": target_id
            }
            
            results = await self.execute_aql_query(query, bind_vars)
            
            if results:
                return {
                    "path": results,
                    "length": len(results)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding shortest path: {e}")
            return None
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            # Get collection statistics
            stats = {"collections": {}}
            
            for collection_name in self.collections.keys():
                url = urljoin(self.base_url, f"/_db/{self.config.database}/_api/collection/{collection_name}/figures")
                
                async with self.session.get(url, headers={"Authorization": self.auth_header}) as response:
                    if response.status == 200:
                        figures = await response.json()
                        stats["collections"][collection_name] = {
                            "count": figures.get("figures", {}).get("count", 0),
                            "size": figures.get("figures", {}).get("fileSize", 0)
                        }
            
            # Add adapter metrics
            stats["adapter_metrics"] = self.metrics.copy()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    async def create_index(self, collection: str, fields: List[str], index_type: str = "hash") -> bool:
        """Create index on collection"""
        try:
            url = urljoin(self.base_url, f"/_db/{self.config.database}/_api/index")
            
            index_data = {
                "type": index_type,
                "fields": fields,
                "unique": False
            }
            
            # Add collection parameter
            params = {"collection": collection}
            
            async with self.session.post(
                url,
                headers={"Authorization": self.auth_header},
                json=index_data,
                params=params
            ) as response:
                
                if response.status in [200, 201]:
                    logger.info(f"Created {index_type} index on {collection}.{fields}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to create index: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error creating index: {e}")
            return False
    
    async def _update_metrics(self, response_time: float, success: bool):
        """Update performance metrics"""
        self.metrics["requests_sent"] += 1
        
        if not success:
            self.metrics["requests_failed"] += 1
        
        self.metrics["total_response_time"] += response_time
        self.metrics["avg_response_time"] = self.metrics["total_response_time"] / self.metrics["requests_sent"]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check adapter health"""
        try:
            start_time = time.time()
            
            url = urljoin(self.base_url, "/_admin/server/availability")
            
            async with self.session.get(url, headers={"Authorization": self.auth_header}) as response:
                response_time = time.time() - start_time
                success = response.status == 200
                
                await self._update_metrics(response_time, success)
                
                return {
                    "status": "healthy" if success else "unhealthy",
                    "response_time_ms": response_time * 1000,
                    "database": self.config.database,
                    "collections": len(self.collections)
                }
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "database": self.config.database
            }
    
    async def shutdown(self):
        """Shutdown adapter and cleanup resources"""
        try:
            logger.info("Shutting down ArangoDB adapter...")
            
            if self.session:
                await self.session.close()
            
            if self.connector:
                await self.connector.close()
            
            logger.info("ArangoDB adapter shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")