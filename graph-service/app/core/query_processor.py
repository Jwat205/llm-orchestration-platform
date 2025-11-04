"""
Advanced Query Processor for Knowledge Graph operations.
Supports multiple query languages and semantic search.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import json
import re

class QueryProcessor:
    """Advanced query processor with multi-language support."""
    
    def __init__(self, graph_engine):
        self.logger = logging.getLogger(__name__)
        self.graph_engine = graph_engine
        self.query_cache = {}
        self.query_stats = {
            "total_queries": 0,
            "cypher_queries": 0,
            "sparql_queries": 0,
            "natural_language_queries": 0,
            "semantic_searches": 0,
            "average_response_time": 0.0
        }
    
    async def initialize(self):
        """Initialize query processor"""
        self.logger.info("Query processor initialized")
    
    async def shutdown(self):
        """Shutdown query processor"""
        self.logger.info("Query processor shutdown")
    
    async def execute_query(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a query based on its type"""
        start_time = datetime.now()
        
        try:
            query_type = query_data.get('type', 'cypher')
            query = query_data.get('query', '')
            parameters = query_data.get('parameters', {})
            
            result = None
            
            if query_type == 'cypher':
                result = await self.execute_cypher(query, parameters)
            elif query_type == 'sparql':
                result = await self.execute_sparql(query, parameters)
            elif query_type == 'natural_language':
                result = await self.execute_natural_language(query, parameters)
            elif query_type == 'semantic_search':
                result = await self.execute_semantic_search(query, parameters)
            elif query_type == 'graph_pattern':
                result = await self.execute_graph_pattern(query, parameters)
            else:
                raise ValueError(f"Unsupported query type: {query_type}")
            
            # Update statistics
            execution_time = (datetime.now() - start_time).total_seconds()
            await self._update_query_stats(query_type, execution_time)
            
            return {
                "data": result,
                "metadata": {
                    "query_type": query_type,
                    "execution_time": execution_time,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error executing query: {e}")
            raise
    
    async def execute_cypher(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute Cypher query"""
        try:
            # Check cache first
            cache_key = f"cypher:{hash(query + str(parameters or {}))}"
            if cache_key in self.query_cache:
                self.logger.debug("Returning cached Cypher result")
                return self.query_cache[cache_key]
            
            # Execute via primary storage
            if self.graph_engine.primary_storage:
                result = await self.graph_engine.primary_storage.execute_cypher(query, parameters)
                
                # Cache result
                self.query_cache[cache_key] = result
                
                self.query_stats["cypher_queries"] += 1
                return result
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error executing Cypher query: {e}")
            raise
    
    async def execute_sparql(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute SPARQL query"""
        try:
            # Convert SPARQL to Cypher (simplified conversion)
            cypher_query = await self._sparql_to_cypher(query)
            
            # Execute converted query
            result = await self.execute_cypher(cypher_query, parameters)
            
            self.query_stats["sparql_queries"] += 1
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing SPARQL query: {e}")
            raise
    
    async def execute_natural_language(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute natural language query by converting to structured query"""
        try:
            # Parse natural language query
            structured_query = await self._parse_natural_language(query)
            
            # Execute structured query
            result = await self.execute_query(structured_query)
            
            self.query_stats["natural_language_queries"] += 1
            return result["data"]
            
        except Exception as e:
            self.logger.error(f"Error executing natural language query: {e}")
            raise
    
    async def execute_semantic_search(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute semantic search using embeddings"""
        try:
            # Get embedding service
            embedding_service = parameters.get('embedding_service')
            if not embedding_service:
                # Use default semantic search
                return await self._default_semantic_search(query, parameters)
            
            # Get query embedding
            query_embedding = await embedding_service.get_embedding(query)
            
            # Find similar entities using vector similarity
            similar_entities = await self._vector_similarity_search(
                query_embedding, 
                parameters.get('limit', 10),
                parameters.get('threshold', 0.7)
            )
            
            self.query_stats["semantic_searches"] += 1
            return similar_entities
            
        except Exception as e:
            self.logger.error(f"Error executing semantic search: {e}")
            raise
    
    async def execute_graph_pattern(self, pattern: Dict[str, Any], parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute graph pattern matching"""
        try:
            # Convert pattern to Cypher
            cypher_query = await self._pattern_to_cypher(pattern)
            
            # Execute query
            result = await self.execute_cypher(cypher_query, parameters)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing graph pattern: {e}")
            raise
    
    async def _sparql_to_cypher(self, sparql_query: str) -> str:
        """Convert SPARQL query to Cypher (simplified)"""
        # This is a simplified conversion - in practice, you'd use a proper SPARQL parser
        
        # Basic SELECT patterns
        if "SELECT" in sparql_query.upper():
            # Extract variables
            select_match = re.search(r'SELECT\s+(.*?)\s+WHERE', sparql_query, re.IGNORECASE | re.DOTALL)
            if select_match:
                variables = select_match.group(1).strip()
                
                # Extract WHERE clause
                where_match = re.search(r'WHERE\s*\{(.*?)\}', sparql_query, re.IGNORECASE | re.DOTALL)
                if where_match:
                    where_clause = where_match.group(1).strip()
                    
                    # Convert triple patterns to Cypher
                    cypher_patterns = []
                    for line in where_clause.split('.'):
                        line = line.strip()
                        if line:
                            # Simple triple pattern: subject predicate object
                            parts = line.split()
                            if len(parts) >= 3:
                                subject, predicate, obj = parts[0], parts[1], parts[2]
                                cypher_patterns.append(f"({subject})-[:{predicate}]->({obj})")
                    
                    if cypher_patterns:
                        return f"MATCH {', '.join(cypher_patterns)} RETURN {variables}"
        
        # Fallback: return a basic query
        return "MATCH (n) RETURN n LIMIT 10"
    
    async def _parse_natural_language(self, query: str) -> Dict[str, Any]:
        """Parse natural language query into structured format"""
        query_lower = query.lower()
        
        # Simple pattern matching for common queries
        if "find" in query_lower or "search" in query_lower:
            if "similar to" in query_lower:
                # Semantic search
                entity = query_lower.split("similar to")[-1].strip()
                return {
                    "type": "semantic_search",
                    "query": entity,
                    "parameters": {"limit": 10}
                }
            else:
                # Text search
                search_terms = query_lower.replace("find", "").replace("search", "").strip()
                return {
                    "type": "cypher",
                    "query": f"MATCH (n:Entity) WHERE n.properties CONTAINS '{search_terms}' RETURN n LIMIT 10",
                    "parameters": {}
                }
        
        elif "connect" in query_lower or "path" in query_lower:
            # Path finding
            return {
                "type": "cypher",
                "query": "MATCH path = shortestPath((a:Entity)-[*]-(b:Entity)) RETURN path LIMIT 5",
                "parameters": {}
            }
        
        else:
            # Default to entity search
            return {
                "type": "cypher", 
                "query": f"MATCH (n:Entity) WHERE n.properties CONTAINS '{query}' RETURN n LIMIT 10",
                "parameters": {}
            }
    
    async def _default_semantic_search(self, query: str, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Default semantic search without embeddings"""
        # Fallback to text-based search
        entity_types = parameters.get('entity_types')
        limit = parameters.get('limit', 10)
        
        results = await self.graph_engine.search_entities(query, entity_types, limit)
        return results
    
    async def _vector_similarity_search(self, query_embedding: List[float], 
                                      limit: int, threshold: float) -> List[Dict[str, Any]]:
        """Perform vector similarity search"""
        try:
            # This would integrate with a vector database
            # For now, return mock results
            return [
                {
                    "id": f"entity_{i}",
                    "type": "Entity",
                    "properties": {"name": f"Similar Entity {i}"},
                    "similarity_score": 0.9 - (i * 0.1)
                }
                for i in range(min(limit, 5))
            ]
            
        except Exception as e:
            self.logger.error(f"Error in vector similarity search: {e}")
            return []
    
    async def _pattern_to_cypher(self, pattern: Dict[str, Any]) -> str:
        """Convert graph pattern to Cypher query"""
        try:
            nodes = pattern.get('nodes', [])
            edges = pattern.get('edges', [])
            
            # Build node patterns
            node_patterns = []
            for node in nodes:
                node_id = node.get('id', 'n')
                node_type = node.get('type', 'Entity')
                properties = node.get('properties', {})
                
                prop_str = ""
                if properties:
                    prop_list = [f"{k}: '{v}'" for k, v in properties.items()]
                    prop_str = f" {{{', '.join(prop_list)}}}"
                
                node_patterns.append(f"({node_id}:{node_type}{prop_str})")
            
            # Build edge patterns
            edge_patterns = []
            for edge in edges:
                source = edge.get('source', 'n1')
                target = edge.get('target', 'n2')
                edge_type = edge.get('type', 'RELATED')
                
                edge_patterns.append(f"({source})-[:{edge_type}]->({target})")
            
            # Combine patterns
            all_patterns = node_patterns + edge_patterns
            if all_patterns:
                return f"MATCH {', '.join(all_patterns)} RETURN *"
            else:
                return "MATCH (n) RETURN n LIMIT 10"
                
        except Exception as e:
            self.logger.error(f"Error converting pattern to Cypher: {e}")
            return "MATCH (n) RETURN n LIMIT 10"
    
    async def _update_query_stats(self, query_type: str, execution_time: float):
        """Update query statistics"""
        self.query_stats["total_queries"] += 1
        
        # Update average response time
        total_time = (self.query_stats["average_response_time"] * 
                     (self.query_stats["total_queries"] - 1) + execution_time)
        self.query_stats["average_response_time"] = total_time / self.query_stats["total_queries"]
    
    async def get_query_statistics(self) -> Dict[str, Any]:
        """Get query execution statistics"""
        return self.query_stats.copy()
    
    async def clear_cache(self):
        """Clear query cache"""
        self.query_cache.clear()
        self.logger.info("Query cache cleared")
    
    async def optimize_query(self, query: str, query_type: str = 'cypher') -> str:
        """Optimize query for better performance"""
        try:
            if query_type == 'cypher':
                # Add basic Cypher optimizations
                optimized = query
                
                # Add LIMIT if missing
                if 'LIMIT' not in optimized.upper():
                    optimized += " LIMIT 1000"
                
                # Suggest using indexes
                if 'WHERE' in optimized.upper() and 'INDEX' not in optimized.upper():
                    self.logger.info("Consider adding indexes for better performance")
                
                return optimized
            
            return query
            
        except Exception as e:
            self.logger.error(f"Error optimizing query: {e}")
            return query