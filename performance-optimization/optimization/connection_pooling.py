"""
Connection Pooling Optimizations
Advanced connection pooling for database and external services
"""

import asyncio
import aioredis
import asyncpg
import aiohttp
import logging
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from dataclasses import dataclass
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

@dataclass
class PoolConfig:
    """Connection pool configuration"""
    min_size: int = 5
    max_size: int = 20
    max_queries: int = 50000
    max_inactive_connection_lifetime: float = 300.0
    timeout: float = 30.0
    command_timeout: float = 10.0
    retry_attempts: int = 3
    retry_delay: float = 1.0

class DatabasePoolManager:
    """
    Advanced PostgreSQL connection pool manager
    Optimized for high-throughput LLM applications
    """
    
    def __init__(self, database_url: str, config: PoolConfig = None):
        self.database_url = database_url
        self.config = config or PoolConfig()
        self.pool: Optional[asyncpg.Pool] = None
        self._stats = {
            'connections_created': 0,
            'connections_closed': 0,
            'queries_executed': 0,
            'query_errors': 0,
            'pool_acquisitions': 0,
            'pool_releases': 0,
            'avg_query_time': 0.0,
            'total_query_time': 0.0
        }
    
    async def initialize(self):
        """Initialize the connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.config.min_size,
                max_size=self.config.max_size,
                max_queries=self.config.max_queries,
                max_inactive_connection_lifetime=self.config.max_inactive_connection_lifetime,
                timeout=self.config.timeout,
                command_timeout=self.config.command_timeout,
                init=self._init_connection
            )
            logger.info(f"Database pool initialized: {self.config.min_size}-{self.config.max_size} connections")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    async def _init_connection(self, connection):
        """Initialize individual connections with optimizations"""
        # Set connection-level optimizations
        await connection.execute("SET synchronous_commit = OFF")
        await connection.execute("SET wal_writer_delay = '10ms'")
        await connection.execute("SET checkpoint_completion_target = 0.9")
        await connection.execute("SET random_page_cost = 1.1")
        await connection.execute("SET effective_cache_size = '4GB'")
        
        self._stats['connections_created'] += 1
    
    @asynccontextmanager
    async def acquire_connection(self):
        """Acquire a connection from the pool with metrics"""
        if not self.pool:
            await self.initialize()
        
        start_time = time.time()
        connection = None
        
        try:
            connection = await self.pool.acquire(timeout=self.config.timeout)
            self._stats['pool_acquisitions'] += 1
            yield connection
        except Exception as e:
            logger.error(f"Error acquiring database connection: {e}")
            self._stats['query_errors'] += 1
            raise
        finally:
            if connection:
                await self.pool.release(connection)
                self._stats['pool_releases'] += 1
                
                # Update timing statistics
                query_time = time.time() - start_time
                self._stats['total_query_time'] += query_time
                self._stats['queries_executed'] += 1
                self._stats['avg_query_time'] = (
                    self._stats['total_query_time'] / self._stats['queries_executed']
                )
    
    async def execute(self, query: str, *args, retry: bool = True) -> Any:
        """Execute a query with automatic retry and metrics"""
        attempt = 0
        last_error = None
        
        while attempt < self.config.retry_attempts:
            try:
                async with self.acquire_connection() as conn:
                    result = await conn.fetch(query, *args)
                    return result
            except Exception as e:
                last_error = e
                attempt += 1
                
                if attempt < self.config.retry_attempts and retry:
                    logger.warning(f"Query attempt {attempt} failed, retrying: {e}")
                    await asyncio.sleep(self.config.retry_delay * attempt)
                else:
                    logger.error(f"Query failed after {attempt} attempts: {e}")
                    self._stats['query_errors'] += 1
                    raise last_error
        
        raise last_error
    
    async def execute_many(self, queries: List[tuple]) -> List[Any]:
        """Execute multiple queries efficiently"""
        results = []
        
        async with self.acquire_connection() as conn:
            async with conn.transaction():
                for query, args in queries:
                    try:
                        result = await conn.fetch(query, *args)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Batch query failed: {e}")
                        self._stats['query_errors'] += 1
                        raise
        
        return results
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        pool_size = len(self.pool._holders) if self.pool else 0
        pool_available = len([h for h in self.pool._holders if h._con is not None]) if self.pool else 0
        
        return {
            'pool_size': pool_size,
            'pool_available': pool_available,
            'pool_busy': pool_size - pool_available,
            'connections_created': self._stats['connections_created'],
            'connections_closed': self._stats['connections_closed'],
            'queries_executed': self._stats['queries_executed'],
            'query_errors': self._stats['query_errors'],
            'avg_query_time': self._stats['avg_query_time'],
            'error_rate': (self._stats['query_errors'] / max(self._stats['queries_executed'], 1)) * 100
        }
    
    async def close(self):
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
            self._stats['connections_closed'] += self._stats['connections_created']
            logger.info("Database pool closed")

class RedisPoolManager:
    """
    Redis connection pool manager with clustering support
    """
    
    def __init__(self, redis_url: str, config: PoolConfig = None):
        self.redis_url = redis_url
        self.config = config or PoolConfig()
        self.pool: Optional[aioredis.ConnectionPool] = None
        self.redis: Optional[aioredis.Redis] = None
        self._stats = {
            'commands_executed': 0,
            'command_errors': 0,
            'avg_command_time': 0.0,
            'total_command_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    async def initialize(self):
        """Initialize Redis connection pool"""
        try:
            # Parse Redis URL for connection parameters
            parsed = urlparse(self.redis_url)
            
            self.pool = aioredis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.config.max_size,
                socket_timeout=self.config.timeout,
                socket_connect_timeout=self.config.timeout,
                health_check_interval=30,
                retry_on_timeout=True
            )
            
            self.redis = aioredis.Redis(connection_pool=self.pool)
            
            # Test connection
            await self.redis.ping()
            logger.info(f"Redis pool initialized: {self.config.max_size} max connections")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis pool: {e}")
            raise
    
    async def execute_command(self, command: str, *args, **kwargs) -> Any:
        """Execute Redis command with metrics"""
        if not self.redis:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            result = await getattr(self.redis, command)(*args, **kwargs)
            
            # Update cache hit/miss statistics for GET operations
            if command == 'get' and result is not None:
                self._stats['cache_hits'] += 1
            elif command == 'get' and result is None:
                self._stats['cache_misses'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Redis command '{command}' failed: {e}")
            self._stats['command_errors'] += 1
            raise
        finally:
            # Update timing statistics
            command_time = time.time() - start_time
            self._stats['total_command_time'] += command_time
            self._stats['commands_executed'] += 1
            self._stats['avg_command_time'] = (
                self._stats['total_command_time'] / self._stats['commands_executed']
            )
    
    async def pipeline_execute(self, commands: List[tuple]) -> List[Any]:
        """Execute multiple Redis commands in a pipeline"""
        if not self.redis:
            await self.initialize()
        
        pipe = self.redis.pipeline()
        
        try:
            for command, args, kwargs in commands:
                getattr(pipe, command)(*args, **kwargs)
            
            results = await pipe.execute()
            return results
            
        except Exception as e:
            logger.error(f"Redis pipeline execution failed: {e}")
            self._stats['command_errors'] += len(commands)
            raise
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get Redis cache statistics"""
        total_requests = self._stats['cache_hits'] + self._stats['cache_misses']
        hit_rate = (self._stats['cache_hits'] / max(total_requests, 1)) * 100
        
        return {
            'commands_executed': self._stats['commands_executed'],
            'command_errors': self._stats['command_errors'],
            'avg_command_time': self._stats['avg_command_time'],
            'cache_hits': self._stats['cache_hits'],
            'cache_misses': self._stats['cache_misses'],
            'cache_hit_rate': hit_rate,
            'error_rate': (self._stats['command_errors'] / max(self._stats['commands_executed'], 1)) * 100
        }
    
    async def close(self):
        """Close Redis connection pool"""
        if self.pool:
            await self.pool.disconnect()
            logger.info("Redis pool closed")

