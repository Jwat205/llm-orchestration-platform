"""
Query Processor - Advanced graph query processing and hybrid search
Handles complex graph queries, SPARQL-like queries, and hybrid vector-graph search
"""

from typing import Dict, List, Any, Optional, Tuple, Union
import asyncio
import re
from dataclasses import dataclass
from enum import Enum
import logging

from app.graph_service.core.graph_engine import GraphEngine
from app.graph_service.algorithms.path_finding import PathFinding
from app.graph_service.algorithms.similarity_propagation import SimilarityPropagation
from ...shared.schemas.graph_schemas import (
    GraphSearchRequest, GraphSearchResponse, RelationshipQuery,
    HybridSearchRequest, GraphEntity, GraphRelationship
)

logger = logging.getLogger(__name__)

class QueryType(Enum):
    ENTITY_SEARCH = "entity_search"
    RELATIONSHIP_QUERY = "relationship_query"
    PATH_QUERY = "path_query"
    SUBGRAPH_QUERY = "subgraph_query"
    PATTERN_MATCH = "pattern_match"
    AGGREGATE_QUERY = "aggregate_query"

@dataclass
class QueryPlan:
    """Query execution plan"""
    query_type: QueryType
    steps: List[Dict[str, Any]]
    estimated_cost: float
    use_cache: bool
    parallel_execution: bool

class QueryParser:
    """Parse and validate graph queries"""
    
    def __init__(self):
        self.sparql_patterns = {
            'select': r'SELECT\s+(.+?)\s+WHERE\s*\{(.+)\}',
            'match': r'MATCH\s+\((.+?)\)',
            'where': r'WHERE\s+(.+)',
            'return': r'RETURN\s+(.+)'
        }
    
    def parse_sparql_like_query(self, query: str) -> Dict[str, Any]:
        """Parse SPARQL-like query syntax"""
        try:
            query = query.strip()
            parsed = {
                'type': 'sparql',
                'select_clause': None,
                'match_patterns': [],
                'where_conditions': [],
                'return_clause': None
            }
            
            # Extract SELECT clause
            select_match = re.search(self.sparql_patterns['select'], query, re.IGNORECASE | re.DOTALL)
            if select_match:
                parsed['select_clause'] = select_match.group(1).strip()
                where_clause = select_match.group(2).strip()
                parsed['where_conditions'] = self._parse_where_clause(where_clause)
            
            # Extract MATCH patterns
            match_patterns = re.findall(self.sparql_patterns['match'], query, re.IGNORECASE)
            parsed['match_patterns'] = [pattern.strip() for pattern in match_patterns]
            
            # Extract RETURN clause
            return_match = re.search(self.sparql_patterns['return'], query, re.IGNORECASE)
            if return_match:
                parsed['return_clause'] = return_match.group(1).strip()
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing SPARQL-like query: {e}")
            raise ValueError(f"Invalid query syntax: {e}")
    
    def _parse_where_clause(self, where_clause: str) -> List[Dict[str, Any]]:
        """Parse WHERE clause conditions"""
        conditions = []
        
        # Simple pattern matching for basic conditions
        # This would be expanded for full SPARQL support
        patterns = where_clause.split('.')
        
        for pattern in patterns:
            pattern = pattern.strip()
            if pattern:
                conditions.append({'pattern': pattern})
        
        return conditions
    
    def parse_cypher_query(self, query: str) -> Dict[str, Any]:
        """Parse Cypher query syntax"""
        try:
            # Basic Cypher parsing - would be expanded for full support
            query = query.strip()
            parsed = {
                'type': 'cypher',
                'match_clause': None,
                'where_clause': None,
                'return_clause': None
            }
            
            # Extract MATCH clause
            match_pattern = r'MATCH\s+(.+?)(?:\s+WHERE|\s+RETURN|$)'
            match_match = re.search(match_pattern, query, re.IGNORECASE | re.DOTALL)
            if match_match:
                parsed['match_clause'] = match_match.group(1).strip()
            
            # Extract WHERE clause
            where_pattern = r'WHERE\s+(.+?)(?:\s+RETURN|$)'
            where_match = re.search(where_pattern, query, re.IGNORECASE | re.DOTALL)
            if where_match:
                parsed['where_clause'] = where_match.group(1).strip()
            
            # Extract RETURN clause
            return_pattern = r'RETURN\s+(.+)'
            return_match = re.search(return_pattern, query, re.IGNORECASE)
            if return_match:
                parsed['return_clause'] = return_match.group(1).strip()
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing Cypher query: {e}")
            raise ValueError(f"Invalid Cypher syntax: {e}")

