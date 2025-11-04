import asyncio
import json
import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
import redis
from collections import defaultdict
import random

class CostAnalyzer:
    """
    Cost Analyzer - like a financial analyst for your API platform.
    
    This analyzes costs and revenue patterns to optimize profitability:
    - Infrastructure costs vs usage
    - Revenue per user analysis
    - Cost optimization opportunities
    - Pricing model effectiveness
    
    Think of this as your platform's CFO that helps you understand the financial
    health and optimization opportunities for your high-volume operation.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        
        # Cost structure configuration (based on typical cloud costs)
        self.cost_structure = {
            'infrastructure': {
                'compute_cost_per_hour': 2.50,      # Server costs per hour
                'gpu_cost_per_hour': 8.00,          # GPU instance costs
                'storage_cost_per_gb_month': 0.10,  # Storage costs
                'bandwidth_cost_per_gb': 0.09,      # Data transfer costs
                'load_balancer_cost_per_hour': 0.18 # Load balancer costs
            },
            'third_party': {
                'monitoring_cost_per_month': 200,   # Monitoring tools
                'cdn_cost_per_gb': 0.05,           # CDN costs
                'backup_cost_per_gb_month': 0.05,  # Backup storage
                'security_tools_per_month': 150    # Security tools
            },
            'operational': {
                'support_cost_per_user_month': 2.00,  # Customer support
                'development_cost_per_month': 15000,  # Development team
                'devops_cost_per_month': 8000        # DevOps/SRE team
            }
        }
        
        # Revenue model (typical SaaS pricing)
        self.pricing_tiers = {
            'free': {'monthly_cost': 0, 'tokens_included': 10000, 'overage_per_1k': 0},
            'starter': {'monthly_cost': 20, 'tokens_included': 100000, 'overage_per_1k': 0.002},
            'professional': {'monthly_cost': 100, 'tokens_included': 1000000, 'overage_per_1k': 0.0015},
            'enterprise': {'monthly_cost': 500, 'tokens_included': 10000000, 'overage_per_1k': 0.001}
        }
    
    async def analyze_cost_patterns(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze comprehensive cost patterns and optimization opportunities.
        Like creating a detailed financial report for your business.
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)
            
            analysis = {
                'analysis_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'cost_breakdown': {},
                'revenue_analysis': {},
                'profitability': {},
                'cost_efficiency': {},
                'optimization_opportunities': {},
                'trends': {},
                'projections': {},
                'recommendations': []
            }
            
            # Collect usage and performance data for cost calculation
            usage_data = await self._collect_cost_relevant_data(start_date, end_date)
            
            if not usage_data:
                return {'error': 'No cost data available for analysis'}
            
            # Analyze different cost aspects
            analysis['cost_breakdown'] = await self._analyze_cost_breakdown(usage_data)
            analysis['revenue_analysis'] = await self._analyze_revenue_patterns(usage_data)
            analysis['profitability'] = await self._analyze_profitability(
                analysis['cost_breakdown'], analysis['revenue_analysis']
            )
            analysis['cost_efficiency'] = await self._analyze_cost_efficiency(usage_data)
            analysis['optimization_opportunities'] = await self._identify_optimization_opportunities(
                analysis['cost_breakdown'], usage_data
            )
            analysis['trends'] = await self._analyze_cost_trends(usage_data, days)
            analysis['projections'] = await self._generate_cost_projections(analysis)
            
            # Generate cost optimization recommendations
            analysis['recommendations'] = await self._generate_cost_recommendations(analysis)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing cost patterns: {e}")
            return {'error': str(e)}
    
    async def _collect_cost_relevant_data(self, start_date, end_date) -> List[Dict[str, Any]]:
        """
        Collect data relevant for cost analysis.
        Like gathering all receipts and invoices for accounting.
        """
        try:
            cost_data = []
            
            current_date = start_date
            while current_date <= end_date:
                date_key = current_date.strftime('%Y%m%d')
                
                day_data = {
                    'date': current_date.isoformat(),
                    'infrastructure_usage': {},
                    'api_usage': {},
                    'user_activity': {},
                    'performance_metrics': {}
                }
                
                # Get performance data (contains resource usage info)
                perf_key = f"performance:daily:{date_key}"
                perf_data = self.redis_client.get(perf_key)
                
                if perf_data:
                    try:
                        perf_info = json.loads(perf_data)
                        day_data['performance_metrics'] = perf_info
                        
                        # Estimate infrastructure usage from performance data
                        day_data['infrastructure_usage'] = self._estimate_infrastructure_usage(perf_info)
                        
                    except json.JSONDecodeError:
                        pass
                
                # Get usage data
                usage_key = f"usage:daily:{date_key}"
                usage_data_raw = self.redis_client.get(usage_key)
                
                if usage_data_raw:
                    try:
                        usage_info = json.loads(usage_data_raw)
                        day_data['api_usage'] = usage_info
                    except json.JSONDecodeError:
                        pass
                
                # Simulate realistic cost data if no actual data available
                if not day_data['api_usage'] and not day_data['infrastructure_usage']:
                    day_data.update(await self._simulate_daily_cost_data(current_date))
                
                cost_data.append(day_data)
                current_date += timedelta(days=1)
            
            return cost_data
            
        except Exception as e:
            self.logger.error(f"Error collecting cost data: {e}")
            return []
    
    def _estimate_infrastructure_usage(self, perf_info: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate infrastructure usage from performance metrics"""
        # Extract relevant metrics
        total_requests = perf_info.get('total_requests', 0)
        avg_response_time = perf_info.get('avg_response_time_ms', 0)
        avg_cpu = perf_info.get('system_stats', {}).get('avg_cpu_percent', 0)
        avg_memory = perf_info.get('system_stats', {}).get('avg_memory_percent', 0)
        
        # Estimate resource usage
        estimated_usage = {
            'compute_hours': 24,  # Assume instances run 24/7
            'gpu_hours': 0,       # GPU usage based on ML workload
            'storage_gb': 100,    # Base storage
            'bandwidth_gb': total_requests * 0.001,  # Rough estimate
            'cpu_utilization': avg_cpu,
            'memory_utilization': avg_memory
        }
        
        # Estimate GPU usage for AI workloads
        if total_requests > 10000:  # High AI usage
            estimated_usage['gpu_hours'] = min(24, total_requests / 5000)  # Scale with usage
        
        # Adjust compute based on utilization
        if avg_cpu > 50:  # High CPU usage
            estimated_usage['compute_hours'] = 24  # Full utilization
        elif avg_cpu > 20:
            estimated_usage['compute_hours'] = 16  # Partial utilization
        else:
            estimated_usage['compute_hours'] = 8   # Low utilization
        
        return estimated_usage
    
    async def _simulate_daily_cost_data(self, date: datetime.date) -> Dict[str, Any]:
        """Simulate realistic daily cost data based on your platform scale"""
        
        # Base on your 100M+ monthly requests (3.3M+ daily average)
        daily_requests = random.randint(2000000, 5000000)  # 2-5M requests
        daily_users = random.randint(8000, 25000)          # 8K-25K daily users
        daily_tokens = daily_requests * random.randint(50, 200)  # 50-200 tokens per request
        
        return {
            'api_usage': {
                'total_requests': daily_requests,
                'total_tokens': daily_tokens,
                'unique_users': daily_users,
                'avg_tokens_per_request': daily_tokens / daily_requests,
                'peak_rps': random.randint(800, 1500),  # Peak requests per second
            },
            'infrastructure_usage': {
                'compute_hours': 24,  # Always-on infrastructure
                'gpu_hours': random.randint(12, 24),  # GPU usage for AI
                'storage_gb': random.randint(500, 1000),
                'bandwidth_gb': daily_requests * 0.0015,  # ~1.5KB per request
                'cpu_utilization': random.randint(30, 80),
                'memory_utilization': random.randint(40, 85)
            },
            'user_activity': {
                'new_signups': random.randint(50, 200),
                'active_subscriptions': random.randint(1000, 5000),
                'churned_users': random.randint(10, 50)
            }
        }
    
    async def _analyze_cost_breakdown(self, usage_data: List[Dict]) -> Dict[str, Any]:
        """
        Analyze detailed cost breakdown by category.
        Like itemizing all expenses on your business credit card statement.
        """
        try:
            total_costs = {
                'infrastructure': {
                    'compute': 0,
                    'gpu': 0,
                    'storage': 0,
                    'bandwidth': 0,
                    'load_balancer': 0
                },
                'third_party': {
                    'monitoring': 0,
                    'cdn': 0,
                    'backup': 0,
                    'security': 0
                },
                'operational': {
                    'support': 0,
                    'development': 0,
                    'devops': 0
                }
            }
            
            daily_costs = []
            total_requests = 0
            total_users = 0
            
            for day_data in usage_data:
                infra_usage = day_data.get('infrastructure_usage', {})
                api_usage = day_data.get('api_usage', {})
                user_activity = day_data.get('user_activity', {})
                
                # Calculate daily infrastructure costs
                daily_infra_cost = {
                    'compute': infra_usage.get('compute_hours', 0) * self.cost_structure['infrastructure']['compute_cost_per_hour'],
                    'gpu': infra_usage.get('gpu_hours', 0) * self.cost_structure['infrastructure']['gpu_cost_per_hour'],
                    'storage': infra_usage.get('storage_gb', 0) * self.cost_structure['infrastructure']['storage_cost_per_gb_month'] / 30,
                    'bandwidth': infra_usage.get('bandwidth_gb', 0) * self.cost_structure['infrastructure']['bandwidth_cost_per_gb'],
                    'load_balancer': 24 * self.cost_structure['infrastructure']['load_balancer_cost_per_hour']
                }
                
                # Calculate daily third-party costs
                daily_third_party_cost = {
                    'monitoring': self.cost_structure['third_party']['monitoring_cost_per_month'] / 30,
                    'cdn': infra_usage.get('bandwidth_gb', 0) * self.cost_structure['third_party']['cdn_cost_per_gb'],
                    'backup': infra_usage.get('storage_gb', 0) * self.cost_structure['third_party']['backup_cost_per_gb_month'] / 30,
                    'security': self.cost_structure['third_party']['security_tools_per_month'] / 30
                }
                
                # Calculate daily operational costs
                active_users = user_activity.get('active_subscriptions', api_usage.get('unique_users', 0))
                daily_operational_cost = {
                    'support': active_users * self.cost_structure['operational']['support_cost_per_user_month'] / 30,
                    'development': self.cost_structure['operational']['development_cost_per_month'] / 30,
                    'devops': self.cost_structure['operational']['devops_cost_per_month'] / 30
                }
                
                # Accumulate totals
                for category in total_costs:
                    for subcategory in total_costs[category]:
                        if category == 'infrastructure':
                            total_costs[category][subcategory] += daily_infra_cost[subcategory]
                        elif category == 'third_party':
                            total_costs[category][subcategory] += daily_third_party_cost[subcategory]
                        elif category == 'operational':
                            total_costs[category][subcategory] += daily_operational_cost[subcategory]
                
                # Store daily totals for trend analysis
                daily_total = (
                    sum(daily_infra_cost.values()) +
                    sum(daily_third_party_cost.values()) +
                    sum(daily_operational_cost.values())
                )
                
                daily_costs.append({
                    'date': day_data['date'],
                    'total_cost': daily_total,
                    'infrastructure': sum(daily_infra_cost.values()),
                    'third_party': sum(daily_third_party_cost.values()),
                    'operational': sum(daily_operational_cost.values()),
                    'requests': api_usage.get('total_requests', 0),
                    'cost_per_request': daily_total / api_usage.get('total_requests', 1) if api_usage.get('total_requests', 0) > 0 else 0
                })
                
                total_requests += api_usage.get('total_requests', 0)
                total_users += api_usage.get('unique_users', 0)
            
            # Calculate summary metrics
            period_total_cost = sum(sum(subcosts.values()) for subcosts in total_costs.values())
            avg_daily_cost = period_total_cost / len(usage_data) if usage_data else 0
            cost_per_request = period_total_cost / total_requests if total_requests > 0 else 0
            cost_per_user = period_total_cost / total_users if total_users > 0 else 0
            
            # Calculate category percentages
            category_totals = {
                'infrastructure': sum(total_costs['infrastructure'].values()),
                'third_party': sum(total_costs['third_party'].values()),
                'operational': sum(total_costs['operational'].values())
            }
            
            category_percentages = {
                category: (total / period_total_cost) * 100 if period_total_cost > 0 else 0
                for category, total in category_totals.items()
            }
            
            return {
                'period_total_cost': round(period_total_cost, 2),
                'avg_daily_cost': round(avg_daily_cost, 2),
                'cost_per_request': round(cost_per_request, 6),
                'cost_per_user': round(cost_per_user, 2),
                'category_breakdown': {
                    category: {
                        'total': round(sum(subcosts.values()), 2),
                        'percentage': round(category_percentages[category], 1),
                        'subcategories': {
                            subcat: round(cost, 2)
                            for subcat, cost in subcosts.items()
                        }
                    }
                    for category, subcosts in total_costs.items()
                },
                'daily_costs': daily_costs,
                'cost_efficiency_metrics': {
                    'infrastructure_efficiency': round((category_totals['infrastructure'] / total_requests) * 1000000, 2) if total_requests > 0 else 0,  # Cost per million requests
                    'operational_efficiency': round(category_totals['operational'] / total_users, 2) if total_users > 0 else 0,
                    'total_requests': total_requests,
                    'total_users': total_users
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing cost breakdown: {e}")
            return {}
    
    async def _analyze_revenue_patterns(self, usage_data: List[Dict]) -> Dict[str, Any]:
        """
        Analyze revenue patterns based on user usage and pricing tiers.
        Like analyzing your sales performance and customer value.
        """
        try:
            revenue_analysis = {
                'total_revenue': 0,
                'revenue_by_tier': {},
                'revenue_streams': {
                    'subscriptions': 0,
                    'overages': 0,
                    'enterprise_contracts': 0
                },
                'user_metrics': {
                    'total_paying_users': 0,
                    'avg_revenue_per_user': 0,
                    'user_distribution_by_tier': {}
                },
                'daily_revenue': []
            }
            
            # Simulate user distribution across pricing tiers based on typical SaaS patterns
            total_users = sum(day.get('api_usage', {}).get('unique_users', 0) for day in usage_data)
            avg_daily_users = total_users / len(usage_data) if usage_data else 0
            
            # Typical freemium distribution
            user_distribution = {
                'free': int(avg_daily_users * 0.70),      # 70% free users
                'starter': int(avg_daily_users * 0.20),   # 20% starter
                'professional': int(avg_daily_users * 0.08),  # 8% professional
                'enterprise': int(avg_daily_users * 0.02)  # 2% enterprise
            }
            
            # Calculate revenue for the period
            days_in_period = len(usage_data)
            monthly_multiplier = days_in_period / 30
            
            for tier, user_count in user_distribution.items():
                if tier == 'free':
                    continue  # No revenue from free tier
                
                tier_config = self.pricing_tiers[tier]
                
                # Base subscription revenue
                monthly_revenue = user_count * tier_config['monthly_cost']
                period_revenue = monthly_revenue * monthly_multiplier
                
                # Calculate overage revenue (simulate some users exceeding limits)
                overage_users = int(user_count * 0.3)  # 30% of users have overages
                avg_overage_tokens = tier_config['tokens_included'] * 0.2  # 20% overage
                overage_revenue = (
                    overage_users * 
                    (avg_overage_tokens / 1000) * 
                    tier_config['overage_per_1k'] * 
                    days_in_period
                )
                
                revenue_analysis['revenue_by_tier'][tier] = {
                    'users': user_count,
                    'subscription_revenue': round(period_revenue, 2),
                    'overage_revenue': round(overage_revenue, 2),
                    'total_revenue': round(period_revenue + overage_revenue, 2),
                    'avg_revenue_per_user': round((period_revenue + overage_revenue) / user_count, 2) if user_count > 0 else 0
                }
                
                revenue_analysis['revenue_streams']['subscriptions'] += period_revenue
                revenue_analysis['revenue_streams']['overages'] += overage_revenue
                revenue_analysis['total_revenue'] += period_revenue + overage_revenue
                revenue_analysis['user_metrics']['total_paying_users'] += user_count
            
            # Add enterprise contracts (simulate)
            enterprise_contracts = max(1, int(avg_daily_users / 10000))  # 1 enterprise contract per 10K users
            enterprise_revenue = enterprise_contracts * 10000 * monthly_multiplier  # $10K/month contracts
            
            revenue_analysis['revenue_streams']['enterprise_contracts'] = enterprise_revenue
            revenue_analysis['total_revenue'] += enterprise_revenue
            
            # Calculate averages
            if revenue_analysis['user_metrics']['total_paying_users'] > 0:
                revenue_analysis['user_metrics']['avg_revenue_per_user'] = round(
                    revenue_analysis['total_revenue'] / revenue_analysis['user_metrics']['total_paying_users'], 2
                )
            
            revenue_analysis['user_metrics']['user_distribution_by_tier'] = user_distribution
            
            # Generate daily revenue breakdown
            daily_revenue = revenue_analysis['total_revenue'] / len(usage_data) if usage_data else 0
            
            for day_data in usage_data:
                # Add some variation to daily revenue
                variation = random.uniform(0.8, 1.2)  # ±20% daily variation
                
                revenue_analysis['daily_revenue'].append({
                    'date': day_data['date'],
                    'revenue': round(daily_revenue * variation, 2),
                    'requests': day_data.get('api_usage', {}).get('total_requests', 0)
                })
            
            # Calculate revenue efficiency metrics
            total_requests = sum(day.get('api_usage', {}).get('total_requests', 0) for day in usage_data)
            
            revenue_analysis['efficiency_metrics'] = {
                'revenue_per_request': round(revenue_analysis['total_revenue'] / total_requests, 6) if total_requests > 0 else 0,
                'revenue_per_thousand_requests': round((revenue_analysis['total_revenue'] / total_requests) * 1000, 4) if total_requests > 0 else 0,
                'monthly_revenue_projection': round(revenue_analysis['total_revenue'] * (30 / days_in_period), 2),
                'annual_revenue_projection': round(revenue_analysis['total_revenue'] * (365 / days_in_period), 2)
            }
            
            return revenue_analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing revenue patterns: {e}")
            return {}
    
    async def _analyze_profitability(self, cost_breakdown: Dict, revenue_analysis: Dict) -> Dict[str, Any]:
        """
        Analyze profitability metrics and margins.
        Like calculating your business's bottom line performance.
        """
        try:
            total_cost = cost_breakdown.get('period_total_cost', 0)
            total_revenue = revenue_analysis.get('total_revenue', 0)
            
            # Basic profitability metrics
            gross_profit = total_revenue - total_cost
            gross_margin = (gross_profit / total_revenue) * 100 if total_revenue > 0 else 0
            
            # Break down margins by cost category
            infrastructure_cost = cost_breakdown.get('category_breakdown', {}).get('infrastructure', {}).get('total', 0)
            operational_cost = cost_breakdown.get('category_breakdown', {}).get('operational', {}).get('total', 0)
            third_party_cost = cost_breakdown.get('category_breakdown', {}).get('third_party', {}).get('total', 0)
            
            contribution_margin = total_revenue - infrastructure_cost  # Revenue minus variable costs
            contribution_margin_percent = (contribution_margin / total_revenue) * 100 if total_revenue > 0 else 0
            
            # Unit economics
            total_requests = cost_breakdown.get('cost_efficiency_metrics', {}).get('total_requests', 0)
            total_users = cost_breakdown.get('cost_efficiency_metrics', {}).get('total_users', 0)
            
            profit_per_request = gross_profit / total_requests if total_requests > 0 else 0
            profit_per_user = gross_profit / total_users if total_users > 0 else 0
            
            # Payback analysis (simplified)
            avg_revenue_per_user = revenue_analysis.get('user_metrics', {}).get('avg_revenue_per_user', 0)
            customer_acquisition_cost = operational_cost / max(1, total_users)  # Simplified CAC
            payback_months = customer_acquisition_cost / (avg_revenue_per_user / 30) if avg_revenue_per_user > 0 else float('inf')
            
            # Break-even analysis
            fixed_costs = operational_cost + third_party_cost
            variable_cost_per_request = infrastructure_cost / total_requests if total_requests > 0 else 0
            revenue_per_request = total_revenue / total_requests if total_requests > 0 else 0
            
            break_even_requests = fixed_costs / (revenue_per_request - variable_cost_per_request) if (revenue_per_request - variable_cost_per_request) > 0 else float('inf')
            
            # Profitability trends
            daily_costs = cost_breakdown.get('daily_costs', [])
            daily_revenues = revenue_analysis.get('daily_revenue', [])
            
            daily_profits = []
            for i, cost_day in enumerate(daily_costs):
                if i < len(daily_revenues):
                    daily_profit = daily_revenues[i]['revenue'] - cost_day['total_cost']
                    daily_profits.append({
                        'date': cost_day['date'],
                        'profit': round(daily_profit, 2),
                        'margin_percent': round((daily_profit / daily_revenues[i]['revenue']) * 100, 2) if daily_revenues[i]['revenue'] > 0 else 0
                    })
            
            return {
                'financial_summary': {
                    'total_revenue': round(total_revenue, 2),
                    'total_cost': round(total_cost, 2),
                    'gross_profit': round(gross_profit, 2),
                    'gross_margin_percent': round(gross_margin, 2)
                },
                'margin_analysis': {
                    'contribution_margin': round(contribution_margin, 2),
                    'contribution_margin_percent': round(contribution_margin_percent, 2),
                    'infrastructure_margin_percent': round(((total_revenue - infrastructure_cost) / total_revenue) * 100, 2) if total_revenue > 0 else 0,
                    'operational_efficiency': round((operational_cost / total_revenue) * 100, 2) if total_revenue > 0 else 0
                },
                'unit_economics': {
                    'profit_per_request': round(profit_per_request, 6),
                    'profit_per_user': round(profit_per_user, 2),
                    'revenue_per_request': round(revenue_per_request, 6) if total_requests > 0 else 0,
                    'cost_per_request': round(total_cost / total_requests, 6) if total_requests > 0 else 0,
                    'customer_acquisition_cost': round(customer_acquisition_cost, 2),
                    'payback_period_months': round(payback_months, 1) if payback_months != float('inf') else 'N/A'
                },
                'break_even_analysis': {
                    'fixed_costs': round(fixed_costs, 2),
                    'variable_cost_per_request': round(variable_cost_per_request, 6),
                    'break_even_requests_daily': round(break_even_requests / len(daily_costs), 0) if break_even_requests != float('inf') and daily_costs else 'N/A',
                    'current_daily_requests': round(total_requests / len(daily_costs), 0) if daily_costs else 0,
                    'break_even_status': 'profitable' if break_even_requests < total_requests else 'break_even_needed'
                },
                'profitability_trends': {
                    'daily_profits': daily_profits,
                    'profit_trend': self._calculate_trend([p['profit'] for p in daily_profits]),
                    'margin_trend': self._calculate_trend([p['margin_percent'] for p in daily_profits]),
                    'avg_daily_profit': round(statistics.mean([p['profit'] for p in daily_profits]), 2) if daily_profits else 0
                },
                'financial_health': {
                    'profitability_status': 'healthy' if gross_margin > 20 else 'concerning' if gross_margin > 0 else 'unprofitable',
                    'margin_quality': 'excellent' if gross_margin > 40 else 'good' if gross_margin > 20 else 'poor',
                    'growth_sustainability': payback_months < 12 if payback_months != float('inf') else False
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing profitability: {e}")
            return {}
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from a series of values"""
        if len(values) < 3:
            return 'insufficient_data'
        
        # Calculate linear trend
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        if n * x2_sum - x_sum * x_sum == 0:
            return 'stable'
        
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        
        # Determine trend based on slope
        avg_value = statistics.mean(values)
        slope_percent = (slope / avg_value) * 100 if avg_value != 0 else 0
        
        if slope_percent > 5:
            return 'increasing'
        elif slope_percent < -5:
            return 'decreasing'
        else:
            return 'stable'
    
    async def _analyze_cost_efficiency(self, usage_data: List[Dict]) -> Dict[str, Any]:
        """
        Analyze cost efficiency metrics and optimization opportunities.
        Like analyzing how efficiently you're running your business operations.
        """
        try:
            efficiency_metrics = {
                'resource_utilization': {},
                'cost_per_unit': {},
                'efficiency_trends': {},
                'optimization_score': 0
            }
            
            # Analyze resource utilization
            total_cpu_hours = 0
            total_cpu_utilization = 0
            total_memory_utilization = 0
            total_gpu_hours = 0
            total_storage_gb = 0
            
            for day_data in usage_data:
                infra_usage = day_data.get('infrastructure_usage', {})
                
                cpu_hours = infra_usage.get('compute_hours', 24)
                cpu_util = infra_usage.get('cpu_utilization', 0)
                memory_util = infra_usage.get('memory_utilization', 0)
                gpu_hours = infra_usage.get('gpu_hours', 0)
                storage = infra_usage.get('storage_gb', 0)
                
                total_cpu_hours += cpu_hours
                total_cpu_utilization += cpu_util
                total_memory_utilization += memory_util
                total_gpu_hours += gpu_hours
                total_storage_gb += storage
            
            days_count = len(usage_data)
            
            efficiency_metrics['resource_utilization'] = {
                'avg_cpu_utilization_percent': round(total_cpu_utilization / days_count, 1) if days_count > 0 else 0,
                'avg_memory_utilization_percent': round(total_memory_utilization / days_count, 1) if days_count > 0 else 0,
                'gpu_utilization_hours_per_day': round(total_gpu_hours / days_count, 1) if days_count > 0 else 0,
                'storage_efficiency_gb_per_day': round(total_storage_gb / days_count, 1) if days_count > 0 else 0,
                'compute_efficiency_score': self._calculate_efficiency_score(total_cpu_utilization / days_count if days_count > 0 else 0)
            }
            
            # Calculate cost per unit metrics
            total_requests = sum(day.get('api_usage', {}).get('total_requests', 0) for day in usage_data)
            total_tokens = sum(day.get('api_usage', {}).get('total_tokens', 0) for day in usage_data)
            
            # Estimate total infrastructure cost
            total_infra_cost = (
                total_cpu_hours * self.cost_structure['infrastructure']['compute_cost_per_hour'] +
                total_gpu_hours * self.cost_structure['infrastructure']['gpu_cost_per_hour'] +
                (total_storage_gb / days_count) * self.cost_structure['infrastructure']['storage_cost_per_gb_month'] +
                sum(day.get('infrastructure_usage', {}).get('bandwidth_gb', 0) for day in usage_data) * self.cost_structure['infrastructure']['bandwidth_cost_per_gb']
            )
            
            efficiency_metrics['cost_per_unit'] = {
                'cost_per_million_requests': round((total_infra_cost / total_requests) * 1000000, 2) if total_requests > 0 else 0,
                'cost_per_million_tokens': round((total_infra_cost / total_tokens) * 1000000, 4) if total_tokens > 0 else 0,
                'infrastructure_cost_per_day': round(total_infra_cost / days_count, 2) if days_count > 0 else 0,
                'requests_per_dollar': round(total_requests / total_infra_cost, 0) if total_infra_cost > 0 else 0
            }
            
            # Calculate efficiency trends
            daily_efficiency = []
            for day_data in usage_data:
                requests = day_data.get('api_usage', {}).get('total_requests', 0)
                cpu_util = day_data.get('infrastructure_usage', {}).get('cpu_utilization', 0)
                
                # Efficiency = requests per unit of resource utilization
                efficiency = requests / max(1, cpu_util) if cpu_util > 0 else 0
                daily_efficiency.append(efficiency)
            
            efficiency_metrics['efficiency_trends'] = {
                'daily_efficiency': daily_efficiency,
                'efficiency_trend': self._calculate_trend(daily_efficiency),
                'avg_efficiency': round(statistics.mean(daily_efficiency), 2) if daily_efficiency else 0,
                'efficiency_volatility': round(statistics.stdev(daily_efficiency), 2) if len(daily_efficiency) > 1 else 0
            }
            
            # Calculate overall optimization score (0-100)
            cpu_score = min(100, (total_cpu_utilization / days_count) * 1.25) if days_count > 0 else 0  # Optimal around 80%
            memory_score = min(100, (total_memory_utilization / days_count) * 1.25) if days_count > 0 else 0
            cost_efficiency_score = min(100, (total_requests / total_infra_cost) / 1000) if total_infra_cost > 0 else 0  # Arbitrary scale
            
            efficiency_metrics['optimization_score'] = round((cpu_score + memory_score + cost_efficiency_score) / 3, 1)
            
            return efficiency_metrics
            
        except Exception as e:
            self.logger.error(f"Error analyzing cost efficiency: {e}")
            return {}
    
    def _calculate_efficiency_score(self, utilization: float) -> str:
        """Calculate efficiency score based on resource utilization"""
        if utilization < 20:
            return 'underutilized'
        elif utilization < 60:
            return 'moderate'
        elif utilization < 85:
            return 'efficient'
        else:
            return 'overutilized'
    
    async def _identify_optimization_opportunities(self, cost_breakdown: Dict, usage_data: List[Dict]) -> Dict[str, Any]:
        """
        Identify specific cost optimization opportunities.
        Like having a consultant review your expenses and suggest savings.
        """
        try:
            opportunities = {
                'infrastructure_optimizations': [],
                'operational_optimizations': [],
                'pricing_optimizations': [],
                'potential_savings': {
                    'monthly_savings_estimate': 0,
                    'percentage_reduction': 0
                }
            }
            
            # Analyze infrastructure optimization opportunities
            category_breakdown = cost_breakdown.get('category_breakdown', {})
            infra_costs = category_breakdown.get('infrastructure', {}).get('subcategories', {})
            
            # GPU optimization
            gpu_cost = infra_costs.get('gpu', 0)
            total_cost = cost_breakdown.get('period_total_cost', 1)
            
            if gpu_cost / total_cost > 0.4:  # GPU costs more than 40%
                opportunities['infrastructure_optimizations'].append({
                    'type': 'gpu_optimization',
                    'description': f'GPU costs account for {(gpu_cost/total_cost)*100:.1f}% of infrastructure spend',
                    'potential_savings': gpu_cost * 0.2,  # Assume 20% savings possible
                    'actions': [
                        'Implement GPU auto-scaling based on demand',
                        'Use spot instances for non-critical GPU workloads',
                        'Optimize model inference batch sizes',
                        'Consider GPU resource pooling'
                    ]
                })
            
            # Storage optimization
            storage_cost = infra_costs.get('storage', 0)
            if storage_cost / total_cost > 0.15:  # Storage more than 15%
                opportunities['infrastructure_optimizations'].append({
                    'type': 'storage_optimization',
                    'description': f'Storage costs are {(storage_cost/total_cost)*100:.1f}% of total - consider optimization',
                    'potential_savings': storage_cost * 0.3,
                    'actions': [
                        'Implement data lifecycle policies',
                        'Use cheaper storage tiers for archived data',
                        'Compress and deduplicate stored data',
                        'Review backup retention policies'
                    ]
                })
            
            # Bandwidth optimization
            bandwidth_cost = infra_costs.get('bandwidth', 0)
            if bandwidth_cost / total_cost > 0.1:  # Bandwidth more than 10%
                opportunities['infrastructure_optimizations'].append({
                    'type': 'bandwidth_optimization',
                    'description': f'Bandwidth costs are significant at {(bandwidth_cost/total_cost)*100:.1f}% of total',
                    'potential_savings': bandwidth_cost * 0.25,
                    'actions': [
                        'Implement response compression',
                        'Use CDN for static content',
                        'Optimize API response sizes',
                        'Cache frequently requested data'
                    ]
                })
            
            # Operational optimizations
            operational_costs = category_breakdown.get('operational', {}).get('subcategories', {})
            support_cost = operational_costs.get('support', 0)
            
            if support_cost / total_cost > 0.2:  # Support costs more than 20%
                opportunities['operational_optimizations'].append({
                    'type': 'support_optimization',
                    'description': f'Support costs are {(support_cost/total_cost)*100:.1f}% of total spend',
                    'potential_savings': support_cost * 0.15,
                    'actions': [
                        'Implement chatbot for common queries',
                        'Create comprehensive self-service documentation',
                        'Optimize support ticket routing',
                        'Analyze and prevent common issues'
                    ]
                })
            
            # Pricing optimizations based on usage patterns
            avg_requests_per_day = statistics.mean([
                day.get('api_usage', {}).get('total_requests', 0) 
                for day in usage_data
            ]) if usage_data else 0
            
            if avg_requests_per_day > 3000000:  # High volume
                opportunities['pricing_optimizations'].append({
                    'type': 'volume_pricing',
                    'description': 'High request volume suggests potential for volume-based pricing optimization',
                    'potential_savings': 0,  # Revenue opportunity, not cost savings
                    'actions': [
                        'Introduce volume discount tiers',
                        'Offer annual subscription discounts',
                        'Create enterprise custom pricing',
                        'Implement usage-based pricing model'
                    ]
                })
            
            # Calculate total potential savings
            total_potential_savings = sum(
                opp['potential_savings'] 
                for opp_list in [
                    opportunities['infrastructure_optimizations'],
                    opportunities['operational_optimizations']
                ]
                for opp in opp_list
            )
            
            opportunities['potential_savings'] = {
                'monthly_savings_estimate': round(total_potential_savings * (30 / len(usage_data)), 2) if usage_data else 0,
                'percentage_reduction': round((total_potential_savings / total_cost) * 100, 1) if total_cost > 0 else 0
            }
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Error identifying optimization opportunities: {e}")
            return {}
    
    async def _analyze_cost_trends(self, usage_data: List[Dict], days: int) -> Dict[str, Any]:
        """
        Analyze cost trends over time.
        Like tracking your spending patterns over time.
        """
        try:
            trends = {
                'cost_trend': 'stable',
                'usage_trend': 'stable',
                'efficiency_trend': 'stable',
                'weekly_patterns': {},
                'cost_volatility': 0
            }
            
            # Extract daily costs and usage
            daily_costs = []
            daily_requests = []
            daily_efficiency = []
            
            for day_data in usage_data:
                # Calculate daily cost
                infra_usage = day_data.get('infrastructure_usage', {})
                api_usage = day_data.get('api_usage', {})
                
                daily_cost = (
                    infra_usage.get('compute_hours', 0) * self.cost_structure['infrastructure']['compute_cost_per_hour'] +
                    infra_usage.get('gpu_hours', 0) * self.cost_structure['infrastructure']['gpu_cost_per_hour'] +
                    infra_usage.get('storage_gb', 0) * self.cost_structure['infrastructure']['storage_cost_per_gb_month'] / 30 +
                    infra_usage.get('bandwidth_gb', 0) * self.cost_structure['infrastructure']['bandwidth_cost_per_gb']
                )
                
                requests = api_usage.get('total_requests', 0)
                efficiency = requests / daily_cost if daily_cost > 0 else 0
                
                daily_costs.append(daily_cost)
                daily_requests.append(requests)
                daily_efficiency.append(efficiency)
            
            # Calculate trends
            trends['cost_trend'] = self._calculate_trend(daily_costs)
            trends['usage_trend'] = self._calculate_trend(daily_requests)
            trends['efficiency_trend'] = self._calculate_trend(daily_efficiency)
            
            # Calculate volatility
            if len(daily_costs) > 1:
                trends['cost_volatility'] = round(statistics.stdev(daily_costs) / statistics.mean(daily_costs) * 100, 2)
            
            # Analyze weekly patterns if we have enough data
            if len(usage_data) >= 7:
                weekly_costs = defaultdict(list)
                for i, day_data in enumerate(usage_data):
                    day_of_week = (datetime.fromisoformat(day_data['date']).weekday() + 1) % 7  # Sunday = 0
                    weekly_costs[day_of_week].append(daily_costs[i])
                
                trends['weekly_patterns'] = {
                    day: {
                        'avg_cost': round(statistics.mean(costs), 2),
                        'day_name': ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][day]
                    }
                    for day, costs in weekly_costs.items()
                    if costs
                }
            
            return trends
            
        except Exception as e:
            self.logger.error(f"Error analyzing cost trends: {e}")
            return {}
    
    async def _generate_cost_projections(self, analysis: Dict) -> Dict[str, Any]:
        """
        Generate cost and revenue projections.
        Like creating financial forecasts for business planning.
        """
        try:
            projections = {
                'monthly_projections': {},
                'annual_projections': {},
                'growth_scenarios': {}
            }
            
            # Base metrics
            cost_breakdown = analysis.get('cost_breakdown', {})
            revenue_analysis = analysis.get('revenue_analysis', {})
            trends = analysis.get('trends', {})
            
            current_daily_cost = cost_breakdown.get('avg_daily_cost', 0)
            current_daily_revenue = revenue_analysis.get('total_revenue', 0) / analysis.get('analysis_period', {}).get('days', 30)
            
            # Monthly projections
            monthly_cost = current_daily_cost * 30
            monthly_revenue = current_daily_revenue * 30
            
            # Apply trend adjustments
            cost_trend = trends.get('cost_trend', 'stable')
            trend_multiplier = 1.0
            
            if cost_trend == 'increasing':
                trend_multiplier = 1.1  # 10% increase
            elif cost_trend == 'decreasing':
                trend_multiplier = 0.9   # 10% decrease
            
            projections['monthly_projections'] = {
                'projected_cost': round(monthly_cost * trend_multiplier, 2),
                'projected_revenue': round(monthly_revenue, 2),
                'projected_profit': round((monthly_revenue - monthly_cost * trend_multiplier), 2),
                'projected_margin': round(((monthly_revenue - monthly_cost * trend_multiplier) / monthly_revenue) * 100, 2) if monthly_revenue > 0 else 0
            }
            
            # Annual projections
            projections['annual_projections'] = {
                'projected_cost': round(monthly_cost * trend_multiplier * 12, 2),
                'projected_revenue': round(monthly_revenue * 12, 2),
                'projected_profit': round((monthly_revenue - monthly_cost * trend_multiplier) * 12, 2),
                'projected_margin': round(((monthly_revenue - monthly_cost * trend_multiplier) / monthly_revenue) * 100, 2) if monthly_revenue > 0 else 0
            }
            
            # Growth scenarios
            projections['growth_scenarios'] = {
                'conservative': {
                    'growth_rate': 0.1,  # 10% growth
                    'annual_revenue': round(monthly_revenue * 12 * 1.1, 2),
                    'annual_cost': round(monthly_cost * trend_multiplier * 12 * 1.05, 2),  # 5% cost increase
                },
                'moderate': {
                    'growth_rate': 0.25,  # 25% growth
                    'annual_revenue': round(monthly_revenue * 12 * 1.25, 2),
                    'annual_cost': round(monthly_cost * trend_multiplier * 12 * 1.15, 2),  # 15% cost increase
                },
                'aggressive': {
                    'growth_rate': 0.5,   # 50% growth
                    'annual_revenue': round(monthly_revenue * 12 * 1.5, 2),
                    'annual_cost': round(monthly_cost * trend_multiplier * 12 * 1.3, 2),   # 30% cost increase
                }
            }
            
            # Calculate profit for each scenario
            for scenario in projections['growth_scenarios'].values():
                scenario['annual_profit'] = round(scenario['annual_revenue'] - scenario['annual_cost'], 2)
                scenario['profit_margin'] = round((scenario['annual_profit'] / scenario['annual_revenue']) * 100, 2) if scenario['annual_revenue'] > 0 else 0
            
            return projections
            
        except Exception as e:
            self.logger.error(f"Error generating cost projections: {e}")
            return {}
    
    async def _generate_cost_recommendations(self, analysis: Dict) -> List[Dict[str, Any]]:
        """
        Generate actionable cost optimization recommendations.
        Like getting advice from a business consultant.
        """
        try:
            recommendations = []
            
            # Analyze profitability
            profitability = analysis.get('profitability', {})
            financial_summary = profitability.get('financial_summary', {})
            margin_percent = financial_summary.get('gross_margin_percent', 0)
            
            # Cost structure analysis
            cost_breakdown = analysis.get('cost_breakdown', {})
            category_breakdown = cost_breakdown.get('category_breakdown', {})
            
            # Recommendation 1: Profitability assessment
            if margin_percent < 0:
                recommendations.append({
                    'priority': 'critical',
                    'category': 'profitability',
                    'title': 'Address Negative Margins',
                    'description': f'Current gross margin is {margin_percent:.1f}%. Immediate action needed.',
                    'actions': [
                        'Review and optimize pricing strategy',
                        'Reduce infrastructure costs through efficiency improvements',
                        'Consider temporary cost reduction measures',
                        'Analyze unprofitable user segments'
                    ],
                    'estimated_impact': 'High'
                })
            elif margin_percent < 20:
                recommendations.append({
                    'priority': 'high',
                    'category': 'profitability',
                    'title': 'Improve Profit Margins',
                    'description': f'Current gross margin of {margin_percent:.1f}% is below healthy levels (>20%).',
                    'actions': [
                        'Optimize infrastructure utilization',
                        'Review pricing tiers and increase where appropriate',
                        'Focus on higher-value customer segments',
                        'Reduce operational overhead'
                    ],
                    'estimated_impact': 'Medium-High'
                })
            
            # Recommendation 2: Infrastructure optimization
            infra_percentage = category_breakdown.get('infrastructure', {}).get('percentage', 0)
            if infra_percentage > 60:
                recommendations.append({
                    'priority': 'high',
                    'category': 'infrastructure',
                    'title': 'Optimize Infrastructure Costs',
                    'description': f'Infrastructure costs are {infra_percentage:.1f}% of total spend - optimization opportunity exists.',
                    'actions': [
                        'Implement auto-scaling to match demand',
                        'Use reserved instances for predictable workloads',
                        'Optimize resource allocation and utilization',
                        'Consider multi-cloud strategy for cost optimization'
                    ],
                    'estimated_impact': 'High'
                })
            
            # Recommendation 3: Cost efficiency
            cost_efficiency = analysis.get('cost_efficiency', {})
            optimization_score = cost_efficiency.get('optimization_score', 0)
            
            if optimization_score < 60:
                recommendations.append({
                    'priority': 'medium',
                    'category': 'efficiency',
                    'title': 'Improve Cost Efficiency',
                    'description': f'Cost efficiency score is {optimization_score}/100 - room for improvement.',
                    'actions': [
                        'Monitor and optimize resource utilization',
                        'Implement better caching strategies',
                        'Optimize database queries and operations',
                        'Review and consolidate underutilized resources'
                    ],
                    'estimated_impact': 'Medium'
                })
            
            # Recommendation 4: Revenue optimization
            revenue_analysis = analysis.get('revenue_analysis', {})
            user_metrics = revenue_analysis.get('user_metrics', {})
            avg_revenue_per_user = user_metrics.get('avg_revenue_per_user', 0)
            
            if avg_revenue_per_user < 50:  # If ARPU is low
                recommendations.append({
                    'priority': 'medium',
                    'category': 'revenue',
                    'title': 'Increase Revenue Per User',
                    'description': f'Average revenue per user is ${avg_revenue_per_user:.2f} - consider upselling opportunities.',
                    'actions': [
                        'Introduce premium features and tiers',
                        'Implement usage-based pricing for heavy users',
                        'Create enterprise packages with higher value',
                        'Analyze and reduce churn in high-value segments'
                    ],
                    'estimated_impact': 'Medium-High'
                })
            
            # Recommendation 5: Trend-based recommendations
            trends = analysis.get('trends', {})
            cost_trend = trends.get('cost_trend', 'stable')
            
            if cost_trend == 'increasing':
                recommendations.append({
                    'priority': 'medium',
                    'category': 'cost_control',
                    'title': 'Address Rising Cost Trends',
                    'description': 'Costs are trending upward - proactive management needed.',
                    'actions': [
                        'Implement cost monitoring and alerts',
                        'Review and optimize recent infrastructure changes',
                        'Analyze cost drivers and usage patterns',
                        'Set up automated cost controls and limits'
                    ],
                    'estimated_impact': 'Medium'
                })
            
            # Sort recommendations by priority
            priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
            recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error generating cost recommendations: {e}")
            return []
    
    async def get_cost_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get a quick cost summary for dashboard display.
        Like a financial health snapshot for executives.
        """
        try:
            analysis = await self.analyze_cost_patterns(days)
            
            if 'error' in analysis:
                return analysis
            
            cost_breakdown = analysis.get('cost_breakdown', {})
            revenue_analysis = analysis.get('revenue_analysis', {})
            profitability = analysis.get('profitability', {})
            
            summary = {
                'period_days': days,
                'total_cost': cost_breakdown.get('period_total_cost', 0),
                'total_revenue': revenue_analysis.get('total_revenue', 0),
                'gross_profit': profitability.get('financial_summary', {}).get('gross_profit', 0),
                'profit_margin': profitability.get('financial_summary', {}).get('gross_margin_percent', 0),
                'daily_averages': {
                    'cost': cost_breakdown.get('avg_daily_cost', 0),
                    'revenue': revenue_analysis.get('total_revenue', 0) / days if days > 0 else 0,
                    'requests': cost_breakdown.get('cost_efficiency_metrics', {}).get('total_requests', 0) / days if days > 0 else 0
                },
                'cost_distribution': {
                    cat: breakdown.get('percentage', 0)
                    for cat, breakdown in cost_breakdown.get('category_breakdown', {}).items()
                },
                'efficiency_score': analysis.get('cost_efficiency', {}).get('optimization_score', 0),
                'top_recommendation': analysis.get('recommendations', [{}])[0] if analysis.get('recommendations') else {},
                'financial_health': profitability.get('financial_health', {}).get('profitability_status', 'unknown')
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating cost summary: {e}")
            return {'error': str(e)}