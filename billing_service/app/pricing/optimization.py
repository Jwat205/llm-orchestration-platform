"""
Pricing Optimization Engine
Analyzes usage patterns and provides cost optimization recommendations
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import numpy as np
from collections import defaultdict
import logging

from .calculator import PricingCalculator, PricingTier, ModelPricing

logger = logging.getLogger(__name__)


class UsagePattern:
    """Represents usage patterns for analysis"""
    
    def __init__(self, data: List[Dict]):
        self.data = data
        self._analyze_patterns()
    
    def _analyze_patterns(self):
        """Analyze usage patterns from raw data"""
        # Group by hour of day
        hourly_usage = defaultdict(list)
        daily_usage = defaultdict(list)
        model_usage = defaultdict(int)
        
        for record in self.data:
            timestamp = record.get("timestamp")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            hour = timestamp.hour
            day = timestamp.date()
            
            tokens = record.get("total_tokens", 0)
            model = record.get("model", "unknown")
            
            hourly_usage[hour].append(tokens)
            daily_usage[day].append(tokens)
            model_usage[model] += tokens
        
        # Calculate statistics
        self.hourly_avg = {
            hour: np.mean(usage) if usage else 0 
            for hour, usage in hourly_usage.items()
        }
        self.hourly_peak = {
            hour: np.max(usage) if usage else 0 
            for hour, usage in hourly_usage.items()
        }
        
        self.daily_totals = {
            day: sum(usage) for day, usage in daily_usage.items()
        }
        self.model_distribution = dict(model_usage)
        
        # Calculate percentiles for capacity planning
        all_daily_totals = list(self.daily_totals.values())
        if all_daily_totals:
            self.daily_p50 = np.percentile(all_daily_totals, 50)
            self.daily_p95 = np.percentile(all_daily_totals, 95)
            self.daily_p99 = np.percentile(all_daily_totals, 99)
        else:
            self.daily_p50 = self.daily_p95 = self.daily_p99 = 0


class PricingOptimizer:
    """Optimizes pricing and tier selection based on usage patterns"""
    
    def __init__(self):
        self.calculator = PricingCalculator()
        self.model_pricing = ModelPricing()
    
    def analyze_cost_optimization(
        self,
        customer_id: str,
        usage_history: List[Dict],
        current_tier: PricingTier,
        lookback_days: int = 30
    ) -> Dict[str, any]:
        """
        Analyze usage and provide cost optimization recommendations
        
        Args:
            customer_id: Customer identifier
            usage_history: List of usage records
            current_tier: Current subscription tier
            lookback_days: Days of history to analyze
            
        Returns:
            Comprehensive cost optimization analysis
        """
        # Analyze usage patterns
        patterns = UsagePattern(usage_history)
        
        # Calculate current costs
        current_costs = self._calculate_period_costs(
            usage_history, 
            current_tier,
            lookback_days
        )
        
        # Find optimization opportunities
        optimizations = []
        
        # 1. Model optimization
        model_optimization = self._optimize_model_selection(patterns, current_tier)
        if model_optimization["potential_savings"] > 0:
            optimizations.append(model_optimization)
        
        # 2. Tier optimization
        tier_optimization = self._optimize_tier_selection(patterns, current_tier)
        if tier_optimization["potential_savings"] > 0:
            optimizations.append(tier_optimization)
        
        # 3. Usage timing optimization
        timing_optimization = self._optimize_usage_timing(patterns)
        if timing_optimization["potential_savings"] > 0:
            optimizations.append(timing_optimization)
        
        # 4. Feature usage optimization
        feature_optimization = self._optimize_feature_usage(usage_history)
        if feature_optimization["potential_savings"] > 0:
            optimizations.append(feature_optimization)
        
        # Sort by potential savings
        optimizations.sort(key=lambda x: x["potential_savings"], reverse=True)
        
        # Calculate total potential savings
        total_potential_savings = sum(opt["potential_savings"] for opt in optimizations)
        
        return {
            "customer_id": customer_id,
            "analysis_period": {
                "days": lookback_days,
                "start": (datetime.utcnow() - timedelta(days=lookback_days)).isoformat(),
                "end": datetime.utcnow().isoformat(),
            },
            "current_costs": current_costs,
            "usage_patterns": {
                "daily_average": float(np.mean(list(patterns.daily_totals.values()))),
                "daily_p95": float(patterns.daily_p95),
                "peak_hour": max(patterns.hourly_avg.items(), key=lambda x: x[1])[0] if patterns.hourly_avg else None,
                "model_distribution": patterns.model_distribution,
            },
            "optimizations": optimizations,
            "total_potential_savings": total_potential_savings,
            "savings_percentage": (total_potential_savings / current_costs["total_cost"] * 100) if current_costs["total_cost"] > 0 else 0,
            "implementation_priority": self._prioritize_optimizations(optimizations),
        }
    
    def forecast_costs(
        self,
        customer_id: str,
        usage_history: List[Dict],
        current_tier: PricingTier,
        forecast_days: int = 30,
        growth_rate: float = 0.0
    ) -> Dict[str, any]:
        """
        Forecast future costs based on historical patterns
        
        Args:
            customer_id: Customer identifier
            usage_history: Historical usage data
            current_tier: Current subscription tier
            forecast_days: Days to forecast
            growth_rate: Expected growth rate (e.g., 0.1 for 10% growth)
            
        Returns:
            Cost forecast with confidence intervals
        """
        patterns = UsagePattern(usage_history)
        
        # Calculate base forecast
        daily_avg = np.mean(list(patterns.daily_totals.values()))
        daily_std = np.std(list(patterns.daily_totals.values()))
        
        # Apply growth rate
        growth_factor = 1 + growth_rate
        projected_daily_avg = daily_avg * growth_factor
        projected_daily_std = daily_std * growth_factor
        
        # Calculate forecast with confidence intervals
        forecast_total = projected_daily_avg * forecast_days
        forecast_low = (projected_daily_avg - 2 * projected_daily_std) * forecast_days
        forecast_high = (projected_daily_avg + 2 * projected_daily_std) * forecast_days
        
        # Calculate costs for each scenario
        tier_config = self.calculator.tier_config.TIER_CONFIGS[current_tier]
        
        scenarios = {}
        for scenario_name, tokens in [
            ("expected", forecast_total),
            ("conservative", forecast_low),
            ("aggressive", forecast_high)
        ]:
            # Simplified cost calculation
            monthly_fee = float(tier_config.get("monthly_price", 0))
            included_tokens = tier_config.get("included_tokens", 0)
            
            if tokens <= included_tokens:
                total_cost = monthly_fee
            else:
                overage = tokens - included_tokens
                # Assume $1 per 1M tokens overage (simplified)
                overage_cost = overage * 0.000001 * 1000
                total_cost = monthly_fee + overage_cost
            
            scenarios[scenario_name] = {
                "tokens": int(tokens),
                "cost": round(total_cost, 2),
                "includes_overage": tokens > included_tokens,
            }
        
        # Recommend tier for expected usage
        recommended_tier = self._recommend_tier_for_usage(forecast_total)
        
        return {
            "customer_id": customer_id,
            "forecast_period": {
                "days": forecast_days,
                "start": datetime.utcnow().isoformat(),
                "end": (datetime.utcnow() + timedelta(days=forecast_days)).isoformat(),
            },
            "growth_rate": growth_rate,
            "current_tier": current_tier.value,
            "scenarios": scenarios,
            "recommendation": {
                "tier": recommended_tier.value,
                "reason": self._get_tier_recommendation_reason(
                    forecast_total,
                    current_tier,
                    recommended_tier
                ),
            },
            "confidence_level": self._calculate_forecast_confidence(patterns),
        }
    
    def get_cost_alerts(
        self,
        customer_id: str,
        current_usage: Dict[str, int],
        current_tier: PricingTier,
        billing_period_start: datetime,
        billing_period_end: datetime
    ) -> List[Dict]:
        """
        Generate cost alerts based on current usage trends
        
        Args:
            customer_id: Customer identifier
            current_usage: Current period usage by model
            current_tier: Current subscription tier
            billing_period_start: Start of current billing period
            billing_period_end: End of current billing period
            
        Returns:
            List of cost alerts
        """
        alerts = []
        
        # Calculate usage pace
        period_elapsed = (datetime.utcnow() - billing_period_start).total_seconds()
        period_total = (billing_period_end - billing_period_start).total_seconds()
        period_progress = period_elapsed / period_total if period_total > 0 else 0
        
        # Calculate total tokens used
        total_tokens = sum(
            usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            for usage in current_usage.values()
        )
        
        tier_config = self.calculator.tier_config.TIER_CONFIGS[current_tier]
        included_tokens = tier_config.get("included_tokens", 0)
        
        # Check usage pace
        if period_progress > 0:
            projected_total = total_tokens / period_progress
            usage_percentage = (total_tokens / included_tokens * 100) if included_tokens > 0 else 0
            
            # High usage alert
            if usage_percentage > 80 and period_progress < 0.8:
                alerts.append({
                    "type": "high_usage",
                    "severity": "warning",
                    "message": f"Token usage at {usage_percentage:.1f}% with {(1-period_progress)*100:.1f}% of billing period remaining",
                    "projected_overage": max(0, projected_total - included_tokens),
                    "recommendation": "Consider upgrading tier or optimizing usage",
                })
            
            # Projected overage alert
            if projected_total > included_tokens * 1.2:
                overage_cost = self._estimate_overage_cost(
                    projected_total - included_tokens,
                    current_tier
                )
                alerts.append({
                    "type": "projected_overage",
                    "severity": "warning",
                    "message": f"Projected to exceed included tokens by {((projected_total/included_tokens)-1)*100:.1f}%",
                    "projected_overage_cost": overage_cost,
                    "recommendation": "Review usage patterns and consider tier upgrade",
                })
        
        # Unusual usage patterns
        unusual_patterns = self._detect_unusual_usage(current_usage)
        for pattern in unusual_patterns:
            alerts.append({
                "type": "unusual_pattern",
                "severity": "info",
                "message": pattern["message"],
                "details": pattern["details"],
                "recommendation": pattern["recommendation"],
            })
        
        # Cost optimization opportunities
        if total_tokens > included_tokens * 0.5:
            alerts.append({
                "type": "optimization_available",
                "severity": "info",
                "message": "Cost optimization analysis available",
                "recommendation": "Run cost optimization analysis for potential savings",
            })
        
        return alerts
    
    def _calculate_period_costs(
        self,
        usage_history: List[Dict],
        tier: PricingTier,
        days: int
    ) -> Dict[str, float]:
        """Calculate costs for a period"""
        total_cost = Decimal("0")
        model_costs = defaultdict(Decimal)
        
        for record in usage_history:
            model = record.get("model", "unknown")
            cost_data = self.calculator.calculate_token_cost(
                model=model,
                input_tokens=record.get("input_tokens", 0),
                output_tokens=record.get("output_tokens", 0),
                features=record.get("features", []),
                tier=tier
            )
            
            total_cost += cost_data["total_cost"]
            model_costs[model] += cost_data["total_cost"]
        
        # Add subscription fee (prorated for period)
        tier_config = self.calculator.tier_config.TIER_CONFIGS[tier]
        monthly_fee = tier_config.get("monthly_price", Decimal("0"))
        period_fee = monthly_fee * Decimal(str(days / 30))
        
        return {
            "total_cost": float(total_cost + period_fee),
            "token_cost": float(total_cost),
            "subscription_fee": float(period_fee),
            "model_costs": {k: float(v) for k, v in model_costs.items()},
        }
    
    def _optimize_model_selection(
        self,
        patterns: UsagePattern,
        current_tier: PricingTier
    ) -> Dict[str, any]:
        """Optimize model selection for cost efficiency"""
        current_cost = Decimal("0")
        optimized_cost = Decimal("0")
        recommendations = []
        
        # Analyze each model's usage
        for model, tokens in patterns.model_distribution.items():
            if model not in self.model_pricing.MODEL_RATES:
                continue
            
            current_rates = self.model_pricing.MODEL_RATES[model]
            
            # Find cheaper alternatives
            for alt_model, alt_rates in self.model_pricing.MODEL_RATES.items():
                if alt_model == model:
                    continue
                
                # Check if alternative is cheaper
                if (alt_rates["input"] < current_rates["input"] and 
                    alt_rates["output"] < current_rates["output"]):
                    
                    # Estimate savings (simplified - assumes 50/50 input/output split)
                    current_model_cost = tokens * (current_rates["input"] + current_rates["output"]) / 2000
                    alt_model_cost = tokens * (alt_rates["input"] + alt_rates["output"]) / 2000
                    savings = current_model_cost - alt_model_cost
                    
                    if savings > 0:
                        recommendations.append({
                            "current_model": model,
                            "recommended_model": alt_model,
                            "tokens_affected": tokens,
                            "potential_savings": float(savings),
                            "savings_percentage": float((savings / current_model_cost) * 100),
                        })
        
        total_savings = sum(r["potential_savings"] for r in recommendations)
        
        return {
            "optimization_type": "model_selection",
            "potential_savings": total_savings,
            "recommendations": recommendations[:3],  # Top 3 recommendations
            "implementation_effort": "low",
            "description": "Switch to more cost-effective models for similar tasks",
        }
    
    def _optimize_tier_selection(
        self,
        patterns: UsagePattern,
        current_tier: PricingTier
    ) -> Dict[str, any]:
        """Optimize tier selection based on usage patterns"""
        monthly_tokens = sum(patterns.daily_totals.values())
        
        current_cost = self._estimate_monthly_cost(monthly_tokens, current_tier)
        optimal_tier = None
        optimal_cost = current_cost
        
        for tier in PricingTier:
            if tier == PricingTier.CUSTOM:
                continue
            
            tier_cost = self._estimate_monthly_cost(monthly_tokens, tier)
            if tier_cost < optimal_cost:
                optimal_cost = tier_cost
                optimal_tier = tier
        
        savings = current_cost - optimal_cost
        
        return {
            "optimization_type": "tier_selection",
            "potential_savings": float(savings),
            "current_tier": current_tier.value,
            "recommended_tier": optimal_tier.value if optimal_tier else current_tier.value,
            "monthly_tokens": monthly_tokens,
            "implementation_effort": "medium",
            "description": f"Switch from {current_tier.value} to {optimal_tier.value if optimal_tier else current_tier.value} tier",
        }
    
    def _optimize_usage_timing(self, patterns: UsagePattern) -> Dict[str, any]:
        """Optimize usage timing for potential discounts"""
        # This is a placeholder - in reality, you might offer off-peak discounts
        peak_hours = [9, 10, 11, 14, 15, 16]  # Business hours
        
        peak_usage = sum(
            patterns.hourly_avg.get(hour, 0) 
            for hour in peak_hours
        )
        total_usage = sum(patterns.hourly_avg.values())
        
        if total_usage > 0:
            peak_percentage = (peak_usage / total_usage) * 100
            
            # If more than 70% of usage is during peak hours, suggest optimization
            if peak_percentage > 70:
                potential_savings = total_usage * 0.1  # 10% discount for off-peak
                
                return {
                    "optimization_type": "usage_timing",
                    "potential_savings": float(potential_savings * 0.001),  # Convert to dollars
                    "peak_usage_percentage": peak_percentage,
                    "recommendation": "Shift non-critical workloads to off-peak hours",
                    "implementation_effort": "medium",
                    "description": "Optimize request timing to take advantage of off-peak rates",
                }
        
        return {
            "optimization_type": "usage_timing",
            "potential_savings": 0,
            "description": "Usage timing is already optimized",
        }
    
    def _optimize_feature_usage(self, usage_history: List[Dict]) -> Dict[str, any]:
        """Optimize feature usage for cost reduction"""
        feature_usage = defaultdict(int)
        feature_costs = defaultdict(Decimal)
        
        for record in usage_history:
            features = record.get("features", [])
            tokens = record.get("input_tokens", 0) + record.get("output_tokens", 0)
            
            for feature in features:
                feature_usage[feature] += tokens
                
                # Calculate cost impact of feature
                multiplier = self.model_pricing.FEATURE_MULTIPLIERS.get(feature, 1.0)
                if multiplier > 1.0:
                    # This feature adds cost
                    base_cost = tokens * 0.0001  # Simplified base rate
                    feature_cost = base_cost * (multiplier - 1.0)
                    feature_costs[feature] += Decimal(str(feature_cost))
        
        recommendations = []
        for feature, cost in feature_costs.items():
            if cost > 0:
                recommendations.append({
                    "feature": feature,
                    "tokens_affected": feature_usage[feature],
                    "additional_cost": float(cost),
                    "recommendation": f"Consider if {feature} is necessary for all requests",
                })
        
        total_savings = sum(feature_costs.values())
        
        return {
            "optimization_type": "feature_usage",
            "potential_savings": float(total_savings),
            "recommendations": sorted(
                recommendations, 
                key=lambda x: x["additional_cost"], 
                reverse=True
            )[:3],
            "implementation_effort": "low",
            "description": "Optimize usage of premium features",
        }
    
    def _prioritize_optimizations(self, optimizations: List[Dict]) -> List[Dict]:
        """Prioritize optimizations by impact and effort"""
        effort_scores = {"low": 1, "medium": 2, "high": 3}
        
        prioritized = []
        for opt in optimizations:
            effort = effort_scores.get(opt.get("implementation_effort", "medium"), 2)
            savings = opt.get("potential_savings", 0)
            
            # Calculate priority score (higher savings, lower effort = higher priority)
            priority_score = savings / effort
            
            prioritized.append({
                **opt,
                "priority_score": round(priority_score, 2),
                "priority_rank": None,  # Will be set after sorting
            })
        
        # Sort by priority score
        prioritized.sort(key=lambda x: x["priority_score"], reverse=True)
        
        # Assign ranks
        for i, opt in enumerate(prioritized):
            opt["priority_rank"] = i + 1
        
        return prioritized
    
    def _recommend_tier_for_usage(self, projected_tokens: int) -> PricingTier:
        """Recommend optimal tier for projected usage"""
        optimal_tier = PricingTier.FREE
        optimal_cost = float('inf')
        
        for tier in PricingTier:
            if tier == PricingTier.CUSTOM:
                continue
            
            cost = self._estimate_monthly_cost(projected_tokens, tier)
            if cost < optimal_cost:
                optimal_cost = cost
                optimal_tier = tier
        
        return optimal_tier
    
    def _estimate_monthly_cost(self, tokens: int, tier: PricingTier) -> float:
        """Estimate monthly cost for given tokens and tier"""
        tier_config = self.calculator.tier_config.TIER_CONFIGS[tier]
        monthly_fee = float(tier_config.get("monthly_price", 0))
        included_tokens = tier_config.get("included_tokens", 0)
        
        if tokens <= included_tokens:
            return monthly_fee
        
        # Calculate overage
        overage = tokens - included_tokens
        overage_discount = tier_config.get("overage_discount", 0)
        
        # Simplified overage rate (would be model-specific in reality)
        base_overage_rate = 0.001  # $1 per 1M tokens
        overage_rate = base_overage_rate * (1 - overage_discount)
        overage_cost = overage * overage_rate
        
        return monthly_fee + overage_cost
    
    def _estimate_overage_cost(self, overage_tokens: int, tier: PricingTier) -> float:
        """Estimate overage cost for given tokens"""
        tier_config = self.calculator.tier_config.TIER_CONFIGS[tier]
        overage_discount = tier_config.get("overage_discount", 0)
        
        # Simplified rate
        base_rate = 0.001  # $1 per 1M tokens
        discounted_rate = base_rate * (1 - overage_discount)
        
        return overage_tokens * discounted_rate
    
    def _get_tier_recommendation_reason(
        self,
        projected_tokens: int,
        current_tier: PricingTier,
        recommended_tier: PricingTier
    ) -> str:
        """Generate reason for tier recommendation"""
        if current_tier == recommended_tier:
            return "Current tier is optimal for projected usage"
        
        current_config = self.calculator.tier_config.TIER_CONFIGS[current_tier]
        recommended_config = self.calculator.tier_config.TIER_CONFIGS[recommended_tier]
        
        current_included = current_config.get("included_tokens", 0)
        recommended_included = recommended_config.get("included_tokens", 0)
        
        if projected_tokens > current_included and projected_tokens <= recommended_included:
            return f"Projected usage ({projected_tokens:,} tokens) exceeds current tier limit ({current_included:,} tokens)"
        elif recommended_tier.value < current_tier.value:
            return f"Projected usage ({projected_tokens:,} tokens) is well below current tier limit ({current_included:,} tokens)"
        else:
            return "Recommended tier offers better value for projected usage"
    
    def _calculate_forecast_confidence(self, patterns: UsagePattern) -> str:
        """Calculate confidence level for forecast"""
        if not patterns.daily_totals:
            return "low"
        
        # Calculate coefficient of variation
        daily_values = list(patterns.daily_totals.values())
        mean = np.mean(daily_values)
        std = np.std(daily_values)
        
        if mean > 0:
            cv = std / mean
            
            if cv < 0.3:
                return "high"
            elif cv < 0.6:
                return "medium"
            else:
                return "low"
        
        return "low"
    
    def _detect_unusual_usage(self, current_usage: Dict[str, Dict]) -> List[Dict]:
        """Detect unusual usage patterns"""
        unusual_patterns = []
        
        # Check for unusual model combinations
        models_used = set(current_usage.keys())
        if len(models_used) > 5:
            unusual_patterns.append({
                "message": f"Using {len(models_used)} different models",
                "details": {"models": list(models_used)},
                "recommendation": "Consider standardizing on fewer models for better rates",
            })
        
        # Check for imbalanced usage
        total_tokens = sum(
            u.get("input_tokens", 0) + u.get("output_tokens", 0)
            for u in current_usage.values()
        )
        
        for model, usage in current_usage.items():
            model_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            if model_tokens > total_tokens * 0.8:
                unusual_patterns.append({
                    "message": f"80%+ of usage from single model: {model}",
                    "details": {"model": model, "percentage": (model_tokens/total_tokens)*100},
                    "recommendation": "Consider load balancing or model-specific optimization",
                })
        
        return unusual_patterns


class CostReportGenerator:
    """Generates detailed cost reports for billing"""
    
    def __init__(self, calculator: PricingCalculator):
        self.calculator = calculator
    
    def generate_invoice_data(
        self,
        customer_id: str,
        billing_period_start: datetime,
        billing_period_end: datetime,
        usage_data: Dict[str, Dict],
        tier: PricingTier,
        custom_config: Optional[Dict] = None
    ) -> Dict[str, any]:
        """
        Generate detailed invoice data
        
        Args:
            customer_id: Customer identifier
            billing_period_start: Start of billing period
            billing_period_end: End of billing period
            usage_data: Usage by model
            tier: Customer's tier
            custom_config: Custom pricing configuration
            
        Returns:
            Detailed invoice data
        """
        # Calculate billing details
        billing_calc = self.calculator.calculate_monthly_usage(
            tier=tier,
            usage_data=usage_data,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            custom_config=custom_config
        )
        
        # Generate line items
        line_items = []
        
        # Subscription fee
        if billing_calc["subscription_fee"] > 0:
            line_items.append({
                "type": "subscription",
                "description": f"{tier.value.title()} Tier Subscription",
                "quantity": 1,
                "unit_price": billing_calc["subscription_fee"],
                "total": billing_calc["subscription_fee"],
            })
        
        # Token usage by model
        for item in billing_calc["usage_breakdown"]:
            model = item["model"]
            usage = item["usage"]
            
            if usage["total_cost"] > 0:
                line_items.append({
                    "type": "usage",
                    "description": f"{model} API Usage",
                    "quantity": usage["total_tokens"],
                    "unit": "tokens",
                    "unit_price": float(usage["total_cost"] / usage["total_tokens"]) if usage["total_tokens"] > 0 else 0,
                    "total": float(usage["total_cost"]),
                    "details": {
                        "input_tokens": usage["input_tokens"],
                        "output_tokens": usage["output_tokens"],
                        "requests": item["requests"],
                    }
                })
        
        # Overage charges
        if billing_calc["overage_cost"] > 0:
            line_items.append({
                "type": "overage",
                "description": "Token Overage Charges",
                "quantity": billing_calc["overage_tokens"],
                "unit": "tokens",
                "total": billing_calc["overage_cost"],
            })
        
        # Credits
        if billing_calc["credits_applied"] > 0:
            line_items.append({
                "type": "credit",
                "description": "Credits Applied",
                "quantity": 1,
                "total": -billing_calc["credits_applied"],
            })
        
        return {
            "invoice_id": f"INV-{customer_id}-{billing_period_start.strftime('%Y%m')}",
            "customer_id": customer_id,
            "billing_period": billing_calc["billing_period"],
            "tier": tier.value,
            "line_items": line_items,
            "subtotal": billing_calc["cost_breakdown"]["subscription"] + billing_calc["cost_breakdown"]["overage"],
            "credits": billing_calc["cost_breakdown"]["credits"],
            "total": billing_calc["cost_breakdown"]["total"],
            "usage_summary": {
                "total_tokens": billing_calc["total_tokens_used"],
                "included_tokens": billing_calc["included_tokens"],
                "overage_tokens": billing_calc["overage_tokens"],
                "usage_percentage": billing_calc["usage_percentage"],
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
    
    def generate_usage_report(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        usage_history: List[Dict],
        include_predictions: bool = True
    ) -> Dict[str, any]:
        """Generate comprehensive usage report with insights"""
        optimizer = PricingOptimizer()
        patterns = UsagePattern(usage_history)
        
        report = {
            "customer_id": customer_id,
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": (end_date - start_date).days,
            },
            "usage_summary": {
                "total_requests": len(usage_history),
                "total_tokens": sum(
                    record.get("input_tokens", 0) + record.get("output_tokens", 0)
                    for record in usage_history
                ),
                "unique_models": len(patterns.model_distribution),
                "daily_average": float(patterns.daily_p50),
                "daily_peak": float(patterns.daily_p99),
            },
            "model_breakdown": [
                {
                    "model": model,
                    "tokens": tokens,
                    "percentage": (tokens / sum(patterns.model_distribution.values()) * 100) if sum(patterns.model_distribution.values()) > 0 else 0,
                }
                for model, tokens in sorted(
                    patterns.model_distribution.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ],
            "usage_trends": {
                "hourly_distribution": patterns.hourly_avg,
                "peak_hours": sorted(
                    patterns.hourly_avg.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3],
                "daily_pattern": {
                    "p50": float(patterns.daily_p50),
                    "p95": float(patterns.daily_p95),
                    "p99": float(patterns.daily_p99),
                },
            },
        }
        
        if include_predictions:
            # Add 30-day forecast
            current_tier = PricingTier.PROFESSIONAL  # Would get from customer data
            forecast = optimizer.forecast_costs(
                customer_id=customer_id,
                usage_history=usage_history,
                current_tier=current_tier,
                forecast_days=30,
                growth_rate=0.1  # 10% growth assumption
            )
            report["forecast"] = forecast
        
        return report