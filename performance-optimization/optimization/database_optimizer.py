"""
Database optimization utilities
"""

import asyncio
import asyncpg
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional, Tuple
import logging
import time
from dataclasses import dataclass
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@dataclass
class QueryStats:
    """Database query statistics"""
    query: str
    calls: int
    total_time: float
    mean_time: float
    min_time: float
    max_time: float
    stddev_time: float
    rows: int


@dataclass
class IndexSuggestion:
    """Index suggestion"""
    table_name: str
    columns: List[str]
    index_type: str
    expected_benefit: str
    query_pattern: str


class DatabaseOptimizer:
    """Database performance optimizer"""
    
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        self.pool = None
    
    async def initialize_pool(self, min_size: int = 5, max_size: int = 20):
        """Initialize connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                min_size=min_size,
                max_size=max_size,
                **self.connection_params
            )
            logger.info("Database pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    async def close_pool(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool"""
        if not self.pool:
            await self.initialize_pool()
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def analyze_slow_queries(self, min_duration_ms: int = 100) -> List[QueryStats]:
        """Analyze slow queries from pg_stat_statements"""
        query = """
        SELECT 
            query,
            calls,
            total_time,
            mean_time,
            min_time,
            max_time,
            stddev_time,
            rows
        FROM pg_stat_statements 
        WHERE mean_time > $1
        ORDER BY mean_time DESC 
        LIMIT 50
        """
        
        async with self.get_connection() as conn:
            try:
                rows = await conn.fetch(query, min_duration_ms)
                return [
                    QueryStats(
                        query=row['query'],
                        calls=row['calls'],
                        total_time=row['total_time'],
                        mean_time=row['mean_time'],
                        min_time=row['min_time'],
                        max_time=row['max_time'],
                        stddev_time=row['stddev_time'],
                        rows=row['rows']
                    ) for row in rows
                ]
            except Exception as e:
                logger.error(f"Failed to analyze slow queries: {e}")
                return []
    
    async def get_missing_indexes(self) -> List[IndexSuggestion]:
        """Suggest missing indexes based on query patterns"""
        suggestions = []
        
        # Check for sequential scans on large tables
        seq_scan_query = """
        SELECT 
            schemaname,
            tablename,
            seq_scan,
            seq_tup_read,
            idx_scan,
            n_tup_ins + n_tup_upd + n_tup_del as modifications
        FROM pg_stat_user_tables 
        WHERE seq_scan > 1000 AND seq_tup_read > 100000
        ORDER BY seq_tup_read DESC
        """
        
        async with self.get_connection() as conn:
            try:
                rows = await conn.fetch(seq_scan_query)
                
                for row in rows:
                    table_name = f"{row['schemaname']}.{row['tablename']}"
                    
                    # Get frequently filtered columns
                    filtered_columns = await self._get_filtered_columns(conn, table_name)
                    
                    if filtered_columns:
                        suggestions.append(IndexSuggestion(
                            table_name=table_name,
                            columns=filtered_columns,
                            index_type="btree",
                            expected_benefit=f"Reduce {row['seq_scan']} sequential scans",
                            query_pattern="WHERE clauses on these columns"
                        ))
                
            except Exception as e:
                logger.error(f"Failed to get missing indexes: {e}")
        
        return suggestions
    
    async def _get_filtered_columns(self, conn, table_name: str) -> List[str]:
        """Get columns frequently used in WHERE clauses"""
        # This is a simplified approach - in practice, you'd analyze query logs
        # or use query plan analysis
        
        # Get columns with low cardinality (good for indexing)
        query = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = $1 
        AND data_type IN ('integer', 'bigint', 'uuid', 'varchar', 'text', 'timestamp')
        LIMIT 5
        """
        
        try:
            table_only = table_name.split('.')[-1]
            rows = await conn.fetch(query, table_only)
            return [row['column_name'] for row in rows]
        except Exception:
            return []
    
    async def analyze_table_stats(self) -> Dict[str, Any]:
        """Analyze table statistics"""
        query = """
        SELECT 
            schemaname,
            tablename,
            n_tup_ins as inserts,
            n_tup_upd as updates,
            n_tup_del as deletes,
            n_live_tup as live_tuples,
            n_dead_tup as dead_tuples,
            last_vacuum,
            last_autovacuum,
            last_analyze,
            last_autoanalyze
        FROM pg_stat_user_tables
        ORDER BY n_live_tup DESC
        """
        
        async with self.get_connection() as conn:
            try:
                rows = await conn.fetch(query)
                
                tables_needing_vacuum = []
                tables_needing_analyze = []
                
                for row in rows:
                    dead_ratio = row['dead_tuples'] / max(row['live_tuples'], 1)
                    
                    if dead_ratio > 0.1:  # More than 10% dead tuples
                        tables_needing_vacuum.append({
                            'table': f"{row['schemaname']}.{row['tablename']}",
                            'dead_ratio': dead_ratio,
                            'last_vacuum': row['last_vacuum']
                        })
                    
                    # Check if statistics are stale
                    if row['last_analyze'] is None or row['last_autoanalyze'] is None:
                        tables_needing_analyze.append({
                            'table': f"{row['schemaname']}.{row['tablename']}",
                            'last_analyze': row['last_analyze']
                        })
                
                return {
                    'total_tables': len(rows),
                    'tables_needing_vacuum': tables_needing_vacuum,
                    'tables_needing_analyze': tables_needing_analyze,
                    'table_stats': [dict(row) for row in rows[:20]]  # Top 20 tables
                }
                
            except Exception as e:
                logger.error(f"Failed to analyze table stats: {e}")
                return {}
    
    async def get_index_usage(self) -> List[Dict[str, Any]]:
        """Analyze index usage"""
        query = """
        SELECT 
            schemaname,
            tablename,
            indexname,
            idx_scan,
            idx_tup_read,
            idx_tup_fetch
        FROM pg_stat_user_indexes
        ORDER BY idx_scan DESC
        """
        
        async with self.get_connection() as conn:
            try:
                rows = await conn.fetch(query)
                
                unused_indexes = []
                frequently_used_indexes = []
                
                for row in rows:
                    if row['idx_scan'] == 0:
                        unused_indexes.append(dict(row))
                    elif row['idx_scan'] > 10000:
                        frequently_used_indexes.append(dict(row))
                
                return {
                    'total_indexes': len(rows),
                    'unused_indexes': unused_indexes,
                    'frequently_used_indexes': frequently_used_indexes[:10]
                }
                
            except Exception as e:
                logger.error(f"Failed to analyze index usage: {e}")
                return []
    
    async def get_lock_analysis(self) -> Dict[str, Any]:
        """Analyze database locks"""
        query = """
        SELECT 
            pg_class.relname,
            pg_locks.locktype,
            pg_locks.mode,
            pg_locks.granted,
            pg_stat_activity.query,
            pg_stat_activity.state,
            pg_stat_activity.query_start
        FROM pg_locks
        JOIN pg_class ON pg_locks.relation = pg_class.oid
        JOIN pg_stat_activity ON pg_locks.pid = pg_stat_activity.pid
        WHERE NOT pg_locks.granted
        ORDER BY pg_stat_activity.query_start
        """
        
        async with self.get_connection() as conn:
            try:
                rows = await conn.fetch(query)
                
                blocked_queries = []
                for row in rows:
                    blocked_queries.append({
                        'table': row['relname'],
                        'lock_type': row['locktype'],
                        'lock_mode': row['mode'],
                        'query': row['query'][:200] if row['query'] else None,
                        'state': row['state'],
                        'waiting_since': row['query_start']
                    })
                
                return {
                    'blocked_queries': blocked_queries,
                    'total_blocked': len(blocked_queries)
                }
                
            except Exception as e:
                logger.error(f"Failed to analyze locks: {e}")
                return {}
    
    async def optimize_queries(self, queries: List[str]) -> List[Dict[str, Any]]:
        """Analyze and suggest optimizations for specific queries"""
        optimizations = []
        
        async with self.get_connection() as conn:
            for query in queries:
                try:
                    # Get query plan
                    explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
                    result = await conn.fetchval(explain_query)
                    
                    plan = result[0]['Plan']
                    
                    suggestions = []
                    
                    # Check for sequential scans
                    if self._has_seq_scan(plan):
                        suggestions.append("Consider adding indexes for filtered columns")
                    
                    # Check for expensive operations
                    if plan.get('Total Cost', 0) > 1000:
                        suggestions.append("High cost query - consider query rewrite")
                    
                    # Check for sorting
                    if self._has_sort(plan):
                        suggestions.append("Consider adding ORDER BY index")
                    
                    optimizations.append({
                        'query': query[:200],
                        'total_cost': plan.get('Total Cost', 0),
                        'execution_time': plan.get('Actual Total Time', 0),
                        'suggestions': suggestions,
                        'plan': plan
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to analyze query: {e}")
                    optimizations.append({
                        'query': query[:200],
                        'error': str(e)
                    })
        
        return optimizations
    
    def _has_seq_scan(self, plan: Dict[str, Any]) -> bool:
        """Check if plan contains sequential scan"""
        if plan.get('Node Type') == 'Seq Scan':
            return True
        
        for child in plan.get('Plans', []):
            if self._has_seq_scan(child):
                return True
        
        return False
    
    def _has_sort(self, plan: Dict[str, Any]) -> bool:
        """Check if plan contains sort operation"""
        if plan.get('Node Type') == 'Sort':
            return True
        
        for child in plan.get('Plans', []):
            if self._has_sort(child):
                return True
        
        return False
    
    async def create_recommended_indexes(self, suggestions: List[IndexSuggestion], dry_run: bool = True) -> List[str]:
        """Create recommended indexes"""
        created_indexes = []
        
        async with self.get_connection() as conn:
            for suggestion in suggestions:
                try:
                    index_name = f"idx_{suggestion.table_name.replace('.', '_')}_{'_'.join(suggestion.columns)}"
                    columns_str = ', '.join(suggestion.columns)
                    
                    create_query = f"""
                    CREATE INDEX CONCURRENTLY {index_name}
                    ON {suggestion.table_name} 
                    USING {suggestion.index_type} ({columns_str})
                    """
                    
                    if dry_run:
                        logger.info(f"DRY RUN: Would create index: {create_query}")
                        created_indexes.append(f"DRY RUN: {index_name}")
                    else:
                        await conn.execute(create_query)
                        created_indexes.append(index_name)
                        logger.info(f"Created index: {index_name}")
                
                except Exception as e:
                    logger.error(f"Failed to create index: {e}")
        
        return created_indexes
    
    async def vacuum_analyze_tables(self, table_names: List[str] = None) -> Dict[str, Any]:
        """Run VACUUM ANALYZE on specified tables or all tables"""
        results = {}
        
        async with self.get_connection() as conn:
            if table_names is None:
                # Get all user tables
                query = "SELECT schemaname || '.' || tablename as full_name FROM pg_stat_user_tables"
                rows = await conn.fetch(query)
                table_names = [row['full_name'] for row in rows]
            
            for table_name in table_names:
                try:
                    start_time = time.time()
                    await conn.execute(f"VACUUM ANALYZE {table_name}")
                    end_time = time.time()
                    
                    results[table_name] = {
                        'status': 'success',
                        'duration': end_time - start_time
                    }
                    
                except Exception as e:
                    results[table_name] = {
                        'status': 'error',
                        'error': str(e)
                    }
        
        return results
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get database connection statistics"""
        query = """
        SELECT 
            state,
            COUNT(*) as count
        FROM pg_stat_activity 
        WHERE datname = current_database()
        GROUP BY state
        """
        
        async with self.get_connection() as conn:
            try:
                rows = await conn.fetch(query)
                
                connection_stats = {}
                total_connections = 0
                
                for row in rows:
                    connection_stats[row['state'] or 'unknown'] = row['count']
                    total_connections += row['count']
                
                # Get max connections
                max_conn_result = await conn.fetchval("SHOW max_connections")
                max_connections = int(max_conn_result)
                
                return {
                    'total_connections': total_connections,
                    'max_connections': max_connections,
                    'connection_utilization': total_connections / max_connections,
                    'by_state': connection_stats
                }
                
            except Exception as e:
                logger.error(f"Failed to get connection stats: {e}")
                return {}
    
    async def generate_optimization_report(self) -> Dict[str, Any]:
        """Generate comprehensive optimization report"""
        logger.info("Generating database optimization report...")
        
        tasks = [
            self.analyze_slow_queries(),
            self.get_missing_indexes(),
            self.analyze_table_stats(),
            self.get_index_usage(),
            self.get_lock_analysis(),
            self.get_connection_stats()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'timestamp': time.time(),
            'slow_queries': results[0] if not isinstance(results[0], Exception) else [],
            'missing_indexes': results[1] if not isinstance(results[1], Exception) else [],
            'table_stats': results[2] if not isinstance(results[2], Exception) else {},
            'index_usage': results[3] if not isinstance(results[3], Exception) else [],
            'lock_analysis': results[4] if not isinstance(results[4], Exception) else {},
            'connection_stats': results[5] if not isinstance(results[5], Exception) else {}
        }


