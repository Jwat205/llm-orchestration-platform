"""
Pricing Calculator for LLM API Platform
Handles token-based pricing, tiered subscriptions, and enterprise custom pricing
"""

from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PricingTier(Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class ModelPricing:
    """Model-specific pricing configuration"""
    
    # Base pricing per 1K tokens (in USD)
    MODEL_RATES = {
        # Input / Output pricing
        "llama-2-7b": {"input": 0.0001, "output": 0.0002},
        "llama-2-13b": {"input": 0.0002, "output": 0.0004},
        "llama-2-70b": {"input": 0.0008, "output": 0.0016},
        "llama-3-8b": {"input": 0.0002, "output": 0.0004},
        "llama-3-70b": {"input": 0.001, "output": 0.002},
        "mistral-7b": {"input": 0.0001, "output": 0.0002},
        "mixtral-8x7b": {"input": 0.0005, "output": 0.001},
        "codellama-7b": {"input": 0.0002, "output": 0.0004},
        "codellama-34b": {"input": 0.0006, "output": 0.0012},
        "phi-3": {"input": 0.00005, "output": 0.0001},
        "custom": {"input": 0.001, "output": 0.002},  # Default custom model pricing
    }
    
    # Additional charges for special features
    FEATURE_MULTIPLIERS = {
        "streaming": 1.0,  # No additional charge
        "function_calling": 1.2,  # 20% premium
        "embeddings": 0.5,  # 50% of base rate
        "fine_tuned": 2.0,  # 2x for fine-tuned models
    }


class TierConfiguration:
    """Subscription tier configurations"""
    
    TIER_CONFIGS = {
        PricingTier.FREE: {
            "monthly_price": Decimal("0"),
            "included_tokens": 100_000,  # 100K tokens/month
            "rate_limit": 20,  # requests per minute
            "max_context": 4096,
            "models": ["llama-2-7b", "mistral-7b", "phi-3"],
            "features": ["basic_api"],
            "support": "community",
        },
        PricingTier.STARTER: {
            "monthly_price": Decimal("29"),
            "included_tokens": 2_000_000,  # 2M tokens/month
            "rate_limit": 60,
            "max_context": 8192,
            "models": ["llama-2-7b", "llama-2-13b", "mistral-7b", "mixtral-8x7b", "phi-3"],
            "features": ["basic_api", "streaming", "embeddings"],
            "support": "email",
            "overage_discount": 0.1,  # 10% discount on overage
        },
        PricingTier.PROFESSIONAL: {
            "monthly_price": Decimal("299"),
            "included_tokens": 10_000_000,  # 10M tokens/month
            "rate_limit": 300,
            "max_context": 16384,
            "models": "all",
            "features": ["basic_api", "streaming", "embeddings", "function_calling", "fine_tuning"],
            "support": "priority",
            "overage_discount": 0.2,  # 20% discount on overage
        },
        PricingTier.ENTERPRISE: {
            "monthly_price": Decimal("2999"),
            "included_tokens": 100_000_000,  # 100M tokens/month
            "rate_limit": 1000,
            "max_context": 32768,
            "models": "all",
            "features": "all",
            "support": "dedicated",
            "overage_discount": 0.3,  # 30% discount on overage
            "sla": True,
            "custom_models": True,
        },
        PricingTier.CUSTOM: {
            # Configured per customer
            "monthly_price": None,
            "included_tokens": None,
            "custom_terms": True,
        }
    }


class PricingCalculator:
    """Main pricing calculator for the LLM API platform"""
    
    def __init__(self):
        self.model_pricing = ModelPricing()
        self.tier_config = TierConfiguration()
        
    def calculate_token_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        features: Optional[List[str]] = None,
        tier: Optional[PricingTier] = None,
        custom_rates: Optional[Dict] = None
    ) -> Dict[str, Decimal]:
        """
        Calculate the cost for a specific API request
        
        Args:
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            features: List of features used (streaming, function_calling, etc.)
            tier: User's subscription tier for discount calculation
            custom_rates: Custom pricing rates for enterprise customers
            
        Returns:
            Dictionary with cost breakdown
        """
        try:
            # Get base rates
            if custom_rates and model in custom_rates:
                rates = custom_rates[model]
            else:
                rates = self.model_pricing.MODEL_RATES.get(
                    model, 
                    self.model_pricing.MODEL_RATES["custom"]
                )
            
            # Calculate base costs (per 1K tokens)
            input_cost = Decimal(str(rates["input"])) * (input_tokens / 1000)
            output_cost = Decimal(str(rates["output"])) * (output_tokens / 1000)
            
            # Apply feature multipliers
            multiplier = Decimal("1.0")
            if features:
                for feature in features:
                    if feature in self.model_pricing.FEATURE_MULTIPLIERS:
                        multiplier *= Decimal(str(self.model_pricing.FEATURE_MULTIPLIERS[feature]))
            
            # Apply tier discounts for overage
            if tier and tier != PricingTier.FREE:
                tier_config = self.tier_config.TIER_CONFIGS.get(tier, {})
                if "overage_discount" in tier_config:
                    multiplier *= Decimal(str(1 - tier_config["overage_discount"]))
            
            # Calculate final costs
            total_input_cost = input_cost * multiplier
            total_output_cost = output_cost * multiplier
            total_cost = total_input_cost + total_output_cost
            
            return {
                "input_cost": total_input_cost.quantize(Decimal("0.000001")),
                "output_cost": total_output_cost.quantize(Decimal("0.000001")),
                "total_cost": total_cost.quantize(Decimal("0.000001")),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "multiplier": multiplier.quantize(Decimal("0.01")),
                "model": model,
                "features": features or [],
            }
            
        except Exception as e:
            logger.error(f"Error calculating token cost: {str(e)}")
            raise
    
    def calculate_monthly_usage(
        self,
        tier: PricingTier,
        usage_data: Dict[str, Dict],
        billing_period_start: datetime,
        billing_period_end: datetime,
        custom_config: Optional[Dict] = None
    ) -> Dict[str, any]:
        """
        Calculate monthly usage and charges for a customer
        
        Args:
            tier: Customer's subscription tier
            usage_data: Dictionary of model usage {model: {input_tokens, output_tokens, requests}}
            billing_period_start: Start of billing period
            billing_period_end: End of billing period
            custom_config: Custom configuration for enterprise customers
            
        Returns:
            Complete billing calculation with breakdown
        """
        tier_config = self.tier_config.TIER_CONFIGS[tier]
        if custom_config:
            tier_config = {**tier_config, **custom_config}
        
        # Calculate total token usage
        total_tokens = 0
        usage_breakdown = []
        
        for model, usage in usage_data.items():
            model_cost = self.calculate_token_cost(
                model=model,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                features=usage.get("features", []),
                tier=tier,
                custom_rates=custom_config.get("custom_rates") if custom_config else None
            )
            
            total_tokens += model_cost["total_tokens"]
            usage_breakdown.append({
                "model": model,
                "usage": model_cost,
                "requests": usage.get("requests", 0),
            })
        
        # Calculate base subscription fee
        monthly_fee = tier_config.get("monthly_price", Decimal("0"))
        
        # Calculate overage if applicable
        included_tokens = tier_config.get("included_tokens", 0)
        overage_tokens = max(0, total_tokens - included_tokens)
        overage_cost = Decimal("0")
        
        if overage_tokens > 0 and tier != PricingTier.FREE:
            # Calculate overage cost based on usage breakdown
            for item in usage_breakdown:
                usage = item["usage"]
                token_ratio = usage["total_tokens"] / total_tokens if total_tokens > 0 else 0
                overage_portion = int(overage_tokens * token_ratio)
                
                if overage_portion > 0:
                    # Recalculate cost for overage portion
                    overage_model_cost = self.calculate_token_cost(
                        model=usage["model"],
                        input_tokens=int(usage["input_tokens"] * overage_portion / usage["total_tokens"]),
                        output_tokens=int(usage["output_tokens"] * overage_portion / usage["total_tokens"]),
                        features=usage["features"],
                        tier=tier
                    )
                    overage_cost += overage_model_cost["total_cost"]
        
        # Calculate total
        total_cost = monthly_fee + overage_cost
        
        # Apply any credits
        credits = custom_config.get("credits", Decimal("0")) if custom_config else Decimal("0")
        final_cost = max(Decimal("0"), total_cost - credits)
        
        # Calculate usage percentage
        usage_percentage = (total_tokens / included_tokens * 100) if included_tokens > 0 else 0
        
        return {
            "billing_period": {
                "start": billing_period_start.isoformat(),
                "end": billing_period_end.isoformat(),
                "days": (billing_period_end - billing_period_start).days,
            },
            "tier": tier.value,
            "subscription_fee": float(monthly_fee),
            "included_tokens": included_tokens,
            "total_tokens_used": total_tokens,
            "overage_tokens": overage_tokens,
            "overage_cost": float(overage_cost),
            "credits_applied": float(credits),
            "total_cost": float(final_cost),
            "usage_percentage": round(usage_percentage, 2),
            "usage_breakdown": usage_breakdown,
            "cost_breakdown": {
                "subscription": float(monthly_fee),
                "overage": float(overage_cost),
                "credits": float(credits),
                "total": float(final_cost),
            },
            "warnings": self._generate_usage_warnings(usage_percentage, tier),
        }
    
    def estimate_cost(
        self,
        tier: PricingTier,
        estimated_requests: int,
        avg_input_tokens: int = 500,
        avg_output_tokens: int = 500,
        model_distribution: Optional[Dict[str, float]] = None,
        features: Optional[List[str]] = None
    ) -> Dict[str, any]:
        """
        Estimate monthly costs based on projected usage
        
        Args:
            tier: Subscription tier
            estimated_requests: Estimated number of requests per month
            avg_input_tokens: Average input tokens per request
            avg_output_tokens: Average output tokens per request
            model_distribution: Distribution of requests across models (percentages)
            features: List of features that will be used
            
        Returns:
            Cost estimate with breakdown
        """
        if not model_distribution:
            # Default distribution
            model_distribution = {
                "llama-2-7b": 0.5,
                "llama-2-13b": 0.3,
                "mistral-7b": 0.2,
            }
        
        tier_config = self.tier_config.TIER_CONFIGS[tier]
        total_estimated_tokens = 0
        estimated_cost = Decimal("0")
        model_estimates = []
        
        for model, percentage in model_distribution.items():
            model_requests = int(estimated_requests * percentage)
            model_input_tokens = model_requests * avg_input_tokens
            model_output_tokens = model_requests * avg_output_tokens
            
            cost_data = self.calculate_token_cost(
                model=model,
                input_tokens=model_input_tokens,
                output_tokens=model_output_tokens,
                features=features,
                tier=tier
            )
            
            total_estimated_tokens += cost_data["total_tokens"]
            estimated_cost += cost_data["total_cost"]
            
            model_estimates.append({
                "model": model,
                "percentage": percentage * 100,
                "requests": model_requests,
                "tokens": cost_data["total_tokens"],
                "cost": float(cost_data["total_cost"]),
            })
        
        # Calculate if there will be overage
        monthly_fee = tier_config.get("monthly_price", Decimal("0"))
        included_tokens = tier_config.get("included_tokens", 0)
        overage_tokens = max(0, total_estimated_tokens - included_tokens)
        
        # Add overage cost if applicable
        if overage_tokens > 0 and tier != PricingTier.FREE:
            overage_ratio = overage_tokens / total_estimated_tokens
            overage_cost = estimated_cost * Decimal(str(overage_ratio))
            total_estimated_cost = monthly_fee + overage_cost
        else:
            total_estimated_cost = monthly_fee
        
        return {
            "tier": tier.value,
            "monthly_subscription": float(monthly_fee),
            "included_tokens": included_tokens,
            "estimated_tokens": total_estimated_tokens,
            "estimated_overage": overage_tokens,
            "estimated_total_cost": float(total_estimated_cost),
            "cost_per_request": float(total_estimated_cost / estimated_requests) if estimated_requests > 0 else 0,
            "model_breakdown": model_estimates,
            "assumptions": {
                "requests_per_month": estimated_requests,
                "avg_input_tokens": avg_input_tokens,
                "avg_output_tokens": avg_output_tokens,
                "features": features or [],
            },
            "recommendation": self._generate_tier_recommendation(
                total_estimated_tokens, 
                total_estimated_cost,
                tier
            ),
        }
    
    def _generate_usage_warnings(self, usage_percentage: float, tier: PricingTier) -> List[str]:
        """Generate warnings based on usage patterns"""
        warnings = []
        
        if usage_percentage >= 90:
            warnings.append("Usage is at 90% or above of included tokens")
        elif usage_percentage >= 75:
            warnings.append("Usage is approaching token limit (75%+)")
        
        if tier == PricingTier.FREE and usage_percentage >= 80:
            warnings.append("Consider upgrading to Starter tier for more tokens and features")
        
        return warnings
    
    def _generate_tier_recommendation(
        self, 
        estimated_tokens: int, 
        estimated_cost: Decimal,
        current_tier: PricingTier
    ) -> Dict[str, any]:
        """Generate tier recommendations based on usage"""
        recommendations = []
        
        for tier in PricingTier:
            if tier == PricingTier.CUSTOM:
                continue
                
            config = self.tier_config.TIER_CONFIGS[tier]
            included_tokens = config.get("included_tokens", 0)
            monthly_price = config.get("monthly_price", Decimal("0"))
            
            if included_tokens >= estimated_tokens:
                # This tier would cover the usage
                if tier != current_tier:
                    savings = float(estimated_cost - monthly_price)
                    if savings > 0:
                        recommendations.append({
                            "tier": tier.value,
                            "monthly_cost": float(monthly_price),
                            "potential_savings": savings,
                            "includes_tokens": included_tokens,
                        })
        
        # Sort by potential savings
        recommendations.sort(key=lambda x: x["potential_savings"], reverse=True)
        
        return {
            "current_tier": current_tier.value,
            "optimal_tier": recommendations[0]["tier"] if recommendations else current_tier.value,
            "alternatives": recommendations[:3],  # Top 3 recommendations
        }
    
    def get_tier_comparison(self) -> List[Dict]:
        """Get a comparison of all available tiers"""
        comparison = []
        
        for tier in PricingTier:
            if tier == PricingTier.CUSTOM:
                continue
                
            config = self.tier_config.TIER_CONFIGS[tier]
            comparison.append({
                "tier": tier.value,
                "monthly_price": float(config.get("monthly_price", 0)),
                "included_tokens": config.get("included_tokens", 0),
                "rate_limit_rpm": config.get("rate_limit", 0),
                "max_context_length": config.get("max_context", 0),
                "models": config.get("models", []),
                "features": config.get("features", []),
                "support_level": config.get("support", "none"),
                "overage_discount": config.get("overage_discount", 0) * 100 if "overage_discount" in config else 0,
            })
        
        return comparison