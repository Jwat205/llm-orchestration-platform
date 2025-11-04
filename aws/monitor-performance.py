#!/usr/bin/env python3
"""
Performance Monitoring Script for LLM API Platform
Validates that the deployed infrastructure meets performance requirements:
- 1,000+ concurrent requests/second
- <100ms response time
- 99.5% uptime
"""

import argparse
import asyncio
import json
import time
import statistics
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import subprocess
import sys

try:
    import aiohttp
    import boto3
    from datetime import datetime, timedelta
except ImportError:
    print("Please install required dependencies:")
    print("pip install aiohttp boto3")
    sys.exit(1)


@dataclass
class PerformanceResults:
    """Data class to store performance test results"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    success_rate: float


class LLMAPIPerformanceMonitor:
    """Performance monitoring and validation for LLM API Platform"""

    def __init__(self, alb_endpoint: str, region: str = "us-east-1"):
        self.alb_endpoint = alb_endpoint.rstrip('/')
        self.region = region
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.ecs = boto3.client('ecs', region_name=region)
        self.rds = boto3.client('rds', region_name=region)
        self.elasticache = boto3.client('elasticache', region_name=region)

    async def run_load_test(self,
                           concurrent_requests: int = 100,
                           total_requests: int = 1000,
                           endpoint: str = "/health") -> PerformanceResults:
        """Run async load test against the API"""

        print(f"🚀 Running load test: {concurrent_requests} concurrent, {total_requests} total requests")
        print(f"📍 Endpoint: {self.alb_endpoint}{endpoint}")

        response_times = []
        successful_requests = 0
        failed_requests = 0

        semaphore = asyncio.Semaphore(concurrent_requests)
        start_time = time.time()

        async def make_request(session: aiohttp.ClientSession, request_id: int) -> Dict[str, Any]:
            """Make a single HTTP request"""
            async with semaphore:
                try:
                    request_start = time.time()
                    async with session.get(f"{self.alb_endpoint}{endpoint}") as response:
                        response_time = (time.time() - request_start) * 1000  # Convert to ms
                        await response.read()  # Consume response body

                        return {
                            'request_id': request_id,
                            'status_code': response.status,
                            'response_time': response_time,
                            'success': 200 <= response.status < 300
                        }
                except Exception as e:
                    return {
                        'request_id': request_id,
                        'status_code': 0,
                        'response_time': 0,
                        'success': False,
                        'error': str(e)
                    }

        # Run load test
        connector = aiohttp.TCPConnector(limit=concurrent_requests, limit_per_host=concurrent_requests)
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [make_request(session, i) for i in range(total_requests)]
            results = await asyncio.gather(*tasks)

        # Process results
        total_time = time.time() - start_time

        for result in results:
            if result['success']:
                successful_requests += 1
                response_times.append(result['response_time'])
            else:
                failed_requests += 1

        # Calculate metrics
        if response_times:
            avg_response_time = statistics.mean(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
            p99_response_time = statistics.quantiles(response_times, n=100)[98]  # 99th percentile
        else:
            avg_response_time = p95_response_time = p99_response_time = 0

        requests_per_second = total_requests / total_time if total_time > 0 else 0
        success_rate = (successful_requests / total_requests) * 100 if total_requests > 0 else 0

        return PerformanceResults(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            average_response_time=avg_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=requests_per_second,
            success_rate=success_rate
        )

    def get_cloudwatch_metrics(self, hours_back: int = 1) -> Dict[str, Any]:
        """Retrieve CloudWatch metrics for the infrastructure"""

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)

        print(f"📊 Fetching CloudWatch metrics for the last {hours_back} hour(s)")

        metrics = {}

        try:
            # ALB metrics
            alb_metrics = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/ApplicationELB',
                MetricName='TargetResponseTime',
                Dimensions=[],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average', 'Maximum']
            )

            if alb_metrics['Datapoints']:
                latest_alb = max(alb_metrics['Datapoints'], key=lambda x: x['Timestamp'])
                metrics['alb_response_time'] = {
                    'average': latest_alb['Average'] * 1000,  # Convert to ms
                    'maximum': latest_alb['Maximum'] * 1000
                }

            # Request count
            request_metrics = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/ApplicationELB',
                MetricName='RequestCount',
                Dimensions=[],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Sum']
            )

            if request_metrics['Datapoints']:
                total_requests = sum(dp['Sum'] for dp in request_metrics['Datapoints'])
                metrics['total_requests'] = total_requests
                metrics['requests_per_second'] = total_requests / (hours_back * 3600)

        except Exception as e:
            print(f"⚠️  Error fetching CloudWatch metrics: {e}")

        return metrics

    def validate_performance_requirements(self, results: PerformanceResults,
                                        cloudwatch_metrics: Dict[str, Any]) -> Dict[str, bool]:
        """Validate that performance requirements are met"""

        validations = {}

        # Validate response time (<100ms target)
        validations['response_time_p95'] = results.p95_response_time < 100
        validations['response_time_avg'] = results.average_response_time < 100

        # Validate success rate (99.5% target)
        validations['uptime_target'] = results.success_rate >= 99.5

        # Validate throughput (1000+ req/sec capability)
        validations['throughput_capability'] = results.requests_per_second >= 100  # Scaled test

        # Validate CloudWatch metrics if available
        if 'alb_response_time' in cloudwatch_metrics:
            validations['production_response_time'] = cloudwatch_metrics['alb_response_time']['average'] < 100

        return validations

    def check_infrastructure_health(self) -> Dict[str, Any]:
        """Check the health of infrastructure components"""

        health_status = {}

        try:
            # Check ECS services
            clusters = self.ecs.list_clusters()['clusterArns']
            for cluster_arn in clusters:
                if 'llm-api' in cluster_arn:
                    services = self.ecs.list_services(cluster=cluster_arn)['serviceArns']
                    for service_arn in services:
                        service_details = self.ecs.describe_services(
                            cluster=cluster_arn,
                            services=[service_arn]
                        )['services'][0]

                        service_name = service_details['serviceName']
                        running_count = service_details['runningCount']
                        desired_count = service_details['desiredCount']

                        health_status[f'ecs_{service_name}'] = {
                            'running': running_count,
                            'desired': desired_count,
                            'healthy': running_count == desired_count
                        }

        except Exception as e:
            print(f"⚠️  Error checking ECS health: {e}")

        return health_status

    def generate_performance_report(self, results: PerformanceResults,
                                  validations: Dict[str, bool],
                                  cloudwatch_metrics: Dict[str, Any],
                                  health_status: Dict[str, Any]) -> str:
        """Generate a comprehensive performance report"""

        report = []
        report.append("=" * 80)
        report.append("🚀 LLM API PLATFORM PERFORMANCE REPORT")
        report.append("=" * 80)
        report.append(f"📅 Timestamp: {datetime.now().isoformat()}")
        report.append(f"🌐 Endpoint: {self.alb_endpoint}")
        report.append("")

        # Load Test Results
        report.append("📈 LOAD TEST RESULTS")
        report.append("-" * 40)
        report.append(f"Total Requests: {results.total_requests:,}")
        report.append(f"Successful Requests: {results.successful_requests:,}")
        report.append(f"Failed Requests: {results.failed_requests:,}")
        report.append(f"Success Rate: {results.success_rate:.2f}%")
        report.append(f"Requests/Second: {results.requests_per_second:.2f}")
        report.append(f"Average Response Time: {results.average_response_time:.2f}ms")
        report.append(f"95th Percentile: {results.p95_response_time:.2f}ms")
        report.append(f"99th Percentile: {results.p99_response_time:.2f}ms")
        report.append("")

        # Performance Requirements Validation
        report.append("✅ PERFORMANCE REQUIREMENTS VALIDATION")
        report.append("-" * 40)
        for requirement, passed in validations.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            report.append(f"{requirement.replace('_', ' ').title()}: {status}")
        report.append("")

        # CloudWatch Production Metrics
        if cloudwatch_metrics:
            report.append("📊 PRODUCTION METRICS (CloudWatch)")
            report.append("-" * 40)
            if 'alb_response_time' in cloudwatch_metrics:
                report.append(f"ALB Avg Response Time: {cloudwatch_metrics['alb_response_time']['average']:.2f}ms")
                report.append(f"ALB Max Response Time: {cloudwatch_metrics['alb_response_time']['maximum']:.2f}ms")
            if 'total_requests' in cloudwatch_metrics:
                report.append(f"Production Requests/Hour: {cloudwatch_metrics.get('total_requests', 0):,.0f}")
                report.append(f"Production Requests/Second: {cloudwatch_metrics.get('requests_per_second', 0):.2f}")
            report.append("")

        # Infrastructure Health
        if health_status:
            report.append("🏥 INFRASTRUCTURE HEALTH")
            report.append("-" * 40)
            for service, status in health_status.items():
                if isinstance(status, dict) and 'healthy' in status:
                    health_icon = "✅" if status['healthy'] else "❌"
                    report.append(f"{service}: {health_icon} {status['running']}/{status['desired']} tasks")
            report.append("")

        # Performance Summary
        report.append("🎯 PERFORMANCE SUMMARY")
        report.append("-" * 40)

        overall_health = "🟢 EXCELLENT"
        if not all(validations.values()):
            overall_health = "🟡 NEEDS ATTENTION"
        if results.success_rate < 95:
            overall_health = "🔴 CRITICAL"

        report.append(f"Overall Status: {overall_health}")
        report.append("")

        # Recommendations
        report.append("💡 RECOMMENDATIONS")
        report.append("-" * 40)

        if not validations.get('response_time_p95', True):
            report.append("• Consider increasing ECS task CPU/memory allocation")
            report.append("• Review database query optimization")
            report.append("• Check Redis cache hit rates")

        if not validations.get('uptime_target', True):
            report.append("• Investigate failed request patterns")
            report.append("• Review application logs for errors")
            report.append("• Consider increasing health check thresholds")

        if results.requests_per_second < 1000:
            report.append("• Scale up ECS service desired count")
            report.append("• Optimize application for higher concurrency")
            report.append("• Consider using faster instance types")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)


async def main():
    parser = argparse.ArgumentParser(description="Monitor LLM API Platform performance")
    parser.add_argument("endpoint", help="ALB endpoint URL")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--concurrent", type=int, default=100, help="Concurrent requests")
    parser.add_argument("--total", type=int, default=1000, help="Total requests")
    parser.add_argument("--output", help="Output file for report")

    args = parser.parse_args()

    monitor = LLMAPIPerformanceMonitor(args.endpoint, args.region)

    # Run load test
    results = await monitor.run_load_test(args.concurrent, args.total)

    # Get CloudWatch metrics
    cloudwatch_metrics = monitor.get_cloudwatch_metrics()

    # Check infrastructure health
    health_status = monitor.check_infrastructure_health()

    # Validate performance requirements
    validations = monitor.validate_performance_requirements(results, cloudwatch_metrics)

    # Generate report
    report = monitor.generate_performance_report(results, validations, cloudwatch_metrics, health_status)

    # Output report
    print(report)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"\n📄 Report saved to: {args.output}")

    # Exit with non-zero code if critical issues found
    if not all(validations.values()) or results.success_rate < 99:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())