class QueryOptimizer:
    """Optimize graph queries for better performance"""
    
    def __init__(self, graph_engine: GraphEngine):
        self.graph_engine = graph_engine
    
    async def create_query_plan(self, query: Dict[str, Any]) -> QueryPlan:
        """Create optimized query execution plan"""
        try:
            query_type = self._determine_query_type(query)
            steps = await self._generate_execution_steps(query, query_type)
            cost = await self._estimate_query_cost(steps)
            
            plan = QueryPlan(
                query_type=query_type,
                steps=steps,
                estimated_cost=cost,
                use_cache=cost > 100,  # Use cache for expensive queries
                parallel_execution=len(steps) > 3
            )
            
            return plan
            
        except Exception as e:
            logger.error(f"Error creating query plan: {e}")
            raise
    
    def _determine_query_type(self, query: Dict[str, Any]) -> QueryType:
        """Determine the type of query for optimization"""
        if 'entity_search' in query or 'entities' in query:
            return QueryType.ENTITY_SEARCH
        elif 'relationship' in query or 'relationships' in query:
            return QueryType.RELATIONSHIP_QUERY
        elif 'path' in query or 'paths' in query:
            return QueryType.PATH_QUERY
        elif 'subgraph' in query:
            return QueryType.SUBGRAPH_QUERY
        elif 'pattern' in query:
            return QueryType.PATTERN_MATCH
        else:
            return QueryType.ENTITY_SEARCH
    
    async def _generate_execution_steps(
        self, 
        query: Dict[str, Any], 
        query_type: QueryType
    ) -> List[Dict[str, Any]]:
        """Generate optimized execution steps"""
        steps = []
        
        if query_type == QueryType.ENTITY_SEARCH:
            steps.extend([
                {'operation': 'index_lookup', 'params': query.get('filters', {})},
                {'operation': 'filter_results', 'params': query.get('conditions', [])},
                {'operation': 'rank_results', 'params': {'limit': query.get('limit', 50)}}
            ])
        
        elif query_type == QueryType.RELATIONSHIP_QUERY:
            steps.extend([
                {'operation': 'entity_lookup', 'params': {'entities': query.get('entities', [])}},
                {'operation': 'relationship_traversal', 'params': query.get('traversal', {})},
                {'operation': 'aggregate_results', 'params': query.get('aggregation', {})}
            ])
        
        elif query_type == QueryType.PATH_QUERY:
            steps.extend([
                {'operation': 'source_target_lookup', 'params': {
                    'source': query.get('source'),
                    'target': query.get('target')
                }},
                {'operation': 'path_finding', 'params': {
                    'algorithm': query.get('algorithm', 'dijkstra'),
                    'max_depth': query.get('max_depth', 5)
                }},
                {'operation': 'path_ranking', 'params': {'criteria': query.get('ranking', 'shortest')}}
            ])
        
        return steps
    
    async def _estimate_query_cost(self, steps: List[Dict[str, Any]]) -> float:
        """Estimate query execution cost"""
        base_costs = {
            'index_lookup': 1.0,
            'entity_lookup': 2.0,
            'relationship_traversal': 5.0,
            'path_finding': 10.0,
            'subgraph_extraction': 15.0,
            'pattern_matching': 20.0
        }
        
        total_cost = sum(base_costs.get(step['operation'], 1.0) for step in steps)
        return total_cost