# Utility functions for connection pooling
class ConnectionPoolManager:
    """Manage database connection pools"""
    
    def __init__(self):
        self.pools = {}
    
    async def get_pool(self, name: str, connection_params: Dict[str, Any], **pool_kwargs) -> asyncpg.Pool:
        """Get or create connection pool"""
        if name not in self.pools:
            self.pools[name] = await asyncpg.create_pool(
                **connection_params,
                **pool_kwargs
            )
        
        return self.pools[name]
    
    async def close_all_pools(self):
        """Close all connection pools"""
        for pool in self.pools.values():
            await pool.close()
        self.pools.clear()


# Global pool manager
pool_manager = ConnectionPoolManager()


# Example usage
if __name__ == "__main__":
    async def main():
        # Database connection parameters
        conn_params = {
            'host': 'localhost',
            'port': 5432,
            'user': 'llm_user',
            'password': 'password',
            'database': 'llm_platform'
        }
        
        optimizer = DatabaseOptimizer(conn_params)
        
        try:
            # Generate optimization report
            report = await optimizer.generate_optimization_report()
            
            print("Database Optimization Report:")
            print(f"Slow queries found: {len(report['slow_queries'])}")
            print(f"Missing indexes suggested: {len(report['missing_indexes'])}")
            print(f"Tables needing vacuum: {len(report['table_stats'].get('tables_needing_vacuum', []))}")
            
            # Example: Create recommended indexes (dry run)
            if report['missing_indexes']:
                created = await optimizer.create_recommended_indexes(
                    report['missing_indexes'], 
                    dry_run=True
                )
                print(f"Recommended indexes: {created}")
        
        finally:
            await optimizer.close_pool()
    
    asyncio.run(main())