import asyncio
import json
import logging
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import redis
import aiohttp
import psutil
from collections import defaultdict, deque

class PerformanceCollector:
    """
    Performance Collector - like a sports statistician tracking every play in real-time.
    
    This continuously monitors and collects performance data to ensure you maintain:
    - <100ms average response time (your SLA target)
    - 99.9% uptime
    - 1,000+ concurrent requests/second capability
    
    Think of this as your platform's fitness tracker that never stops measuring
    how well your system is performing.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        
        # Performance data buffer for batch processing
        self.performance_buffer = deque(maxlen=1000)
        self.last_flush = datetime.utcnow()
        
        # Service endpoints to monitor
        self.service_endpoints = {
            'django': {
                'health_url': 'http://django-service:8000/health/',
                'metrics_url': 'http://django-service:8000/metrics/',
                'timeout': 5
            },
            'fastapi': {
                'health_url': 'http://fastapi-service:8001/health',
                'metrics_url': 'http://fastapi-service:8001/metrics',
                'timeout': 5
            },
            'monitoring': {
                'health_url': 'http://localhost:8003/health',
                'metrics_url': 'http://localhost:8003/metrics',
                'timeout': 3
            }
        }
        
        # Performance thresholds for alerting
        self.thresholds = {
            'response_time_warning': 100,    # Your SLA target
            'response_time_critical': 500,   # Critical threshold
            'error_rate_warning': 1.0,       # 1% error rate
            'error_rate_critical': 5.0,      # 5% error rate
            'cpu_warning': 80,               # 80% CPU usage
            'cpu_critical': 90,              # 90% CPU usage
            'memory_warning': 85,            # 85% memory usage
            'memory_critical': 95            # 95% memory usage
        }
        
        # Moving averages for trend detection
        self.moving_averages = {
            'response_time': deque(maxlen=100),  # Last 100 measurements
            'error_rate': deque(maxlen=100),
            'throughput': deque(maxlen=100)
        }
    
    async def collect_performance_data(self) -> Dict[str, Any]:
        """
        Collect comprehensive performance data from all sources.
        Like taking vital signs during a medical checkup.
        """
        try:
            collection_start = time.time()
            
            performance_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'collection_duration_ms': 0,
                'services': {},
                'system': {},
                'aggregated_metrics': {}
            }
            
            # Collect from all services concurrently
            service_tasks = []
            for service_name, config in self.service_endpoints.items():
                task = asyncio.create_task(
                    self._collect_service_performance(service_name, config)
                )
                service_tasks.append((service_name, task))
            
            # Collect system performance
            system_task = asyncio.create_task(self._collect_system_performance())
            
            # Wait for all collections to complete
            for service_name, task in service_tasks:
                try:
                    service_data = await task
                    performance_data['services'][service_name] = service_data
                except Exception as e:
                    self.logger.error(f"Error collecting performance from {service_name}: {e}")
                    performance_data['services'][service_name] = {
                        'status': 'error',
                        'error': str(e)
                    }
            
            # Get system performance
            try:
                performance_data['system'] = await system_task
            except Exception as e:
                self.logger.error(f"Error collecting system performance: {e}")
                performance_data['system'] = {'error': str(e)}
            
            # Calculate aggregated metrics
            performance_data['aggregated_metrics'] = await self._calculate_aggregated_metrics(
                performance_data['services']
            )
            
            # Record collection duration
            performance_data['collection_duration_ms'] = (time.time() - collection_start) * 1000
            
            # Add to buffer for batch processing
            self.performance_buffer.append(performance_data)
            
            # Update moving averages
            await self._update_moving_averages(performance_data)
            
            # Flush buffer if needed
            if len(self.performance_buffer) >= 50 or (datetime.utcnow() - self.last_flush).seconds >= 60:
                await self._flush_performance_buffer()
            
            # Store latest performance data
            await self._store_latest_performance(performance_data)
            
            return performance_data
            
        except Exception as e:
            self.logger.error(f"Error collecting performance data: {e}")
            return {'error': str(e), 'timestamp': datetime.utcnow().isoformat()}
    
    async def _collect_service_performance(self, service_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect performance data from a specific service.
        Like checking the pulse and temperature of one patient.
        """
        service_data = {
            'name': service_name,
            'status': 'unknown',
            'response_time_ms': 0,
            'health_check': {},
            'metrics': {},
            'availability': False
        }
        
        try:
            # Health check with timing
            health_start = time.time()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=config['timeout'])) as session:
                try:
                    async with session.get(config['health_url']) as response:
                        health_response_time = (time.time() - health_start) * 1000
                        service_data['response_time_ms'] = health_response_time
                        
                        if response.status == 200:
                            service_data['status'] = 'healthy'
                            service_data['availability'] = True
                            
                            try:
                                health_data = await response.json()
                                service_data['health_check'] = health_data
                            except:
                                service_data['health_check'] = {'status': 'ok'}
                        else:
                            service_data['status'] = 'unhealthy'
                            service_data['health_check'] = {
                                'status': 'error',
                                'http_status': response.status
                            }
                
                except asyncio.TimeoutError:
                    service_data['status'] = 'timeout'
                    service_data['response_time_ms'] = config['timeout'] * 1000
                    service_data['health_check'] = {'status': 'timeout'}
                except aiohttp.ClientError as e:
                    service_data['status'] = 'connection_error'
                    service_data['health_check'] = {'status': 'connection_error', 'error': str(e)}
                
                # Collect metrics if service is healthy
                if service_data['status'] == 'healthy' and 'metrics_url' in config:
                    try:
                        metrics_start = time.time()
                        async with session.get(config['metrics_url']) as metrics_response:
                            metrics_response_time = (time.time() - metrics_start) * 1000
                            
                            if metrics_response.status == 200:
                                try:
                                    metrics_data = await metrics_response.json()
                                    service_data['metrics'] = metrics_data
                                    service_data['metrics']['collection_time_ms'] = metrics_response_time
                                except:
                                    service_data['metrics'] = {'status': 'parse_error'}
                            else:
                                service_data['metrics'] = {'status': 'unavailable'}
                    
                    except Exception as e:
                        service_data['metrics'] = {'status': 'error', 'error': str(e)}
            
        except Exception as e:
            service_data['status'] = 'error'
            service_data['health_check'] = {'status': 'error', 'error': str(e)}
        
        return service_data
    
    async def _collect_system_performance(self) -> Dict[str, Any]:
        """
        Collect system-level performance metrics.
        Like checking the vital signs of the server itself.
        """
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)  # Short interval for responsiveness
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Network metrics
            network = psutil.net_io_counters()
            
            # Process metrics
            process_count = len(psutil.pids())
            
            # Calculate performance scores
            cpu_score = max(0, 100 - cpu_percent)
            memory_score = max(0, 100 - memory.percent)
            disk_score = max(0, 100 - disk.percent)
            
            overall_score = (cpu_score + memory_score + disk_score) / 3
            
            return {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'load_avg_1m': load_avg[0],
                    'load_avg_5m': load_avg[1],
                    'load_avg_15m': load_avg[2],
                    'score': cpu_score
                },
                'memory': {
                    'total_gb': round(memory.total / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2),
                    'used_gb': round(memory.used / (1024**3), 2),
                    'percent': memory.percent,
                    'score': memory_score
                },
                'swap': {
                    'total_gb': round(swap.total / (1024**3), 2),
                    'used_gb': round(swap.used / (1024**3), 2),
                    'percent': swap.percent
                },
                'disk': {
                    'total_gb': round(disk.total / (1024**3), 2),
                    'used_gb': round(disk.used / (1024**3), 2),
                    'free_gb': round(disk.free / (1024**3), 2),
                    'percent': disk.percent,
                    'score': disk_score
                },
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                },
                'processes': {
                    'count': process_count
                },
                'overall_score': round(overall_score, 1)
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting system performance: {e}")
            return {'error': str(e)}
    
    async def _calculate_aggregated_metrics(self, services_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate aggregated metrics across all services.
        Like calculating team statistics from individual player stats.
        """
        try:
            aggregated = {
                'service_count': len(services_data),
                'healthy_services': 0,
                'avg_response_time_ms': 0,
                'max_response_time_ms': 0,
                'min_response_time_ms': float('inf'),
                'availability_percent': 0,
                'error_count': 0,
                'total_requests': 0,
                'sla_compliance': True,  # Your <100ms target
                'performance_grade': 'A'
            }
            
            response_times = []
            available_services = 0
            
            for service_name, service_data in services_data.items():
                if isinstance(service_data, dict) and 'status' in service_data:
                    # Count healthy services
                    if service_data['status'] == 'healthy':
                        aggregated['healthy_services'] += 1
                        available_services += 1
                    
                    # Collect response times
                    response_time = service_data.get('response_time_ms', 0)
                    if response_time > 0:
                        response_times.append(response_time)
                        
                        # Check SLA compliance (your <100ms target)
                        if response_time > 100:
                            aggregated['sla_compliance'] = False
                    
                    # Count errors
                    if service_data['status'] in ['error', 'timeout', 'unhealthy']:
                        aggregated['error_count'] += 1
                    
                    # Extract request counts from metrics if available
                    metrics = service_data.get('metrics', {})
                    if isinstance(metrics, dict):
                        requests = metrics.get('total_requests', 0)
                        if isinstance(requests, (int, float)):
                            aggregated['total_requests'] += requests
            
            # Calculate response time statistics
            if response_times:
                aggregated['avg_response_time_ms'] = round(statistics.mean(response_times), 2)
                aggregated['max_response_time_ms'] = max(response_times)
                aggregated['min_response_time_ms'] = min(response_times)
                
                # Calculate performance grade
                avg_rt = aggregated['avg_response_time_ms']
                if avg_rt < 50:
                    aggregated['performance_grade'] = 'A+'
                elif avg_rt < 100:  # Your SLA target
                    aggregated['performance_grade'] = 'A'
                elif avg_rt < 200:
                    aggregated['performance_grade'] = 'B'
                elif avg_rt < 500:
                    aggregated['performance_grade'] = 'C'
                else:
                    aggregated['performance_grade'] = 'F'
            else:
                aggregated['min_response_time_ms'] = 0
            
            # Calculate availability percentage
            if aggregated['service_count'] > 0:
                aggregated['availability_percent'] = round(
                    (available_services / aggregated['service_count']) * 100, 2
                )
            
            # Calculate error rate
            if aggregated['service_count'] > 0:
                aggregated['error_rate_percent'] = round(
                    (aggregated['error_count'] / aggregated['service_count']) * 100, 2
                )
            else:
                aggregated['error_rate_percent'] = 0
            
            return aggregated
            
        except Exception as e:
            self.logger.error(f"Error calculating aggregated metrics: {e}")
            return {'error': str(e)}
    
    async def _update_moving_averages(self, performance_data: Dict[str, Any]):
        """
        Update moving averages for trend detection.
        Like keeping a running score to see if performance is improving or declining.
        """
        try:
            aggregated = performance_data.get('aggregated_metrics', {})
            
            # Update response time moving average
            avg_response_time = aggregated.get('avg_response_time_ms', 0)
            if avg_response_time > 0:
                self.moving_averages['response_time'].append(avg_response_time)
            
            # Update error rate moving average
            error_rate = aggregated.get('error_rate_percent', 0)
            self.moving_averages['error_rate'].append(error_rate)
            
            # Update throughput moving average (requests per minute)
            total_requests = aggregated.get('total_requests', 0)
            self.moving_averages['throughput'].append(total_requests)
            
        except Exception as e:
            self.logger.error(f"Error updating moving averages: {e}")
    
    async def _flush_performance_buffer(self):
        """
        Flush buffered performance data to storage.
        Like emptying your measurement clipboard and filing the data.
        """
        try:
            if not self.performance_buffer:
                return
            
            buffer_copy = list(self.performance_buffer)
            self.performance_buffer.clear()
            self.last_flush = datetime.utcnow()
            
            # Store in time-series format
            await self._store_time_series_data(buffer_copy)
            
            # Calculate and store aggregated statistics
            await self._calculate_period_statistics(buffer_copy)
            
            # Check for performance alerts
            await self._check_performance_alerts(buffer_copy)
            
            self.logger.debug(f"Flushed {len(buffer_copy)} performance data points")
            
        except Exception as e:
            self.logger.error(f"Error flushing performance buffer: {e}")
    
    async def _store_time_series_data(self, performance_data: List[Dict[str, Any]]):
        """
        Store performance data in time-series format for analysis.
        Like creating a detailed timeline of your platform's performance.
        """
        try:
            current_minute = datetime.utcnow().strftime('%Y%m%d%H%M')
            
            # Aggregate data for this minute
            minute_aggregation = {
                'timestamp': datetime.utcnow().isoformat(),
                'data_points': len(performance_data),
                'services': defaultdict(list),
                'system_metrics': [],
                'response_times': [],
                'error_rates': [],
                'availability_checks': []
            }
            
            # Process each data point
            for data_point in performance_data:
                # Collect service data
                for service_name, service_data in data_point.get('services', {}).items():
                    if isinstance(service_data, dict):
                        minute_aggregation['services'][service_name].append({
                            'timestamp': data_point['timestamp'],
                            'status': service_data.get('status', 'unknown'),
                            'response_time_ms': service_data.get('response_time_ms', 0),
                            'availability': service_data.get('availability', False)
                        })
                
                # Collect system metrics
                system_data = data_point.get('system', {})
                if isinstance(system_data, dict) and 'cpu' in system_data:
                    minute_aggregation['system_metrics'].append({
                        'timestamp': data_point['timestamp'],
                        'cpu_percent': system_data['cpu'].get('percent', 0),
                        'memory_percent': system_data['memory'].get('percent', 0),
                        'disk_percent': system_data['disk'].get('percent', 0),
                        'overall_score': system_data.get('overall_score', 0)
                    })
                
                # Collect aggregated metrics
                aggregated = data_point.get('aggregated_metrics', {})
                if isinstance(aggregated, dict):
                    avg_rt = aggregated.get('avg_response_time_ms', 0)
                    if avg_rt > 0:
                        minute_aggregation['response_times'].append(avg_rt)
                    
                    error_rate = aggregated.get('error_rate_percent', 0)
                    minute_aggregation['error_rates'].append(error_rate)
                    
                    availability = aggregated.get('availability_percent', 0)
                    minute_aggregation['availability_checks'].append(availability)
            
            # Store minute aggregation
            minute_key = f"performance:minute:{current_minute}"
            self.redis_client.setex(minute_key, 3600, json.dumps(minute_aggregation))  # 1 hour
            
            # Store in hourly aggregation
            await self._update_hourly_aggregation(current_minute, minute_aggregation)
            
        except Exception as e:
            self.logger.error(f"Error storing time series data: {e}")
    
    async def _update_hourly_aggregation(self, minute_key: str, minute_data: Dict[str, Any]):
        """
        Update hourly aggregated data.
        Like summarizing the day's performance into hourly reports.
        """
        try:
            hour_key = minute_key[:10]  # YYYYMMDDHH
            hourly_key = f"performance:hourly:{hour_key}"
            
            # Get existing hourly data
            hourly_data = self.redis_client.get(hourly_key)
            if hourly_data:
                hourly_stats = json.loads(hourly_data)
            else:
                hourly_stats = {
                    'hour': hour_key,
                    'start_time': datetime.strptime(hour_key, '%Y%m%d%H').isoformat(),
                    'data_points': 0,
                    'minutes_recorded': 0,
                    'avg_response_time_ms': 0,
                    'max_response_time_ms': 0,
                    'min_response_time_ms': float('inf'),
                    'avg_error_rate_percent': 0,
                    'avg_availability_percent': 0,
                    'sla_violations': 0,
                    'total_requests': 0,
                    'service_stats': {},
                    'system_stats': {
                        'avg_cpu_percent': 0,
                        'avg_memory_percent': 0,
                        'avg_disk_percent': 0
                    }
                }
            
            # Update with minute data
            hourly_stats['data_points'] += minute_data['data_points']
            hourly_stats['minutes_recorded'] += 1
            
            # Process response times
            response_times = minute_data.get('response_times', [])
            if response_times:
                avg_rt = sum(response_times) / len(response_times)
                max_rt = max(response_times)
                min_rt = min(response_times)
                
                # Update hourly averages
                current_avg = hourly_stats['avg_response_time_ms']
                minutes_count = hourly_stats['minutes_recorded']
                hourly_stats['avg_response_time_ms'] = ((current_avg * (minutes_count - 1)) + avg_rt) / minutes_count
                
                hourly_stats['max_response_time_ms'] = max(hourly_stats['max_response_time_ms'], max_rt)
                if hourly_stats['min_response_time_ms'] == float('inf'):
                    hourly_stats['min_response_time_ms'] = min_rt
                else:
                    hourly_stats['min_response_time_ms'] = min(hourly_stats['min_response_time_ms'], min_rt)
                
                # Count SLA violations (your <100ms target)
                sla_violations = sum(1 for rt in response_times if rt > 100)
                hourly_stats['sla_violations'] += sla_violations
            
            # Process error rates
            error_rates = minute_data.get('error_rates', [])
            if error_rates:
                avg_error_rate = sum(error_rates) / len(error_rates)
                current_error_avg = hourly_stats['avg_error_rate_percent']
                minutes_count = hourly_stats['minutes_recorded']
                hourly_stats['avg_error_rate_percent'] = ((current_error_avg * (minutes_count - 1)) + avg_error_rate) / minutes_count
            
            # Process availability
            availability_checks = minute_data.get('availability_checks', [])
            if availability_checks:
                avg_availability = sum(availability_checks) / len(availability_checks)
                current_avail_avg = hourly_stats['avg_availability_percent']
                minutes_count = hourly_stats['minutes_recorded']
                hourly_stats['avg_availability_percent'] = ((current_avail_avg * (minutes_count - 1)) + avg_availability) / minutes_count
            
            # Process system metrics
            system_metrics = minute_data.get('system_metrics', [])
            if system_metrics:
                avg_cpu = sum(m['cpu_percent'] for m in system_metrics) / len(system_metrics)
                avg_memory = sum(m['memory_percent'] for m in system_metrics) / len(system_metrics)
                avg_disk = sum(m['disk_percent'] for m in system_metrics) / len(system_metrics)
                
                sys_stats = hourly_stats['system_stats']
                minutes_count = hourly_stats['minutes_recorded']
                
                sys_stats['avg_cpu_percent'] = ((sys_stats['avg_cpu_percent'] * (minutes_count - 1)) + avg_cpu) / minutes_count
                sys_stats['avg_memory_percent'] = ((sys_stats['avg_memory_percent'] * (minutes_count - 1)) + avg_memory) / minutes_count
                sys_stats['avg_disk_percent'] = ((sys_stats['avg_disk_percent'] * (minutes_count - 1)) + avg_disk) / minutes_count
            
            # Store updated hourly stats
            self.redis_client.setex(hourly_key, 86400, json.dumps(hourly_stats))  # 24 hours
            
        except Exception as e:
            self.logger.error(f"Error updating hourly aggregation: {e}")
    
    async def _calculate_period_statistics(self, performance_data: List[Dict[str, Any]]):
        """
        Calculate statistics for the flush period.
        Like creating a summary report card for this time period.
        """
        try:
            if not performance_data:
                return
            
            period_stats = {
                'period_start': performance_data[0]['timestamp'],
                'period_end': performance_data[-1]['timestamp'],
                'data_points': len(performance_data),
                'summary': {
                    'avg_response_time_ms': 0,
                    'max_response_time_ms': 0,
                    'min_response_time_ms': float('inf'),
                    'sla_compliance_percent': 0,
                    'availability_percent': 0,
                    'error_rate_percent': 0,
                    'performance_grade': 'F'
                },
                'service_breakdown': {},
                'trends': {}
            }
            
            # Collect all metrics
            all_response_times = []
            all_error_rates = []
            all_availability = []
            service_stats = defaultdict(lambda: {'response_times': [], 'statuses': []})
            
            for data_point in performance_data:
                aggregated = data_point.get('aggregated_metrics', {})
                
                # Collect response times
                avg_rt = aggregated.get('avg_response_time_ms', 0)
                if avg_rt > 0:
                    all_response_times.append(avg_rt)
                
                # Collect error rates
                error_rate = aggregated.get('error_rate_percent', 0)
                all_error_rates.append(error_rate)
                
                # Collect availability
                availability = aggregated.get('availability_percent', 0)
                all_availability.append(availability)
                
                # Collect service-specific data
                for service_name, service_data in data_point.get('services', {}).items():
                    if isinstance(service_data, dict):
                        rt = service_data.get('response_time_ms', 0)
                        if rt > 0:
                            service_stats[service_name]['response_times'].append(rt)
                        service_stats[service_name]['statuses'].append(service_data.get('status', 'unknown'))
            
            # Calculate summary statistics
            if all_response_times:
                period_stats['summary']['avg_response_time_ms'] = round(statistics.mean(all_response_times), 2)
                period_stats['summary']['max_response_time_ms'] = max(all_response_times)
                period_stats['summary']['min_response_time_ms'] = min(all_response_times)
                
                # SLA compliance (your <100ms target)
                compliant_requests = sum(1 for rt in all_response_times if rt < 100)
                period_stats['summary']['sla_compliance_percent'] = round(
                    (compliant_requests / len(all_response_times)) * 100, 2
                )
                
                # Performance grade
                avg_rt = period_stats['summary']['avg_response_time_ms']
                if avg_rt < 50:
                    period_stats['summary']['performance_grade'] = 'A+'
                elif avg_rt < 100:
                    period_stats['summary']['performance_grade'] = 'A'
                elif avg_rt < 200:
                    period_stats['summary']['performance_grade'] = 'B'
                elif avg_rt < 500:
                    period_stats['summary']['performance_grade'] = 'C'
                else:
                    period_stats['summary']['performance_grade'] = 'F'
            else:
                period_stats['summary']['min_response_time_ms'] = 0
            
            if all_error_rates:
                period_stats['summary']['error_rate_percent'] = round(statistics.mean(all_error_rates), 2)
            
            if all_availability:
                period_stats['summary']['availability_percent'] = round(statistics.mean(all_availability), 2)
            
            # Calculate service breakdown
            for service_name, stats in service_stats.items():
                if stats['response_times']:
                    service_breakdown = {
                        'avg_response_time_ms': round(statistics.mean(stats['response_times']), 2),
                        'max_response_time_ms': max(stats['response_times']),
                        'min_response_time_ms': min(stats['response_times']),
                        'data_points': len(stats['response_times'])
                    }
                    
                    # Calculate availability for this service
                    healthy_count = sum(1 for status in stats['statuses'] if status == 'healthy')
                    service_breakdown['availability_percent'] = round(
                        (healthy_count / len(stats['statuses'])) * 100, 2
                    )
                    
                    period_stats['service_breakdown'][service_name] = service_breakdown
            
            # Calculate trends using moving averages
            period_stats['trends'] = await self._calculate_trends()
            
            # Store period statistics
            period_key = f"performance:period:{int(datetime.utcnow().timestamp())}"
            self.redis_client.setex(period_key, 7200, json.dumps(period_stats))  # 2 hours
            
        except Exception as e:
            self.logger.error(f"Error calculating period statistics: {e}")
    
    async def _calculate_trends(self) -> Dict[str, Any]:
        """
        Calculate performance trends from moving averages.
        Like analyzing whether your team's performance is improving or declining.
        """
        try:
            trends = {}
            
            # Response time trend
            if len(self.moving_averages['response_time']) >= 10:
                rt_values = list(self.moving_averages['response_time'])
                recent_avg = statistics.mean(rt_values[-10:])  # Last 10 measurements
                older_avg = statistics.mean(rt_values[-20:-10]) if len(rt_values) >= 20 else recent_avg
                
                trend_direction = 'stable'
                if recent_avg > older_avg * 1.1:  # 10% increase
                    trend_direction = 'worsening'
                elif recent_avg < older_avg * 0.9:  # 10% decrease
                    trend_direction = 'improving'
                
                trends['response_time'] = {
                    'direction': trend_direction,
                    'recent_avg': round(recent_avg, 2),
                    'older_avg': round(older_avg, 2),
                    'change_percent': round(((recent_avg - older_avg) / older_avg) * 100, 2) if older_avg > 0 else 0
                }
            
            # Error rate trend
            if len(self.moving_averages['error_rate']) >= 10:
                er_values = list(self.moving_averages['error_rate'])
                recent_avg = statistics.mean(er_values[-10:])
                older_avg = statistics.mean(er_values[-20:-10]) if len(er_values) >= 20 else recent_avg
                
                trend_direction = 'stable'
                if recent_avg > older_avg * 1.2:  # 20% increase in errors
                    trend_direction = 'worsening'
                elif recent_avg < older_avg * 0.8:  # 20% decrease in errors
                    trend_direction = 'improving'
                
                trends['error_rate'] = {
                    'direction': trend_direction,
                    'recent_avg': round(recent_avg, 2),
                    'older_avg': round(older_avg, 2),
                    'change_percent': round(((recent_avg - older_avg) / older_avg) * 100, 2) if older_avg > 0 else 0
                }
            
            return trends
            
        except Exception as e:
            self.logger.error(f"Error calculating trends: {e}")
            return {}
    
    async def _check_performance_alerts(self, performance_data: List[Dict[str, Any]]):
        """
        Check for performance conditions that should trigger alerts.
        Like a coach spotting when a player needs attention.
        """
        try:
            # Analyze recent performance data
            recent_response_times = []
            recent_error_rates = []
            recent_availability = []
            
            for data_point in performance_data:
                aggregated = data_point.get('aggregated_metrics', {})
                
                rt = aggregated.get('avg_response_time_ms', 0)
                if rt > 0:
                    recent_response_times.append(rt)
                
                er = aggregated.get('error_rate_percent', 0)
                recent_error_rates.append(er)
                
                av = aggregated.get('availability_percent', 0)
                recent_availability.append(av)
            
            # Check response time alerts
            if recent_response_times:
                avg_rt = statistics.mean(recent_response_times)
                max_rt = max(recent_response_times)
                
                # SLA violation alert (your <100ms target)
                if avg_rt > self.thresholds['response_time_warning']:
                    severity = 'critical' if avg_rt > self.thresholds['response_time_critical'] else 'warning'
                    
                    alert = {
                        'type': 'performance_alert',
                        'category': 'response_time',
                        'severity': severity,
                        'message': f'Average response time: {avg_rt:.1f}ms (SLA: <100ms)',
                        'details': {
                            'avg_response_time_ms': avg_rt,
                            'max_response_time_ms': max_rt,
                            'threshold_warning': self.thresholds['response_time_warning'],
                            'threshold_critical': self.thresholds['response_time_critical'],
                            'data_points': len(recent_response_times)
                        }
                    }
                    
                    # Store alert
                    alert_key = f"alerts:performance:response_time:{int(datetime.utcnow().timestamp())}"
                    self.redis_client.setex(alert_key, 3600, json.dumps(alert))
            
            # Check error rate alerts
            if recent_error_rates:
                avg_er = statistics.mean(recent_error_rates)
                
                if avg_er > self.thresholds['error_rate_warning']:
                    severity = 'critical' if avg_er > self.thresholds['error_rate_critical'] else 'warning'
                    
                    alert = {
                        'type': 'performance_alert',
                        'category': 'error_rate',
                        'severity': severity,
                        'message': f'High error rate: {avg_er:.1f}% (threshold: {self.thresholds["error_rate_warning"]}%)',
                        'details': {
                            'avg_error_rate_percent': avg_er,
                            'threshold_warning': self.thresholds['error_rate_warning'],
                            'threshold_critical': self.thresholds['error_rate_critical'],
                            'data_points': len(recent_error_rates)
                        }
                    }
                    
                    # Store alert
                    alert_key = f"alerts:performance:error_rate:{int(datetime.utcnow().timestamp())}"
                    self.redis_client.setex(alert_key, 3600, json.dumps(alert))
            
            # Check availability alerts
            if recent_availability:
                avg_av = statistics.mean(recent_availability)
                
                if avg_av < 99.0:  # Below 99% availability
                    severity = 'critical' if avg_av < 95.0 else 'warning'
                    
                    alert = {
                        'type': 'performance_alert',
                        'category': 'availability',
                        'severity': severity,
                        'message': f'Low availability: {avg_av:.1f}% (target: >99%)',
                        'details': {
                            'avg_availability_percent': avg_av,
                            'target': 99.0,
                            'data_points': len(recent_availability)
                        }
                    }
                    
                    # Store alert
                    alert_key = f"alerts:performance:availability:{int(datetime.utcnow().timestamp())}"
                    self.redis_client.setex(alert_key, 3600, json.dumps(alert))
            
        except Exception as e:
            self.logger.error(f"Error checking performance alerts: {e}")
    
    async def _store_latest_performance(self, performance_data: Dict[str, Any]):
        """Store the latest performance snapshot for quick access"""
        try:
            latest_key = "performance:latest"
            
            # Create simplified snapshot
            snapshot = {
                'timestamp': performance_data['timestamp'],
                'collection_duration_ms': performance_data.get('collection_duration_ms', 0),
                'summary': performance_data.get('aggregated_metrics', {}),
                'service_count': len(performance_data.get('services', {})),
                'healthy_services': performance_data.get('aggregated_metrics', {}).get('healthy_services', 0),
                'trends': await self._calculate_trends()
            }
            
            self.redis_client.setex(latest_key, 300, json.dumps(snapshot))  # 5 minutes
            
        except Exception as e:
            self.logger.error(f"Error storing latest performance: {e}")
    
    async def get_performance_window(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """
        Get performance data for a specific time window.
        Like reviewing the last hour of game footage.
        """
        try:
            performance_window = []
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=minutes)
            
            # Get minute-level data
            current_minute = start_time.replace(second=0, microsecond=0)
            while current_minute <= end_time:
                minute_key = f"performance:minute:{current_minute.strftime('%Y%m%d%H%M')}"
                minute_data = self.redis_client.get(minute_key)
                
                if minute_data:
                    try:
                        data = json.loads(minute_data)
                        
                        # Create summary for this minute
                        minute_summary = {
                            'timestamp': current_minute.isoformat(),
                            'data_points': data.get('data_points', 0),
                            'avg_response_time_ms': 0,
                            'error_rate_percent': 0,
                            'availability_percent': 0,
                            'services': {}
                        }
                        
                        # Calculate averages for this minute
                        response_times = data.get('response_times', [])
                        if response_times:
                            minute_summary['avg_response_time_ms'] = round(
                                sum(response_times) / len(response_times), 2
                            )
                        
                        error_rates = data.get('error_rates', [])
                        if error_rates:
                            minute_summary['error_rate_percent'] = round(
                                sum(error_rates) / len(error_rates), 2
                            )
                        
                        availability_checks = data.get('availability_checks', [])
                        if availability_checks:
                            minute_summary['availability_percent'] = round(
                                sum(availability_checks) / len(availability_checks), 2
                            )
                        
                        # Add service summaries
                        for service_name, service_data_list in data.get('services', {}).items():
                            if service_data_list:
                                service_rts = [s.get('response_time_ms', 0) for s in service_data_list if s.get('response_time_ms', 0) > 0]
                                service_availability = [s.get('availability', False) for s in service_data_list]
                                
                                minute_summary['services'][service_name] = {
                                    'avg_response_time_ms': round(sum(service_rts) / len(service_rts), 2) if service_rts else 0,
                                    'availability_percent': round((sum(service_availability) / len(service_availability)) * 100, 2) if service_availability else 0,
                                    'data_points': len(service_data_list)
                                }
                        
                        performance_window.append(minute_summary)
                        
                    except json.JSONDecodeError:
                        continue
                
                current_minute += timedelta(minutes=1)
            
            return performance_window
            
        except Exception as e:
            self.logger.error(f"Error getting performance window: {e}")
            return []
    
    async def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get performance summary for dashboard display.
        Like getting the highlight reel of your platform's performance.
        """
        try:
            # Get latest snapshot
            latest_key = "performance:latest"
            latest_data = self.redis_client.get(latest_key)
            
            if latest_data:
                latest_snapshot = json.loads(latest_data)
            else:
                latest_snapshot = {}
            
            # Get recent performance window
            recent_data = await self.get_performance_window(60)  # Last hour
            
            # Calculate summary metrics
            if recent_data:
                response_times = [d['avg_response_time_ms'] for d in recent_data if d['avg_response_time_ms'] > 0]
                error_rates = [d['error_rate_percent'] for d in recent_data]
                availability_checks = [d['availability_percent'] for d in recent_data if d['availability_percent'] > 0]
                
                summary = {
                    'current_performance': latest_snapshot.get('summary', {}),
                    'recent_hour': {
                        'avg_response_time_ms': round(statistics.mean(response_times), 2) if response_times else 0,
                        'max_response_time_ms': max(response_times) if response_times else 0,
                        'avg_error_rate_percent': round(statistics.mean(error_rates), 2) if error_rates else 0,
                        'avg_availability_percent': round(statistics.mean(availability_checks), 2) if availability_checks else 100,
                        'data_points': len(recent_data)
                    },
                    'sla_compliance': {
                        'target_response_time_ms': 100,  # Your SLA target
                        'compliant_requests_percent': round((sum(1 for rt in response_times if rt < 100) / len(response_times)) * 100, 2) if response_times else 100,
                        'target_availability_percent': 99.9,
                        'current_availability': round(statistics.mean(availability_checks), 2) if availability_checks else 100
                    },
                    'health_status': 'excellent' if (
                        (not response_times or statistics.mean(response_times) < 100) and
                        (not error_rates or statistics.mean(error_rates) < 1.0) and
                        (not availability_checks or statistics.mean(availability_checks) > 99.0)
                    ) else 'good' if (
                        (not response_times or statistics.mean(response_times) < 200) and
                        (not error_rates or statistics.mean(error_rates) < 2.0)
                    ) else 'poor',
                    'trends': latest_snapshot.get('trends', {}),
                    'last_updated': latest_snapshot.get('timestamp', datetime.utcnow().isoformat())
                }
            else:
                summary = {
                    'current_performance': latest_snapshot.get('summary', {}),
                    'recent_hour': {},
                    'sla_compliance': {},
                    'health_status': 'unknown',
                    'trends': {},
                    'last_updated': latest_snapshot.get('timestamp', datetime.utcnow().isoformat())
                }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting performance summary: {e}")
            return {'error': str(e)}


# Export main class
__all__ = ['PerformanceCollector']