class QueryProcessor:
    """Main query processing engine"""
    
    def __init__(self, graph_engine: GraphEngine):
        self.graph_engine = graph_engine
        self.parser = QueryParser()
        self.optimizer = QueryOptimizer(graph_engine)
        self.path_finder = PathFinding(graph_engine.storage)
        self.similarity_propagation = SimilarityPropagation(graph_engine.storage)
        self.query_cache = {}
    
    async def search_graph(self, request: GraphSearchRequest) -> GraphSearchResponse:
        """Execute graph search query"""
        try:
            # Parse query
            if request.query_language == 'sparql':
                parsed_query = self.parser.parse_sparql_like_query(request.query)
            elif request.query_language == 'cypher':
                parsed_query = self.parser.parse_cypher_query(request.query)
            else:
                # Simple structured query
                parsed_query = {
                    'type': 'structured',
                    'filters': request.filters,
                    'conditions': request.conditions
                }
            
            # Create execution plan
            query_plan = await self.optimizer.create_query_plan(parsed_query)
            
            # Execute query
            results = await self._execute_query_plan(query_plan, request)
            
            # Build response
            response = GraphSearchResponse(
                entities=results.get('entities', []),
                relationships=results.get('relationships', []),
                paths=results.get('paths', []),
                metadata={
                    'total_results': len(results.get('entities', [])),
                    'execution_time': results.get('execution_time', 0),
                    'query_cost': query_plan.estimated_cost
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error in graph search: {e}")
            raise
    
    async def hybrid_search(self, request: HybridSearchRequest) -> Dict[str, Any]:
        """Perform hybrid vector-graph search"""
        try:
            # Vector search component
            vector_results = await self._vector_search(
                query=request.query_text,
                embedding_model=request.embedding_model,
                top_k=request.vector_top_k
            )
            
            # Graph traversal component
            graph_results = await self._graph_traversal_search(
                entities=vector_results,
                traversal_depth=request.traversal_depth,
                relationship_types=request.relationship_filters
            )
            
            # Combine and rank results
            combined_results = await self._combine_hybrid_results(
                vector_results, 
                graph_results,
                request.ranking_strategy
            )
            
            return {
                'results': combined_results,
                'vector_component': {
                    'count': len(vector_results),
                    'avg_similarity': sum(r.get('similarity', 0) for r in vector_results) / len(vector_results) if vector_results else 0
                },
                'graph_component': {
                    'count': len(graph_results),
                    'traversal_depth': request.traversal_depth
                },
                'hybrid_score': self._calculate_hybrid_score(combined_results)
            }
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            raise
    
    async def query_relationships(self, query: RelationshipQuery) -> List[GraphRelationship]:
        """Query relationships in the knowledge graph"""
        try:
            relationships = []
            
            if query.source_entity and query.target_entity:
                # Direct relationship query
                relationships = await self.graph_engine.storage.get_relationships_between(
                    source_id=query.source_entity,
                    target_id=query.target_entity,
                    relationship_types=query.relationship_types
                )
            
            elif query.source_entity:
                # Outgoing relationships
                relationships = await self.graph_engine.storage.get_outgoing_relationships(
                    entity_id=query.source_entity,
                    relationship_types=query.relationship_types,
                    max_depth=query.max_depth
                )
            
            elif query.target_entity:
                # Incoming relationships
                relationships = await self.graph_engine.storage.get_incoming_relationships(
                    entity_id=query.target_entity,
                    relationship_types=query.relationship_types,
                    max_depth=query.max_depth
                )
            
            else:
                # Global relationship search
                relationships = await self.graph_engine.storage.search_relationships(
                    relationship_types=query.relationship_types,
                    properties=query.property_filters,
                    limit=query.limit
                )
            
            # Apply additional filters
            if query.confidence_threshold:
                relationships = [
                    rel for rel in relationships 
                    if rel.confidence >= query.confidence_threshold
                ]
            
            # Sort by relevance
            if query.sort_by:
                relationships.sort(
                    key=lambda x: getattr(x, query.sort_by, 0),
                    reverse=query.sort_order == 'desc'
                )
            
            return relationships[:query.limit] if query.limit else relationships
            
        except Exception as e:
            logger.error(f"Error querying relationships: {e}")
            raise
    
    async def _execute_query_plan(
        self, 
        query_plan: QueryPlan, 
        request: GraphSearchRequest
    ) -> Dict[str, Any]:
        """Execute the optimized query plan"""
        try:
            results = {
                'entities': [],
                'relationships': [],
                'paths': [],
                'execution_time': 0
            }
            
            import time
            start_time = time.time()
            
            # Execute steps
            if query_plan.parallel_execution:
                # Parallel execution for independent steps
                tasks = []
                for step in query_plan.steps:
                    task = asyncio.create_task(self._execute_step(step, request))
                    tasks.append(task)
                
                step_results = await asyncio.gather(*tasks)
                
                # Combine results
                for step_result in step_results:
                    if step_result:
                        results['entities'].extend(step_result.get('entities', []))
                        results['relationships'].extend(step_result.get('relationships', []))
                        results['paths'].extend(step_result.get('paths', []))
            
            else:
                # Sequential execution
                context = {}
                for step in query_plan.steps:
                    step_result = await self._execute_step(step, request, context)
                    if step_result:
                        context.update(step_result)
                        results['entities'].extend(step_result.get('entities', []))
                        results['relationships'].extend(step_result.get('relationships', []))
                        results['paths'].extend(step_result.get('paths', []))
            
            results['execution_time'] = time.time() - start_time
            return results
            
        except Exception as e:
            logger.error(f"Error executing query plan: {e}")
            raise
    
    async def _execute_step(
        self, 
        step: Dict[str, Any], 
        request: GraphSearchRequest,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a single query step"""
        operation = step['operation']
        params = step['params']
        
        if operation == 'index_lookup':
            entities = await self.graph_engine.storage.search_entities(
                filters=params,
                limit=request.limit
            )
            return {'entities': entities}
        
        elif operation == 'relationship_traversal':
            if context and 'entities' in context:
                relationships = []
                for entity in context['entities']:
                    entity_rels = await self.graph_engine.storage.get_entity_relationships(
                        entity.id,
                        max_depth=params.get('max_depth', 1)
                    )
                    relationships.extend(entity_rels)
                return {'relationships': relationships}
        
        elif operation == 'path_finding':
            paths = await self.path_finder.find_paths(
                source=params.get('source'),
                target=params.get('target'),
                max_depth=params.get('max_depth', 5),
                algorithm=params.get('algorithm', 'dijkstra')
            )
            return {'paths': paths}
        
        return {}
    
    async def _vector_search(
        self, 
        query: str, 
        embedding_model: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search"""
        # This would integrate with the embeddings service
        # For now, return mock results
        return [
            {'entity_id': f'entity_{i}', 'similarity': 0.9 - i * 0.1}
            for i in range(min(top_k, 10))
        ]
    
    async def _graph_traversal_search(
        self,
        entities: List[Dict[str, Any]],
        traversal_depth: int,
        relationship_types: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Perform graph traversal from seed entities"""
        try:
            traversal_results = []
            
            for entity in entities:
                entity_id = entity.get('entity_id')
                if entity_id:
                    # Traverse from this entity
                    neighbors = await self.graph_engine.storage.get_neighbors(
                        entity_id=entity_id,
                        max_depth=traversal_depth,
                        relationship_types=relationship_types
                    )
                    
                    for neighbor in neighbors:
                        traversal_results.append({
                            'entity': neighbor,
                            'source_entity': entity_id,
                            'distance': neighbor.get('distance', 1)
                        })
            
            return traversal_results
            
        except Exception as e:
            logger.error(f"Error in graph traversal search: {e}")
            return []
    
    async def _combine_hybrid_results(
        self,
        vector_results: List[Dict[str, Any]],
        graph_results: List[Dict[str, Any]],
        ranking_strategy: str = 'weighted'
    ) -> List[Dict[str, Any]]:
        """Combine vector and graph search results"""
        try:
            combined = {}
            
            # Add vector results
            for result in vector_results:
                entity_id = result.get('entity_id')
                if entity_id:
                    combined[entity_id] = {
                        'entity_id': entity_id,
                        'vector_score': result.get('similarity', 0),
                        'graph_score': 0,
                        'hybrid_score': 0
                    }
            
            # Add graph results
            for result in graph_results:
                entity = result.get('entity', {})
                entity_id = entity.get('id')
                if entity_id:
                    if entity_id not in combined:
                        combined[entity_id] = {
                            'entity_id': entity_id,
                            'vector_score': 0,
                            'graph_score': 0,
                            'hybrid_score': 0
                        }
                    
                    # Graph score based on distance (inverse)
                    distance = result.get('distance', 1)
                    combined[entity_id]['graph_score'] = 1.0 / distance
            
            # Calculate hybrid scores
            for entity_id, scores in combined.items():
                if ranking_strategy == 'weighted':
                    scores['hybrid_score'] = (
                        0.6 * scores['vector_score'] + 
                        0.4 * scores['graph_score']
                    )
                elif ranking_strategy == 'max':
                    scores['hybrid_score'] = max(
                        scores['vector_score'], 
                        scores['graph_score']
                    )
                else:  # additive
                    scores['hybrid_score'] = (
                        scores['vector_score'] + scores['graph_score']
                    )
            
            # Sort by hybrid score
            sorted_results = sorted(
                combined.values(),
                key=lambda x: x['hybrid_score'],
                reverse=True
            )
            
            return sorted_results
            
        except Exception as e:
            logger.error(f"Error combining hybrid results: {e}")
            return []
    
    def _calculate_hybrid_score(self, results: List[Dict[str, Any]]) -> float:
        """Calculate overall hybrid search quality score"""
        if not results:
            return 0.0
        
        avg_hybrid_score = sum(r.get('hybrid_score', 0) for r in results) / len(results)
        return avg_hybrid_score