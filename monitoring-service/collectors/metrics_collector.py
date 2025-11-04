import asyncio
import psutil
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import redis
import aiohttp
import socket

class MetricsCollector:
    """
    Metrics collector - like a data logger in a factory that records everything.
    This continuously gathers system metrics to feed your analytics dashboard.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        self.hostname = socket.gethostname()
        
        # Configuration for different metric types
        self.metric_config = {
            'system_metrics_interval': 30,  # seconds
            'app_metrics_interval': 10,     # seconds
            'retention_days': 7,            # how long to keep metrics
        }
    
    async def collect_system_metrics(self) -> Dict[str, Any]:
        """
        Collect system-level metrics - like checking vital signs.
        Essential for maintaining your infrastructure supporting 1,000+ concurrent users.
        """
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Network metrics
            network_io = psutil.net_io_counters()
            
            # Process metrics
            process_count = len(psutil.pids())
            
            metrics = {
                'timestamp': datetime.utcnow().isoformat(),
                'hostname': self.hostname,
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'load_avg_1m': load_avg[0],
                    'load_avg_5m': load_avg[1],
                    'load_avg_15m': load_avg[2],
                },
                'memory': {
                    'total_bytes': memory.total,
                    'available_bytes': memory.available,
                    'used_bytes': memory.used,
                    'percent': memory.percent,
                    'free_bytes': memory.free,
                },
                'swap': {
                    'total_bytes': swap.total,
                    'used_bytes': swap.used,
                    'free_bytes': swap.free,
                    'percent': swap.percent,
                },
                'disk': {
                    'total_bytes': disk.total,
                    'used_bytes': disk.used,
                    'free_bytes': disk.free,
                    'percent': disk.percent,
                    'read_bytes': disk_io.read_bytes if disk_io else 0,
                    'write_bytes': disk_io.write_bytes if disk_io else 0,
                    'read_count': disk_io.read_count if disk_io else 0,
                    'write_count': disk_io.write_count if disk_io else 0,
                },
                'network': {
                    'bytes_sent': network_io.bytes_sent,
                    'bytes_recv': network_io.bytes_recv,
                    'packets_sent': network_io.packets_sent,
                    'packets_recv': network_io.packets_recv,
                },
                'processes': {
                    'count': process_count,
                }
            }
            
            # Store in Redis with expiration
            await self._store_metric('system_metrics', metrics)
            
            # Check for alerts (high CPU, memory, etc.)
            await self._check_system_alerts(metrics)
            
            self.logger.debug(f"Collected system metrics: CPU {cpu_percent}%, Memory {memory.percent}%")
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            return {}
    
    async def collect_application_metrics(self) -> Dict[str, Any]:
        """
        Collect application-specific metrics - like counting customers and sales.
        Tracks your API performance and business metrics.
        """
        try:
            metrics = {
                'timestamp': datetime.utcnow().isoformat(),
                'hostname': self.hostname,
                'service': 'monitoring-service',
            }
            
            # Get Redis metrics
            redis_info = self.redis_client.info()
            metrics['redis'] = {
                'connected_clients': redis_info.get('connected_clients', 0),
                'used_memory_bytes': redis_info.get('used_memory', 0),
                'used_memory_human': redis_info.get('used_memory_human', '0B'),
                'total_commands_processed': redis_info.get('total_commands_processed', 0),
                'keyspace_hits': redis_info.get('keyspace_hits', 0),
                'keyspace_misses': redis_info.get('keyspace_misses', 0),
                'evicted_keys': redis_info.get('evicted_keys', 0),
            }
            
            # Calculate cache hit rate
            hits = redis_info.get('keyspace_hits', 0)
            misses = redis_info.get('keyspace_misses', 0)
            total_requests = hits + misses
            cache_hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0
            metrics['redis']['cache_hit_rate_percent'] = cache_hit_rate
            
            # Get API metrics from other services
            api_metrics = await self._collect_api_metrics()
            metrics.update(api_metrics)
            
            await self._store_metric('app_metrics', metrics)
            
            self.logger.debug(f"Collected app metrics: Cache hit rate {cache_hit_rate:.1f}%")
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error collecting application metrics: {e}")
            return {}
    
    async def _collect_api_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics from API services - like asking each department for their daily report.
        """
        api_metrics = {
            'django_service': {},
            'fastapi_service': {},
        }
        
        # Collect from Django service
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://django-service/health/', timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        api_metrics['django_service'] = {
                            'status': 'healthy',
                            'response_time_ms': data.get('response_time_ms', 0),
                            'active_connections': data.get('active_connections', 0),
                        }
                    else:
                        api_metrics['django_service'] = {'status': 'unhealthy'}
        except Exception as e:
            api_metrics['django_service'] = {'status': 'unreachable', 'error': str(e)}
        
        # Collect from FastAPI service
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://fastapi-service/health', timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        api_metrics['fastapi_service'] = {
                            'status': 'healthy',
                            'response_time_ms': data.get('response_time_ms', 0),
                            'active_requests': data.get('active_requests', 0),
                            'models_loaded': data.get('models_loaded', 0),
                        }
                    else:
                        api_metrics['fastapi_service'] = {'status': 'unhealthy'}
        except Exception as e:
            api_metrics['fastapi_service'] = {'status': 'unreachable', 'error': str(e)}
        
        return api_metrics
    
    async def record_custom_metric(self, metric_data: Dict[str, Any]):
        """
        Record custom metric from external services.
        Like having a suggestion box where services can report their own metrics.
        """
        try:
            # Validate metric data
            required_fields = ['name', 'value', 'timestamp']
            if not all(field in metric_data for field in required_fields):
                raise ValueError(f"Missing required fields: {required_fields}")
            
            # Add metadata
            enriched_metric = {
                **metric_data,
                'received_at': datetime.utcnow().isoformat(),
                'source': metric_data.get('source', 'unknown'),
                'hostname': self.hostname,
            }
            
            # Store with appropriate expiration
            await self._store_metric('custom_metrics', enriched_metric)
            
            self.logger.info(f"Recorded custom metric: {metric_data['name']} = {metric_data['value']}")
            
        except Exception as e:
            self.logger.error(f"Error recording custom metric: {e}")
            raise
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get the most recent metrics snapshot.
        Like checking the current readings on all your dashboard gauges.
        """
        try:
            # Get latest system metrics
            system_key = 'metrics:system_metrics:latest'
            system_data = self.redis_client.get(system_key)
            system_metrics = json.loads(system_data) if system_data else {}
            
            # Get latest app metrics
            app_key = 'metrics:app_metrics:latest'
            app_data = self.redis_client.get(app_key)
            app_metrics = json.loads(app_data) if app_data else {}
            
            # Calculate derived metrics
            derived_metrics = await self._calculate_derived_metrics(system_metrics, app_metrics)
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'system': system_metrics,
                'application': app_metrics,
                'derived': derived_metrics,
            }
            
        except Exception as e:
            self.logger.error(f"Error getting current metrics: {e}")
            return {}
    
    async def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get historical metrics - like looking at your activity tracker's weekly summary.
        Useful for trending and analysis.
        """
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)
            
            # Get metrics from time-series data in Redis
            metrics_history = []
            
            # Query metrics for each hour
            current_time = start_time
            while current_time <= end_time:
                hour_key = f"metrics:hourly:{current_time.strftime('%Y%m%d%H')}"
                hour_data = self.redis_client.get(hour_key)
                
                if hour_data:
                    metrics_history.append(json.loads(hour_data))
                
                current_time += timedelta(hours=1)
            
            return metrics_history
            
        except Exception as e:
            self.logger.error(f"Error getting metrics history: {e}")
            return []
    
    async def _store_metric(self, metric_type: str, data: Dict[str, Any]):
        """
        Store metric in Redis with appropriate keys and expiration.
        Like filing documents in organized folders with automatic cleanup.
        """
        try:
            timestamp = datetime.utcnow()
            
            # Store latest value
            latest_key = f'metrics:{metric_type}:latest'
            self.redis_client.setex(latest_key, 3600, json.dumps(data))  # 1 hour expiration
            
            # Store in time series (hourly aggregation)
            hour_key = f"metrics:hourly:{timestamp.strftime('%Y%m%d%H')}"
            hour_data = self.redis_client.get(hour_key)
            
            if hour_data:
                # Update existing hour data
                existing_data = json.loads(hour_data)
                # Merge or aggregate data as needed
                existing_data['last_update'] = data['timestamp']
                existing_data['sample_count'] = existing_data.get('sample_count', 0) + 1
                
                # Update averages for key metrics
                if metric_type == 'system_metrics':
                    for key in ['cpu', 'memory', 'disk']:
                        if key in data and key in existing_data:
                            existing_data[key] = self._update_average(
                                existing_data[key], 
                                data[key], 
                                existing_data['sample_count']
                            )
                
                merged_data = existing_data
            else:
                # First entry for this hour
                merged_data = {**data, 'sample_count': 1}
            
            # Store with 7-day expiration
            self.redis_client.setex(hour_key, 604800, json.dumps(merged_data))
            
            # Store in daily aggregation for longer-term storage
            day_key = f"metrics:daily:{timestamp.strftime('%Y%m%d')}"
            self._update_daily_metrics(day_key, data, metric_type)
            
        except Exception as e:
            self.logger.error(f"Error storing metric: {e}")
    
    def _update_average(self, existing_avg: Dict, new_value: Dict, sample_count: int) -> Dict:
        """Update running average for metric values"""
        updated = {}
        for key, value in new_value.items():
            if isinstance(value, (int, float)):
                if key in existing_avg:
                    # Calculate new average
                    old_avg = existing_avg[key]
                    updated[key] = ((old_avg * (sample_count - 1)) + value) / sample_count
                else:
                    updated[key] = value
            else:
                updated[key] = value
        return updated
    
    def _update_daily_metrics(self, day_key: str, data: Dict, metric_type: str):
        """Update daily aggregated metrics"""
        try:
            day_data = self.redis_client.get(day_key)
            
            if day_data:
                existing_data = json.loads(day_data)
            else:
                existing_data = {'date': data['timestamp'][:10], 'metrics': {}}
            
            # Add to daily aggregation
            if metric_type not in existing_data['metrics']:
                existing_data['metrics'][metric_type] = {
                    'count': 0,
                    'first_sample': data['timestamp'],
                    'last_sample': data['timestamp'],
                }
            
            existing_data['metrics'][metric_type]['count'] += 1
            existing_data['metrics'][metric_type]['last_sample'] = data['timestamp']
            
            # Store with 30-day expiration
            self.redis_client.setex(day_key, 2592000, json.dumps(existing_data))
            
        except Exception as e:
            self.logger.error(f"Error updating daily metrics: {e}")
    
    async def _calculate_derived_metrics(self, system_metrics: Dict, app_metrics: Dict) -> Dict[str, Any]:
        """
        Calculate derived metrics from raw data.
        Like a calculator that figures out your car's fuel efficiency from distance and gas used.
        """
        derived = {}
        
        try:
            # System health score (0-100)
            health_factors = []
            
            if system_metrics.get('cpu', {}).get('percent'):
                cpu_score = max(0, 100 - system_metrics['cpu']['percent'])
                health_factors.append(cpu_score)
            
            if system_metrics.get('memory', {}).get('percent'):
                memory_score = max(0, 100 - system_metrics['memory']['percent'])
                health_factors.append(memory_score)
            
            if system_metrics.get('disk', {}).get('percent'):
                disk_score = max(0, 100 - system_metrics['disk']['percent'])
                health_factors.append(disk_score)
            
            derived['system_health_score'] = sum(health_factors) / len(health_factors) if health_factors else 0
            
            # Resource utilization efficiency
            if system_metrics.get('cpu', {}).get('percent') and system_metrics.get('memory', {}).get('percent'):
                cpu_util = system_metrics['cpu']['percent']
                mem_util = system_metrics['memory']['percent']
                
                # Ideal utilization is around 70-80%
                cpu_efficiency = 100 - abs(cpu_util - 75)
                mem_efficiency = 100 - abs(mem_util - 75)
                derived['resource_efficiency'] = (cpu_efficiency + mem_efficiency) / 2
            
            # Cache efficiency from Redis
            if app_metrics.get('redis', {}).get('cache_hit_rate_percent') is not None:
                hit_rate = app_metrics['redis']['cache_hit_rate_percent']
                derived['cache_efficiency'] = hit_rate
            
            # Service availability score
            services = ['django_service', 'fastapi_service']
            healthy_services = sum(
                1 for service in services 
                if app_metrics.get(service, {}).get('status') == 'healthy'
            )
            derived['service_availability_percent'] = (healthy_services / len(services)) * 100
            
            # Performance indicators
            response_times = []
            for service in services:
                rt = app_metrics.get(service, {}).get('response_time_ms')
                if rt:
                    response_times.append(rt)
            
            if response_times:
                derived['avg_service_response_time_ms'] = sum(response_times) / len(response_times)
                derived['sla_compliance'] = all(rt < 100 for rt in response_times)  # Your <100ms target
            
        except Exception as e:
            self.logger.error(f"Error calculating derived metrics: {e}")
        
        return derived
    
    async def _check_system_alerts(self, metrics: Dict[str, Any]):
        """
        Check for system-level alert conditions.
        Like smoke detectors that automatically call the fire department.
        """
        try:
            alerts = []
            
            # CPU usage alert
            cpu_percent = metrics.get('cpu', {}).get('percent', 0)
            if cpu_percent > 90:
                alerts.append({
                    'type': 'system_alert',
                    'severity': 'critical',
                    'message': f'High CPU usage: {cpu_percent:.1f}%',
                    'metric': 'cpu_percent',
                    'value': cpu_percent,
                    'threshold': 90,
                    'timestamp': datetime.utcnow().isoformat()
                })
            elif cpu_percent > 80:
                alerts.append({
                    'type': 'system_alert',
                    'severity': 'warning',
                    'message': f'Elevated CPU usage: {cpu_percent:.1f}%',
                    'metric': 'cpu_percent',
                    'value': cpu_percent,
                    'threshold': 80,
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            # Memory usage alert
            memory_percent = metrics.get('memory', {}).get('percent', 0)
            if memory_percent > 95:
                alerts.append({
                    'type': 'system_alert',
                    'severity': 'critical',
                    'message': f'Critical memory usage: {memory_percent:.1f}%',
                    'metric': 'memory_percent',
                    'value': memory_percent,
                    'threshold': 95,
                    'timestamp': datetime.utcnow().isoformat()
                })
            elif memory_percent > 85:
                alerts.append({
                    'type': 'system_alert',
                    'severity': 'warning',
                    'message': f'High memory usage: {memory_percent:.1f}%',
                    'metric': 'memory_percent',
                    'value': memory_percent,
                    'threshold': 85,
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            # Disk usage alert
            disk_percent = metrics.get('disk', {}).get('percent', 0)
            if disk_percent > 95:
                alerts.append({
                    'type': 'system_alert',
                    'severity': 'critical',
                    'message': f'Critical disk usage: {disk_percent:.1f}%',
                    'metric': 'disk_percent',
                    'value': disk_percent,
                    'threshold': 95,
                    'timestamp': datetime.utcnow().isoformat()
                })
            elif disk_percent > 85:
                alerts.append({
                    'type': 'system_alert',
                    'severity': 'warning',
                    'message': f'High disk usage: {disk_percent:.1f}%',
                    'metric': 'disk_percent',
                    'value': disk_percent,
                    'threshold': 85,
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            # Store alerts in Redis for alert manager
            for alert in alerts:
                alert_key = f"alerts:system:{alert['metric']}:{int(time.time())}"
                self.redis_client.setex(alert_key, 3600, json.dumps(alert))  # 1 hour expiration
            
        except Exception as e:
            self.logger.error(f"Error checking system alerts: {e}")
    
    async def cleanup_old_metrics(self):
        """
        Clean up old metrics to prevent Redis from growing too large.
        Like emptying the trash regularly to keep your workspace clean.
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.metric_config['retention_days'])
            
            # Find and delete old daily metrics
            pattern = "metrics:daily:*"
            for key in self.redis_client.scan_iter(match=pattern):
                key_str = key.decode() if isinstance(key, bytes) else key
                date_part = key_str.split(':')[-1]
                
                try:
                    key_date = datetime.strptime(date_part, '%Y%m%d')
                    if key_date < cutoff_date:
                        self.redis_client.delete(key)
                        self.logger.debug(f"Deleted old metric key: {key}")
                except ValueError:
                    # Invalid date format, skip
                    continue
            
            # Clean up old hourly metrics (keep last 48 hours)
            cutoff_hour = datetime.utcnow() - timedelta(hours=48)
            pattern = "metrics:hourly:*"
            for key in self.redis_client.scan_iter(match=pattern):
                key_str = key.decode() if isinstance(key, bytes) else key
                hour_part = key_str.split(':')[-1]
                
                try:
                    key_hour = datetime.strptime(hour_part, '%Y%m%d%H')
                    if key_hour < cutoff_hour:
                        self.redis_client.delete(key)
                        self.logger.debug(f"Deleted old hourly metric: {key}")
                except ValueError:
                    continue
            
            self.logger.info("Completed metrics cleanup")
            
        except Exception as e:
            self.logger.error(f"Error during metrics cleanup: {e}")
    
    async def export_metrics(self, start_time: datetime, end_time: datetime, format: str = 'json') -> Dict[str, Any]:
        """
        Export metrics for external analysis or backup.
        Like creating a backup copy of your important data.
        """
        try:
            exported_data = {
                'export_timestamp': datetime.utcnow().isoformat(),
                'period_start': start_time.isoformat(),
                'period_end': end_time.isoformat(),
                'format': format,
                'metrics': []
            }
            
            # Export daily metrics for the period
            current_date = start_time.date()
            end_date = end_time.date()
            
            while current_date <= end_date:
                day_key = f"metrics:daily:{current_date.strftime('%Y%m%d')}"
                day_data = self.redis_client.get(day_key)
                
                if day_data:
                    exported_data['metrics'].append(json.loads(day_data))
                
                current_date += timedelta(days=1)
            
            self.logger.info(f"Exported {len(exported_data['metrics'])} daily metric records")
            return exported_data
            
        except Exception as e:
            self.logger.error(f"Error exporting metrics: {e}")
            return {}


class MetricsAggregator:
    """
    Aggregates metrics across multiple instances and time periods.
    Like a financial analyst who summarizes quarterly reports from all departments.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
    
    async def aggregate_hourly_metrics(self, hour: datetime) -> Dict[str, Any]:
        """Aggregate all metrics for a specific hour"""
        try:
            hour_key = f"metrics:hourly:{hour.strftime('%Y%m%d%H')}"
            aggregated_data = {
                'hour': hour.isoformat(),
                'system_metrics': {
                    'avg_cpu_percent': 0,
                    'avg_memory_percent': 0,
                    'avg_disk_percent': 0,
                    'sample_count': 0
                },
                'application_metrics': {
                    'avg_response_time_ms': 0,
                    'total_requests': 0,
                    'cache_hit_rate': 0
                }
            }
            
            # Get all metric samples for this hour
            pattern = f"metrics:*:{hour.strftime('%Y%m%d%H')}:*"
            sample_keys = list(self.redis_client.scan_iter(match=pattern))
            
            if not sample_keys:
                return aggregated_data
            
            # Aggregate samples
            total_samples = len(sample_keys)
            cpu_sum = memory_sum = disk_sum = 0
            response_time_sum = request_count = cache_hits = cache_total = 0
            
            for key in sample_keys:
                data = self.redis_client.get(key)
                if data:
                    sample = json.loads(data)
                    
                    # Aggregate system metrics
                    if 'cpu' in sample:
                        cpu_sum += sample['cpu'].get('percent', 0)
                    if 'memory' in sample:
                        memory_sum += sample['memory'].get('percent', 0)
                    if 'disk' in sample:
                        disk_sum += sample['disk'].get('percent', 0)
                    
                    # Aggregate app metrics
                    if 'response_time_ms' in sample:
                        response_time_sum += sample['response_time_ms']
                    if 'request_count' in sample:
                        request_count += sample['request_count']
                    if 'redis' in sample:
                        redis_data = sample['redis']
                        cache_hits += redis_data.get('keyspace_hits', 0)
                        cache_total += redis_data.get('keyspace_hits', 0) + redis_data.get('keyspace_misses', 0)
            
            # Calculate averages
            if total_samples > 0:
                aggregated_data['system_metrics'].update({
                    'avg_cpu_percent': cpu_sum / total_samples,
                    'avg_memory_percent': memory_sum / total_samples,
                    'avg_disk_percent': disk_sum / total_samples,
                    'sample_count': total_samples
                })
                
                aggregated_data['application_metrics'].update({
                    'avg_response_time_ms': response_time_sum / total_samples,
                    'total_requests': request_count,
                    'cache_hit_rate': (cache_hits / cache_total * 100) if cache_total > 0 else 0
                })
            
            # Store aggregated data
            self.redis_client.setex(hour_key, 604800, json.dumps(aggregated_data))  # 7 days
            
            return aggregated_data
            
        except Exception as e:
            self.logger.error(f"Error aggregating hourly metrics: {e}")
            return {}
    
    async def generate_daily_summary(self, date: datetime) -> Dict[str, Any]:
        """Generate daily summary from hourly data"""
        try:
            daily_summary = {
                'date': date.date().isoformat(),
                'system_performance': {
                    'peak_cpu_percent': 0,
                    'avg_cpu_percent': 0,
                    'peak_memory_percent': 0,
                    'avg_memory_percent': 0,
                    'disk_usage_percent': 0
                },
                'application_performance': {
                    'total_requests': 0,
                    'avg_response_time_ms': 0,
                    'peak_response_time_ms': 0,
                    'uptime_percent': 100,
                    'sla_compliance_percent': 0
                },
                'alerts_summary': {
                    'total_alerts': 0,
                    'critical_alerts': 0,
                    'warning_alerts': 0
                }
            }
            
            # Aggregate from 24 hourly summaries
            hourly_data = []
            for hour in range(24):
                hour_time = date.replace(hour=hour, minute=0, second=0, microsecond=0)
                hour_key = f"metrics:hourly:{hour_time.strftime('%Y%m%d%H')}"
                hour_data = self.redis_client.get(hour_key)
                
                if hour_data:
                    hourly_data.append(json.loads(hour_data))
            
            if hourly_data:
                # Calculate daily averages and peaks
                cpu_values = [h['system_metrics']['avg_cpu_percent'] for h in hourly_data if 'system_metrics' in h]
                memory_values = [h['system_metrics']['avg_memory_percent'] for h in hourly_data if 'system_metrics' in h]
                response_times = [h['application_metrics']['avg_response_time_ms'] for h in hourly_data if 'application_metrics' in h]
                
                if cpu_values:
                    daily_summary['system_performance']['peak_cpu_percent'] = max(cpu_values)
                    daily_summary['system_performance']['avg_cpu_percent'] = sum(cpu_values) / len(cpu_values)
                
                if memory_values:
                    daily_summary['system_performance']['peak_memory_percent'] = max(memory_values)
                    daily_summary['system_performance']['avg_memory_percent'] = sum(memory_values) / len(memory_values)
                
                if response_times:
                    daily_summary['application_performance']['avg_response_time_ms'] = sum(response_times) / len(response_times)
                    daily_summary['application_performance']['peak_response_time_ms'] = max(response_times)
                    
                    # Calculate SLA compliance (your <100ms target)
                    sla_compliant = sum(1 for rt in response_times if rt < 100)
                    daily_summary['application_performance']['sla_compliance_percent'] = (sla_compliant / len(response_times)) * 100
                
                # Sum total requests
                total_requests = sum(h['application_metrics'].get('total_requests', 0) for h in hourly_data)
                daily_summary['application_performance']['total_requests'] = total_requests
            
            # Store daily summary
            day_key = f"summary:daily:{date.strftime('%Y%m%d')}"
            self.redis_client.setex(day_key, 2592000, json.dumps(daily_summary))  # 30 days
            
            return daily_summary
            
        except Exception as e:
            self.logger.error(f"Error generating daily summary: {e}")
            return {}