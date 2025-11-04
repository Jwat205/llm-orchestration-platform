import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Pattern
import redis
import aiofiles
from collections import defaultdict, deque
import grok

class LogCollector:
    """
    Log Collector - like a librarian who organizes and catalogs all your books.
    
    This processes logs from all your services to extract valuable insights:
    - Error patterns and trends
    - Performance bottlenecks
    - Security events
    - Business metrics from log data
    
    Think of this as your platform's memory system that remembers everything
    important that happened, making it searchable and actionable.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        
        # Log parsing patterns for different services
        self.log_patterns = self._initialize_log_patterns()
        
        # Error classification patterns
        self.error_patterns = self._initialize_error_patterns()
        
        # Performance tracking
        self.performance_keywords = [
            'slow', 'timeout', 'bottleneck', 'latency', 'response_time',
            'connection_pool', 'database_slow', 'memory_high'
        ]
        
        # Security event patterns
        self.security_patterns = self._initialize_security_patterns()
        
        # Buffer for batch processing
        self.log_buffer = deque(maxlen=1000)
        self.last_flush = datetime.utcnow()
        
    def _initialize_log_patterns(self) -> Dict[str, Pattern]:
        """
        Initialize regex patterns for parsing different log formats.
        Like having templates for reading different types of documents.
        """
        return {
            # Django logs
            'django': re.compile(
                r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+'
                r'(?P<level>\w+)\s+'
                r'(?P<logger>[\w.]+)\s+'
                r'(?P<message>.*)'
            ),
            
            # FastAPI/Uvicorn logs
            'fastapi': re.compile(
                r'(?P<level>\w+):\s+'
                r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d+)\s+'
                r'-\s+(?P<message>.*)'
            ),
            
            # Nginx access logs
            'nginx_access': re.compile(
                r'(?P<remote_addr>[\d.]+)\s+'
                r'-\s+(?P<remote_user>\S+)\s+'
                r'\[(?P<timestamp>[^\]]+)\]\s+'
                r'"(?P<method>\w+)\s+(?P<path>\S+)\s+(?P<protocol>[^"]+)"\s+'
                r'(?P<status>\d+)\s+'
                r'(?P<body_bytes_sent>\d+)\s+'
                r'"(?P<referrer>[^"]*)"\s+'
                r'"(?P<user_agent>[^"]*)"'
            ),
            
            # Application performance logs
            'performance': re.compile(
                r'(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d+Z?)\s+'
                r'.*response_time[=:]\s*(?P<response_time>[\d.]+)ms'
            ),
            
            # Error logs with stack traces
            'error_trace': re.compile(
                r'(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}[.,]\d+)\s+'
                r'(?P<level>ERROR|CRITICAL)\s+'
                r'(?P<message>.*?)(?P<traceback>Traceback.*)?$',
                re.DOTALL
            )
        }
    
    def _initialize_error_patterns(self) -> Dict[str, List[Pattern]]:
        """
        Initialize patterns for classifying different types of errors.
        Like having a diagnostic manual for different types of problems.
        """
        return {
            'database_errors': [
                re.compile(r'connection.*timeout', re.I),
                re.compile(r'database.*unavailable', re.I),
                re.compile(r'deadlock detected', re.I),
                re.compile(r'too many connections', re.I),
                re.compile(r'connection.*refused', re.I)
            ],
            'memory_errors': [
                re.compile(r'out of memory', re.I),
                re.compile(r'memory.*exhausted', re.I),
                re.compile(r'allocation.*failed', re.I),
                re.compile(r'heap.*overflow', re.I)
            ],
            'network_errors': [
                re.compile(r'connection.*reset', re.I),
                re.compile(r'network.*unreachable', re.I),
                re.compile(r'timeout.*reading', re.I),
                re.compile(r'socket.*error', re.I)
            ],
            'authentication_errors': [
                re.compile(r'authentication.*failed', re.I),
                re.compile(r'invalid.*credentials', re.I),
                re.compile(r'unauthorized.*access', re.I),
                re.compile(r'token.*expired', re.I)
            ],
            'rate_limit_errors': [
                re.compile(r'rate.*limit.*exceeded', re.I),
                re.compile(r'too many requests', re.I),
                re.compile(r'quota.*exceeded', re.I),
                re.compile(r'throttled', re.I)
            ],
            'validation_errors': [
                re.compile(r'validation.*error', re.I),
                re.compile(r'invalid.*input', re.I),
                re.compile(r'malformed.*request', re.I),
                re.compile(r'schema.*violation', re.I)
            ]
        }
    
    def _initialize_security_patterns(self) -> List[Pattern]:
        """
        Initialize patterns for detecting security-related events.
        Like having a security guard's checklist of suspicious activities.
        """
        return [
            re.compile(r'failed.*login.*attempt', re.I),
            re.compile(r'brute.*force', re.I),
            re.compile(r'sql.*injection', re.I),
            re.compile(r'xss.*attack', re.I),
            re.compile(r'csrf.*token.*mismatch', re.I),
            re.compile(r'unauthorized.*api.*access', re.I),
            re.compile(r'suspicious.*user.*agent', re.I),
            re.compile(r'multiple.*failed.*requests', re.I)
        ]
    
    async def process_log_stream(self) -> int:
        """
        Process incoming log streams from all services.
        Like a mail sorter processing incoming letters.
        """
        processed_count = 0
        
        try:
            # Check for new logs from different sources
            sources = ['django', 'fastapi', 'nginx', 'system']
            
            for source in sources:
                count = await self._process_source_logs(source)
                processed_count += count
            
            # Process buffered logs if buffer is full or enough time has passed
            if len(self.log_buffer) >= 100 or (datetime.utcnow() - self.last_flush).seconds >= 60:
                await self._flush_log_buffer()
            
            return processed_count
            
        except Exception as e:
            self.logger.error(f"Error processing log stream: {e}")
            return processed_count
    
    async def _process_source_logs(self, source: str) -> int:
        """Process logs from a specific source"""
        try:
            processed = 0
            
            # Get new log entries from Redis stream
            stream_key = f"logs:{source}:stream"
            
            # Read from stream (get last 100 entries)
            log_entries = self.redis_client.xrange(stream_key, count=100)
            
            for entry_id, fields in log_entries:
                try:
                    # Parse log entry
                    log_data = {
                        'id': entry_id.decode() if isinstance(entry_id, bytes) else entry_id,
                        'source': source,
                        'timestamp': datetime.utcnow().isoformat(),
                        'raw_message': fields.get(b'message', b'').decode() if isinstance(fields.get(b'message'), bytes) else fields.get('message', '')
                    }
                    
                    # Parse structured data from log message
                    parsed_data = await self._parse_log_message(log_data['raw_message'], source)
                    log_data.update(parsed_data)
                    
                    # Classify and enrich log entry
                    await self._classify_log_entry(log_data)
                    
                    # Add to buffer for batch processing
                    self.log_buffer.append(log_data)
                    processed += 1
                    
                except Exception as e:
                    self.logger.error(f"Error processing log entry from {source}: {e}")
                    continue
            
            return processed
            
        except Exception as e:
            self.logger.error(f"Error processing logs from {source}: {e}")
            return 0
    
    async def _parse_log_message(self, message: str, source: str) -> Dict[str, Any]:
        """
        Parse log message using appropriate pattern.
        Like having different reading glasses for different types of text.
        """
        parsed_data = {}
        
        try:
            # Try to match against known patterns
            for pattern_name, pattern in self.log_patterns.items():
                if source in pattern_name or pattern_name == 'performance':
                    match = pattern.match(message)
                    if match:
                        parsed_data.update(match.groupdict())
                        parsed_data['pattern_matched'] = pattern_name
                        break
            
            # Try to extract JSON data if present
            if '{' in message and '}' in message:
                try:
                    # Extract JSON portion
                    start = message.find('{')
                    end = message.rfind('}') + 1
                    json_str = message[start:end]
                    json_data = json.loads(json_str)
                    parsed_data['structured_data'] = json_data
                except (json.JSONDecodeError, ValueError):
                    pass
            
            # Extract key metrics if present
            parsed_data.update(self._extract_metrics_from_message(message))
            
            return parsed_data
            
        except Exception as e:
            self.logger.error(f"Error parsing log message: {e}")
            return {}
    
    def _extract_metrics_from_message(self, message: str) -> Dict[str, Any]:
        """
        Extract performance metrics from log messages.
        Like a detective looking for clues in witness statements.
        """
        metrics = {}
        
        try:
            # Response time patterns
            response_time_patterns = [
                r'response_time[=:]\s*([\d.]+)ms',
                r'duration[=:]\s*([\d.]+)ms',
                r'took\s+([\d.]+)ms',
                r'elapsed[=:]\s*([\d.]+)ms'
            ]
            
            for pattern in response_time_patterns:
                match = re.search(pattern, message, re.I)
                if match:
                    metrics['response_time_ms'] = float(match.group(1))
                    break
            
            # Status code patterns
            status_match = re.search(r'status[=:]\s*(\d+)', message, re.I)
            if status_match:
                metrics['status_code'] = int(status_match.group(1))
            
            # User ID patterns
            user_patterns = [
                r'user[=:]\s*(\d+)',
                r'user_id[=:]\s*(\d+)',
                r'uid[=:]\s*(\d+)'
            ]
            
            for pattern in user_patterns:
                match = re.search(pattern, message, re.I)
                if match:
                    metrics['user_id'] = match.group(1)
                    break
            
            # Request ID patterns
            request_id_match = re.search(r'request_id[=:]\s*([a-f0-9-]+)', message, re.I)
            if request_id_match:
                metrics['request_id'] = request_id_match.group(1)
            
            # API endpoint patterns
            endpoint_match = re.search(r'endpoint[=:]\s*([^\s]+)', message, re.I)
            if endpoint_match:
                metrics['endpoint'] = endpoint_match.group(1)
            
            # Method patterns
            method_match = re.search(r'method[=:]\s*(GET|POST|PUT|DELETE|PATCH)', message, re.I)
            if method_match:
                metrics['method'] = method_match.group(1).upper()
            
            # Token usage patterns
            tokens_match = re.search(r'tokens[=:]\s*(\d+)', message, re.I)
            if tokens_match:
                metrics['tokens_used'] = int(tokens_match.group(1))
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error extracting metrics from message: {e}")
            return {}
    
    async def _classify_log_entry(self, log_data: Dict[str, Any]):
        """
        Classify log entry by type and severity.
        Like a triage nurse determining how urgent each case is.
        """
        try:
            message = log_data.get('raw_message', '').lower()
            level = log_data.get('level', '').upper()
            
            # Set base classification
            log_data['classification'] = {
                'type': 'application',
                'severity': level if level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] else 'INFO',
                'categories': []
            }
            
            # Error classification
            if level in ['ERROR', 'CRITICAL'] or 'error' in message:
                log_data['classification']['type'] = 'error'
                
                # Classify error type
                for error_type, patterns in self.error_patterns.items():
                    for pattern in patterns:
                        if pattern.search(message):
                            log_data['classification']['categories'].append(error_type)
                            break
            
            # Performance classification
            if any(keyword in message for keyword in self.performance_keywords):
                log_data['classification']['categories'].append('performance')
                
                # Check if it's a slow request (above your 100ms SLA)
                response_time = log_data.get('response_time_ms', 0)
                if response_time > 100:
                    log_data['classification']['categories'].append('sla_violation')
                if response_time > 500:
                    log_data['classification']['categories'].append('slow_request')
            
            # Security classification
            for pattern in self.security_patterns:
                if pattern.search(message):
                    log_data['classification']['categories'].append('security')
                    log_data['classification']['type'] = 'security'
                    break
            
            # Business metrics classification
            if any(keyword in message for keyword in ['payment', 'subscription', 'billing', 'user_signup']):
                log_data['classification']['categories'].append('business')
            
            # Access log classification
            if log_data.get('pattern_matched') == 'nginx_access':
                log_data['classification']['type'] = 'access'
                
                # Check for unusual status codes
                status_code = log_data.get('status_code', 200)
                if status_code >= 400:
                    log_data['classification']['categories'].append('http_error')
                if status_code >= 500:
                    log_data['classification']['categories'].append('server_error')
            
        except Exception as e:
            self.logger.error(f"Error classifying log entry: {e}")
    
    async def _flush_log_buffer(self):
        """
        Flush buffered logs to storage and analysis.
        Like emptying your mailbox and filing letters in appropriate folders.
        """
        try:
            if not self.log_buffer:
                return
            
            buffer_copy = list(self.log_buffer)
            self.log_buffer.clear()
            self.last_flush = datetime.utcnow()
            
            # Store logs in Redis for analysis
            await self._store_processed_logs(buffer_copy)
            
            # Generate analytics from this batch
            await self._analyze_log_batch(buffer_copy)
            
            # Check for alerts
            await self._check_log_alerts(buffer_copy)
            
            self.logger.debug(f"Flushed {len(buffer_copy)} log entries")
            
        except Exception as e:
            self.logger.error(f"Error flushing log buffer: {e}")
    
    async def _store_processed_logs(self, logs: List[Dict[str, Any]]):
        """Store processed logs in Redis with appropriate indexing"""
        try:
            current_hour = datetime.utcnow().strftime('%Y%m%d%H')
            
            # Store in time-based keys for efficient querying
            for log_entry in logs:
                # Store individual log
                log_key = f"logs:processed:{current_hour}:{log_entry.get('id', 'unknown')}"
                self.redis_client.setex(log_key, 86400, json.dumps(log_entry))  # 24 hours
                
                # Add to indices for fast searching
                categories = log_entry.get('classification', {}).get('categories', [])
                for category in categories:
                    index_key = f"logs:index:{category}:{current_hour}"
                    self.redis_client.sadd(index_key, log_entry.get('id', 'unknown'))
                    self.redis_client.expire(index_key, 86400)
                
                # Add to error index if it's an error
                if log_entry.get('classification', {}).get('type') == 'error':
                    error_key = f"logs:errors:{current_hour}"
                    self.redis_client.lpush(error_key, json.dumps(log_entry))
                    self.redis_client.expire(error_key, 604800)  # 7 days
            
        except Exception as e:
            self.logger.error(f"Error storing processed logs: {e}")
    
    async def _analyze_log_batch(self, logs: List[Dict[str, Any]]):
        """
        Analyze batch of logs for patterns and trends.
        Like a data analyst looking for insights in customer feedback.
        """
        try:
            analysis = {
                'timestamp': datetime.utcnow().isoformat(),
                'total_logs': len(logs),
                'by_level': defaultdict(int),
                'by_source': defaultdict(int),
                'by_category': defaultdict(int),
                'error_patterns': defaultdict(int),
                'performance_metrics': {
                    'slow_requests': 0,
                    'sla_violations': 0,
                    'avg_response_time': 0
                }
            }
            
            response_times = []
            
            # Analyze each log entry
            for log_entry in logs:
                # Count by level
                level = log_entry.get('level', 'INFO')
                analysis['by_level'][level] += 1
                
                # Count by source
                source = log_entry.get('source', 'unknown')
                analysis['by_source'][source] += 1
                
                # Count by categories
                categories = log_entry.get('classification', {}).get('categories', [])
                for category in categories:
                    analysis['by_category'][category] += 1
                
                # Analyze errors
                if log_entry.get('classification', {}).get('type') == 'error':
                    message = log_entry.get('raw_message', '')
                    # Simple error pattern detection
                    if 'timeout' in message.lower():
                        analysis['error_patterns']['timeout'] += 1
                    elif 'connection' in message.lower():
                        analysis['error_patterns']['connection'] += 1
                    elif 'memory' in message.lower():
                        analysis['error_patterns']['memory'] += 1
                    else:
                        analysis['error_patterns']['other'] += 1
                
                # Analyze performance
                response_time = log_entry.get('response_time_ms', 0)
                if response_time > 0:
                    response_times.append(response_time)
                    if response_time > 500:
                        analysis['performance_metrics']['slow_requests'] += 1
                    if response_time > 100:  # Your SLA target
                        analysis['performance_metrics']['sla_violations'] += 1
            
            # Calculate average response time
            if response_times:
                analysis['performance_metrics']['avg_response_time'] = sum(response_times) / len(response_times)
            
            # Store analysis
            analysis_key = f"logs:analysis:{datetime.utcnow().strftime('%Y%m%d%H%M')}"
            self.redis_client.setex(analysis_key, 3600, json.dumps(analysis))  # 1 hour
            
        except Exception as e:
            self.logger.error(f"Error analyzing log batch: {e}")
    
    async def _check_log_alerts(self, logs: List[Dict[str, Any]]):
        """
        Check logs for conditions that should trigger alerts.
        Like a security guard checking for unusual activities.
        """
        try:
            # Error rate alert
            error_count = sum(1 for log in logs if log.get('classification', {}).get('type') == 'error')
            error_rate = (error_count / len(logs)) * 100 if logs else 0
            
            if error_rate > 10:  # More than 10% errors
                alert = {
                    'type': 'log_alert',
                    'severity': 'critical',
                    'message': f'High error rate in logs: {error_rate:.1f}% ({error_count}/{len(logs)})',
                    'category': 'log_analysis',
                    'details': {
                        'error_count': error_count,
                        'total_logs': len(logs),
                        'error_rate': error_rate,
                        'time_window': '1 minute'
                    }
                }
                
                # Store alert
                alert_key = f"alerts:log_analysis:{int(datetime.utcnow().timestamp())}"
                self.redis_client.setex(alert_key, 3600, json.dumps(alert))
            
            # Security alert
            security_events = [log for log in logs if 'security' in log.get('classification', {}).get('categories', [])]
            if len(security_events) > 5:  # More than 5 security events
                alert = {
                    'type': 'log_alert',
                    'severity': 'warning',
                    'message': f'Multiple security events detected: {len(security_events)} events',
                    'category': 'security',
                    'details': {
                        'security_events': len(security_events),
                        'total_logs': len(logs),
                        'events': [log.get('raw_message', '')[:100] for log in security_events[:3]]
                    }
                }
                
                # Store alert
                alert_key = f"alerts:security:{int(datetime.utcnow().timestamp())}"
                self.redis_client.setex(alert_key, 3600, json.dumps(alert))
            
            # Performance alert
            slow_requests = sum(1 for log in logs if log.get('response_time_ms', 0) > 500)
            if slow_requests > len(logs) * 0.05:  # More than 5% slow requests
                alert = {
                    'type': 'log_alert',
                    'severity': 'warning',
                    'message': f'High number of slow requests: {slow_requests} requests > 500ms',
                    'category': 'performance',
                    'details': {
                        'slow_requests': slow_requests,
                        'total_requests': len(logs),
                        'percentage': (slow_requests / len(logs)) * 100
                    }
                }
                
                # Store alert
                alert_key = f"alerts:performance:{int(datetime.utcnow().timestamp())}"
                self.redis_client.setex(alert_key, 3600, json.dumps(alert))
            
        except Exception as e:
            self.logger.error(f"Error checking log alerts: {e}")
    
    async def search_logs(self, query: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search through processed logs.
        Like having a smart search engine for your log library.
        """
        try:
            results = []
            
            # Build search criteria
            start_time = query.get('start_time')
            end_time = query.get('end_time', datetime.utcnow())
            level = query.get('level')
            category = query.get('category')
            source = query.get('source')
            message_contains = query.get('message_contains', '').lower()
            
            # Search through time-based indices
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time)
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            elif start_time is None:
                start_time = end_time - timedelta(hours=24)  # Default to last 24 hours
            
            # Iterate through hours in the time range
            current_hour = start_time.replace(minute=0, second=0, microsecond=0)
            while current_hour <= end_time and len(results) < limit:
                hour_key = current_hour.strftime('%Y%m%d%H')
                
                # Search in category index if specified
                if category:
                    index_key = f"logs:index:{category}:{hour_key}"
                    log_ids = self.redis_client.smembers(index_key)
                else:
                    # Search all logs for this hour
                    pattern = f"logs:processed:{hour_key}:*"
                    log_ids = [key.split(':')[-1] for key in self.redis_client.scan_iter(match=pattern)]
                
                # Retrieve and filter logs
                for log_id in log_ids:
                    if len(results) >= limit:
                        break
                    
                    log_key = f"logs:processed:{hour_key}:{log_id}"
                    log_data = self.redis_client.get(log_key)
                    
                    if log_data:
                        try:
                            log_entry = json.loads(log_data)
                            
                            # Apply filters
                            if level and log_entry.get('level') != level:
                                continue
                            
                            if source and log_entry.get('source') != source:
                                continue
                            
                            if message_contains and message_contains not in log_entry.get('raw_message', '').lower():
                                continue
                            
                            results.append(log_entry)
                            
                        except json.JSONDecodeError:
                            continue
                
                current_hour += timedelta(hours=1)
            
            # Sort by timestamp (most recent first)
            results.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            self.logger.error(f"Error searching logs: {e}")
            return []
    
    async def get_log_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get log statistics for the specified time period.
        Like getting a summary report of all activities.
        """
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)
            
            stats = {
                'period': {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'hours': hours
                },
                'totals': {
                    'total_logs': 0,
                    'errors': 0,
                    'warnings': 0,
                    'security_events': 0,
                    'performance_issues': 0
                },
                'by_source': defaultdict(int),
                'by_category': defaultdict(int),
                'error_trends': [],
                'top_errors': []
            }
            
            # Analyze logs hour by hour
            current_hour = start_time.replace(minute=0, second=0, microsecond=0)
            while current_hour <= end_time:
                hour_key = current_hour.strftime('%Y%m%d%H')
                
                # Get analysis for this hour
                analysis_pattern = f"logs:analysis:{hour_key}*"
                for analysis_key in self.redis_client.scan_iter(match=analysis_pattern):
                    analysis_data = self.redis_client.get(analysis_key)
                    if analysis_data:
                        try:
                            analysis = json.loads(analysis_data)
                            
                            # Aggregate totals
                            stats['totals']['total_logs'] += analysis.get('total_logs', 0)
                            
                            # Aggregate by level
                            by_level = analysis.get('by_level', {})
                            stats['totals']['errors'] += by_level.get('ERROR', 0) + by_level.get('CRITICAL', 0)
                            stats['totals']['warnings'] += by_level.get('WARNING', 0)
                            
                            # Aggregate by source
                            for source, count in analysis.get('by_source', {}).items():
                                stats['by_source'][source] += count
                            
                            # Aggregate by category
                            for category, count in analysis.get('by_category', {}).items():
                                stats['by_category'][category] += count
                                
                                if category == 'security':
                                    stats['totals']['security_events'] += count
                                elif category in ['performance', 'slow_request']:
                                    stats['totals']['performance_issues'] += count
                            
                            # Store hourly error trend
                            stats['error_trends'].append({
                                'hour': current_hour.isoformat(),
                                'errors': by_level.get('ERROR', 0) + by_level.get('CRITICAL', 0),
                                'warnings': by_level.get('WARNING', 0)
                            })
                            
                        except json.JSONDecodeError:
                            continue
                
                current_hour += timedelta(hours=1)
            
            # Convert defaultdicts to regular dicts
            stats['by_source'] = dict(stats['by_source'])
            stats['by_category'] = dict(stats['by_category'])
            
            # Calculate rates
            if stats['totals']['total_logs'] > 0:
                stats['rates'] = {
                    'error_rate_percent': (stats['totals']['errors'] / stats['totals']['total_logs']) * 100,
                    'warning_rate_percent': (stats['totals']['warnings'] / stats['totals']['total_logs']) * 100,
                    'logs_per_hour': stats['totals']['total_logs'] / hours
                }
            else:
                stats['rates'] = {
                    'error_rate_percent': 0,
                    'warning_rate_percent': 0,
                    'logs_per_hour': 0
                }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting log statistics: {e}")
            return {'error': str(e)}
    
    async def cleanup_old_logs(self):
        """
        Clean up old logs to manage storage.
        Like cleaning out old files to keep your filing cabinet organized.
        """
        try:
            # Clean up logs older than 7 days
            cutoff_time = datetime.utcnow() - timedelta(days=7)
            cutoff_hour = cutoff_time.strftime('%Y%m%d%H')
            
            # Find and delete old log keys
            patterns = [
                "logs:processed:*",
                "logs:analysis:*",
                "logs:index:*",
                "logs:errors:*"
            ]
            
            deleted_count = 0
            
            for pattern in patterns:
                for key in self.redis_client.scan_iter(match=pattern):
                    key_str = key.decode() if isinstance(key, bytes) else key
                    
                    # Extract timestamp from key
                    parts = key_str.split(':')
                    if len(parts) >= 3:
                        timestamp_part = parts[2]
                        
                        # Check if it's a timestamp format we recognize
                        if len(timestamp_part) >= 10:  # YYYYMMDDHH or YYYYMMDDHHMM
                            try:
                                key_hour = timestamp_part[:10]
                                if key_hour < cutoff_hour:
                                    self.redis_client.delete(key)
                                    deleted_count += 1
                            except ValueError:
                                continue
            
            self.logger.info(f"Cleaned up {deleted_count} old log entries")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old logs: {e}")


class LogStreamProcessor:
    """
    Real-time log stream processor for handling high-volume log ingestion.
    Like a high-speed mail sorting machine for your platform's logs.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        self.log_collector = LogCollector(redis_client)
        self.processing_queue = asyncio.Queue(maxsize=10000)
        
    async def ingest_log_entry(self, source: str, message: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Ingest a single log entry into the processing system.
        Like accepting a new letter for processing.
        """
        try:
            log_entry = {
                'source': source,
                'message': message,
                'metadata': metadata or {},
                'ingested_at': datetime.utcnow().isoformat()
            }
            
            # Add to processing queue
            try:
                self.processing_queue.put_nowait(log_entry)
                return True
            except asyncio.QueueFull:
                self.logger.warning("Log processing queue is full, dropping log entry")
                return False
                
        except Exception as e:
            self.logger.error(f"Error ingesting log entry: {e}")
            return False
    
    async def process_queue_worker(self):
        """
        Background worker to process log entries from the queue.
        Like a dedicated worker processing mail in the background.
        """
        while True:
            try:
                # Get log entry from queue
                log_entry = await self.processing_queue.get()
                
                # Add to Redis stream for batch processing
                stream_key = f"logs:{log_entry['source']}:stream"
                
                self.redis_client.xadd(
                    stream_key,
                    {
                        'message': log_entry['message'],
                        'metadata': json.dumps(log_entry['metadata']),
                        'ingested_at': log_entry['ingested_at']
                    },
                    maxlen=10000  # Keep last 10k entries per source
                )
                
                # Mark task as done
                self.processing_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in queue worker: {e}")
                await asyncio.sleep(1)  # Brief pause on error
    
    async def start_processing(self):
        """Start the log processing workers"""
        # Start multiple workers for parallel processing
        workers = []
        for i in range(3):  # 3 worker threads
            worker = asyncio.create_task(self.process_queue_worker())
            workers.append(worker)
        
        return workers


class LogAnomalyDetector:
    """
    Detects anomalies in log patterns to identify potential issues.
    Like a smart security system that learns normal patterns and spots unusual activity.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        
        # Store baseline patterns
        self.baseline_patterns = {
            'hourly_log_counts': {},
            'error_rates': {},
            'response_time_patterns': {},
            'endpoint_usage': {}
        }
    
    async def learn_baseline_patterns(self, days: int = 7):
        """
        Learn baseline patterns from historical data.
        Like studying normal behavior to recognize when something's wrong.
        """
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)
            
            # Analyze historical data to establish baselines
            hourly_counts = defaultdict(list)
            error_rates = defaultdict(list)
            
            current_hour = start_time.replace(minute=0, second=0, microsecond=0)
            while current_hour <= end_time:
                hour_key = current_hour.strftime('%Y%m%d%H')
                
                # Get analysis for this hour
                analysis_pattern = f"logs:analysis:{hour_key}*"
                for analysis_key in self.redis_client.scan_iter(match=analysis_pattern):
                    analysis_data = self.redis_client.get(analysis_key)
                    if analysis_data:
                        try:
                            analysis = json.loads(analysis_data)
                            
                            # Track hourly patterns
                            hour_of_day = current_hour.hour
                            day_of_week = current_hour.weekday()
                            
                            hourly_counts[f"{day_of_week}_{hour_of_day}"].append(analysis.get('total_logs', 0))
                            
                            # Track error patterns
                            total_logs = analysis.get('total_logs', 1)
                            errors = analysis.get('by_level', {}).get('ERROR', 0)
                            error_rate = (errors / total_logs) * 100 if total_logs > 0 else 0
                            error_rates[f"{day_of_week}_{hour_of_day}"].append(error_rate)
                            
                        except json.JSONDecodeError:
                            continue
                
                current_hour += timedelta(hours=1)
            
            # Calculate baseline statistics
            for time_key, counts in hourly_counts.items():
                if len(counts) >= 3:  # Need at least 3 data points
                    self.baseline_patterns['hourly_log_counts'][time_key] = {
                        'mean': sum(counts) / len(counts),
                        'std': self._calculate_std(counts),
                        'min': min(counts),
                        'max': max(counts)
                    }
            
            for time_key, rates in error_rates.items():
                if len(rates) >= 3:
                    self.baseline_patterns['error_rates'][time_key] = {
                        'mean': sum(rates) / len(rates),
                        'std': self._calculate_std(rates),
                        'min': min(rates),
                        'max': max(rates)
                    }
            
            # Store baseline patterns
            baseline_key = "logs:baseline_patterns"
            self.redis_client.setex(baseline_key, 604800, json.dumps(self.baseline_patterns))  # 7 days
            
            self.logger.info(f"Learned baseline patterns from {days} days of data")
            
        except Exception as e:
            self.logger.error(f"Error learning baseline patterns: {e}")
    
    def _calculate_std(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5
    
    async def detect_anomalies(self, current_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in current log analysis compared to baseline.
        Like a security guard noticing something unusual.
        """
        anomalies = []
        
        try:
            # Load baseline patterns if not already loaded
            if not self.baseline_patterns['hourly_log_counts']:
                baseline_key = "logs:baseline_patterns"
                baseline_data = self.redis_client.get(baseline_key)
                if baseline_data:
                    self.baseline_patterns = json.loads(baseline_data)
                else:
                    # No baseline available, can't detect anomalies
                    return anomalies
            
            current_time = datetime.utcnow()
            time_key = f"{current_time.weekday()}_{current_time.hour}"
            
            # Check log volume anomaly
            current_log_count = current_analysis.get('total_logs', 0)
            if time_key in self.baseline_patterns['hourly_log_counts']:
                baseline = self.baseline_patterns['hourly_log_counts'][time_key]
                
                # Check if current count is significantly different (>2 standard deviations)
                if abs(current_log_count - baseline['mean']) > 2 * baseline['std']:
                    anomaly_type = 'high_volume' if current_log_count > baseline['mean'] else 'low_volume'
                    
                    anomalies.append({
                        'type': 'log_volume_anomaly',
                        'subtype': anomaly_type,
                        'severity': 'medium',
                        'description': f"Unusual log volume: {current_log_count} (expected: {baseline['mean']:.1f} ± {baseline['std']:.1f})",
                        'current_value': current_log_count,
                        'expected_range': {
                            'min': baseline['mean'] - 2 * baseline['std'],
                            'max': baseline['mean'] + 2 * baseline['std']
                        },
                        'confidence': 'high' if abs(current_log_count - baseline['mean']) > 3 * baseline['std'] else 'medium'
                    })
            
            # Check error rate anomaly
            total_logs = current_analysis.get('total_logs', 1)
            current_errors = current_analysis.get('by_level', {}).get('ERROR', 0)
            current_error_rate = (current_errors / total_logs) * 100 if total_logs > 0 else 0
            
            if time_key in self.baseline_patterns['error_rates']:
                baseline = self.baseline_patterns['error_rates'][time_key]
                
                if current_error_rate > baseline['mean'] + 2 * baseline['std']:
                    anomalies.append({
                        'type': 'error_rate_anomaly',
                        'subtype': 'high_error_rate',
                        'severity': 'high',
                        'description': f"Unusual error rate: {current_error_rate:.2f}% (expected: {baseline['mean']:.2f}% ± {baseline['std']:.2f}%)",
                        'current_value': current_error_rate,
                        'expected_range': {
                            'min': max(0, baseline['mean'] - 2 * baseline['std']),
                            'max': baseline['mean'] + 2 * baseline['std']
                        },
                        'confidence': 'high'
                    })
            
            # Check for unusual error patterns
            error_patterns = current_analysis.get('error_patterns', {})
            for pattern, count in error_patterns.items():
                if count > 10:  # More than 10 of the same error pattern
                    anomalies.append({
                        'type': 'error_pattern_anomaly',
                        'subtype': pattern,
                        'severity': 'medium',
                        'description': f"High frequency of {pattern} errors: {count} occurrences",
                        'current_value': count,
                        'confidence': 'medium'
                    })
            
            return anomalies
            
        except Exception as e:
            self.logger.error(f"Error detecting anomalies: {e}")
            return []


# Export main classes
__all__ = [
    'LogCollector',
    'LogStreamProcessor', 
    'LogAnomalyDetector'
]