class HTTPPoolManager:
    """
    HTTP connection pool manager for external APIs
    """
    
    def __init__(self, config: PoolConfig = None):
        self.config = config or PoolConfig()
        self.session: Optional[aiohttp.ClientSession] = None
        self._stats = {
            'requests_made': 0,
            'request_errors': 0,
            'avg_request_time': 0.0,
            'total_request_time': 0.0,
            'status_codes': {}
        }
    
    async def initialize(self):
        """Initialize HTTP session with connection pooling"""
        connector = aiohttp.TCPConnector(
            limit=self.config.max_size,
            limit_per_host=self.config.max_size // 2,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=60,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(
            total=self.config.timeout,
            connect=self.config.timeout / 3
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'LLM-Platform/1.0'}
        )
        
        logger.info("HTTP pool initialized")
    
    async def request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make HTTP request with metrics"""
        if not self.session:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                # Update statistics
                request_time = time.time() - start_time
                self._stats['total_request_time'] += request_time
                self._stats['requests_made'] += 1
                self._stats['avg_request_time'] = (
                    self._stats['total_request_time'] / self._stats['requests_made']
                )
                
                # Track status codes
                status_code = response.status
                self._stats['status_codes'][status_code] = (
                    self._stats['status_codes'].get(status_code, 0) + 1
                )
                
                return response
                
        except Exception as e:
            logger.error(f"HTTP request failed: {method} {url} - {e}")
            self._stats['request_errors'] += 1
            raise
    
    def get_http_stats(self) -> Dict[str, Any]:
        """Get HTTP pool statistics"""
        return {
            'requests_made': self._stats['requests_made'],
            'request_errors': self._stats['request_errors'],
            'avg_request_time': self._stats['avg_request_time'],
            'status_codes': self._stats['status_codes'],
            'error_rate': (self._stats['request_errors'] / max(self._stats['requests_made'], 1)) * 100
        }
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            logger.info("HTTP pool closed")

class PoolManager:
    """
    Unified connection pool manager for all services
    """
    
    def __init__(self, database_url: str, redis_url: str, 
                 db_config: PoolConfig = None, 
                 redis_config: PoolConfig = None,
                 http_config: PoolConfig = None):
        self.db_pool = DatabasePoolManager(database_url, db_config)
        self.redis_pool = RedisPoolManager(redis_url, redis_config)
        self.http_pool = HTTPPoolManager(http_config)
    
    async def initialize_all(self):
        """Initialize all connection pools"""
        await asyncio.gather(
            self.db_pool.initialize(),
            self.redis_pool.initialize(),
            self.http_pool.initialize()
        )
        logger.info("All connection pools initialized")
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics from all pools"""
        return {
            'database': self.db_pool.get_pool_stats(),
            'redis': self.redis_pool.get_cache_stats(),
            'http': self.http_pool.get_http_stats()
        }
    
    async def close_all(self):
        """Close all connection pools"""
        await asyncio.gather(
            self.db_pool.close(),
            self.redis_pool.close(),
            self.http_pool.close()
        )
        logger.info("All connection pools closed")

# Global pool manager instance
pool_manager: Optional[PoolManager] = None

async def initialize_pools(database_url: str, redis_url: str):
    """Initialize global pool manager"""
    global pool_manager
    pool_manager = PoolManager(database_url, redis_url)
    await pool_manager.initialize_all()

async def get_pool_stats():
    """Get global pool statistics"""
    if pool_manager:
        return pool_manager.get_all_stats()
    return {}

async def close_pools():
    """Close global pools"""
    if pool_manager:
        await pool_manager.close_all()