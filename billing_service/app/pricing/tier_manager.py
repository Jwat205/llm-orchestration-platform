"""
Tier Manager for subscription management and tier transitions
Handles upgrades, downgrades, and tier-specific feature access
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import asyncio
import logging
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .calculator import PricingTier, TierConfiguration

logger = logging.getLogger(__name__)


class TierTransitionType(Enum):
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    RENEWAL = "renewal"
    CANCELLATION = "cancellation"


class TierManager:
    """Manages subscription tiers and transitions"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.tier_config = TierConfiguration()
        
    async def get_customer_tier(self, customer_id: str) -> Dict[str, any]:
        """
        Get current tier information for a customer
        
        Args:
            customer_id: Customer identifier
            
        Returns:
            Current tier information including features and limits
        """
        # This would query your database for the customer's subscription
        # For now, returning a mock response
        query = """
        SELECT 
            s.tier,
            s.status,
            s.started_at,
            s.expires_at,
            s.auto_renew,
            s.custom_config,
            c.total_tokens_used,
            c.current_period_tokens
        FROM subscriptions s
        JOIN customers c ON s.customer_id = c.id
        WHERE c.id = :customer_id
        AND s.status = 'active'
        ORDER BY s.created_at DESC
        LIMIT 1
        """
        
        # Mock implementation
        tier = PricingTier.PROFESSIONAL
        tier_config = self.tier_config.TIER_CONFIGS[tier]
        
        return {
            "customer_id": customer_id,
            "tier": tier.value,
            "tier_details": tier_config,
            "status": "active",
            "started_at": datetime.utcnow() - timedelta(days=15),
            "expires_at": datetime.utcnow() + timedelta(days=15),
            "auto_renew": True,
            "usage": {
                "current_period_tokens": 5_000_000,
                "included_tokens": tier_config["included_tokens"],
                "remaining_tokens": tier_config["included_tokens"] - 5_000_000,
                "usage_percentage": 50.0,
            },
            "features": tier_config.get("features", []),
            "rate_limit": tier_config.get("rate_limit", 0),
        }
    
    async def check_tier_access(
        self, 
        customer_id: str, 
        feature: str,
        model: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if customer has access to a specific feature or model
        
        Args:
            customer_id: Customer identifier
            feature: Feature to check (e.g., "function_calling", "fine_tuning")
            model: Optional model to check access for
            
        Returns:
            Tuple of (has_access, denial_reason)
        """
        tier_info = await self.get_customer_tier(customer_id)
        tier_config = tier_info["tier_details"]
        
        # Check feature access
        allowed_features = tier_config.get("features", [])
        if allowed_features != "all" and feature not in allowed_features:
            return False, f"Feature '{feature}' not available in {tier_info['tier']} tier"
        
        # Check model access
        if model:
            allowed_models = tier_config.get("models", [])
            if allowed_models != "all" and model not in allowed_models:
                return False, f"Model '{model}' not available in {tier_info['tier']} tier"
        
        # Check rate limits
        if tier_info["status"] != "active":
            return False, "Subscription is not active"
        
        return True, None
    
    async def calculate_tier_transition(
        self,
        customer_id: str,
        target_tier: PricingTier,
        effective_date: Optional[datetime] = None
    ) -> Dict[str, any]:
        """
        Calculate the cost and details of a tier transition
        
        Args:
            customer_id: Customer identifier
            target_tier: Target tier to transition to
            effective_date: When the transition should take effect
            
        Returns:
            Transition calculation including prorated amounts
        """
        current_tier_info = await self.get_customer_tier(customer_id)
        current_tier = PricingTier(current_tier_info["tier"])
        
        if not effective_date:
            effective_date = datetime.utcnow()
        
        # Determine transition type
        if current_tier == target_tier:
            transition_type = TierTransitionType.RENEWAL
        elif self._get_tier_rank(target_tier) > self._get_tier_rank(current_tier):
            transition_type = TierTransitionType.UPGRADE
        else:
            transition_type = TierTransitionType.DOWNGRADE
        
        # Calculate prorated amounts
        days_remaining = (current_tier_info["expires_at"] - effective_date).days
        total_period_days = (current_tier_info["expires_at"] - current_tier_info["started_at"]).days
        proration_factor = days_remaining / total_period_days if total_period_days > 0 else 0
        
        current_config = self.tier_config.TIER_CONFIGS[current_tier]
        target_config = self.tier_config.TIER_CONFIGS[target_tier]
        
        current_monthly = current_config.get("monthly_price", Decimal("0"))
        target_monthly = target_config.get("monthly_price", Decimal("0"))
        
        # Calculate credits and charges
        if transition_type == TierTransitionType.UPGRADE:
            # Credit for unused time on current tier
            credit = current_monthly * Decimal(str(proration_factor))
            # Charge for remaining time on new tier
            charge = target_monthly * Decimal(str(proration_factor))
            immediate_charge = charge - credit
        elif transition_type == TierTransitionType.DOWNGRADE:
            # Credit for unused time on current tier
            credit = current_monthly * Decimal(str(proration_factor))
            # No immediate charge for downgrades, credit applies to next billing
            charge = Decimal("0")
            immediate_charge = Decimal("0")
        else:
            credit = Decimal("0")
            charge = target_monthly
            immediate_charge = charge
        
        # Check for any usage overages that need to be settled
        overage_charge = await self._calculate_pending_overage(customer_id)
        
        return {
            "transition_type": transition_type.value,
            "current_tier": current_tier.value,
            "target_tier": target_tier.value,
            "effective_date": effective_date.isoformat(),
            "days_remaining": days_remaining,
            "proration": {
                "credit": float(credit),
                "charge": float(charge),
                "immediate_charge": float(immediate_charge),
                "overage_settlement": float(overage_charge),
                "total_due": float(immediate_charge + overage_charge),
            },
            "features": {
                "gained": self._get_feature_diff(current_tier, target_tier, "gained"),
                "lost": self._get_feature_diff(current_tier, target_tier, "lost"),
            },
            "limits": {
                "current_tokens": current_config.get("included_tokens", 0),
                "new_tokens": target_config.get("included_tokens", 0),
                "current_rate_limit": current_config.get("rate_limit", 0),
                "new_rate_limit": target_config.get("rate_limit", 0),
            },
            "warnings": self._generate_transition_warnings(
                transition_type, 
                current_tier_info,
                target_tier
            ),
        }
    
    async def execute_tier_transition(
        self,
        customer_id: str,
        target_tier: PricingTier,
        payment_method_id: Optional[str] = None,
        effective_date: Optional[datetime] = None
    ) -> Dict[str, any]:
        """
        Execute a tier transition
        
        Args:
            customer_id: Customer identifier
            target_tier: Target tier
            payment_method_id: Payment method for any charges
            effective_date: When transition takes effect
            
        Returns:
            Transition result
        """
        # Calculate transition
        transition = await self.calculate_tier_transition(
            customer_id, 
            target_tier, 
            effective_date
        )
        
        try:
            # Begin transaction
            async with self.db.begin():
                # Process any immediate charges
                if transition["proration"]["total_due"] > 0:
                    # This would integrate with your payment processor
                    payment_result = await self._process_transition_payment(
                        customer_id,
                        transition["proration"]["total_due"],
                        payment_method_id
                    )
                    if not payment_result["success"]:
                        raise Exception(f"Payment failed: {payment_result['error']}")
                
                # Update subscription in database
                await self._update_subscription_tier(
                    customer_id,
                    target_tier,
                    transition["effective_date"]
                )
                
                # Update customer limits and features
                await self._update_customer_limits(customer_id, target_tier)
                
                # Send notifications
                await self._send_tier_change_notification(customer_id, transition)
                
                # Log the transition
                await self._log_tier_transition(customer_id, transition)
            
            return {
                "success": True,
                "transition": transition,
                "new_tier": target_tier.value,
                "effective_date": transition["effective_date"],
            }
            
        except Exception as e:
            logger.error(f"Tier transition failed for customer {customer_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "transition": transition,
            }
    
    async def check_usage_limits(
        self,
        customer_id: str,
        tokens_to_use: int
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Check if customer has enough tokens for a request
        
        Args:
            customer_id: Customer identifier
            tokens_to_use: Number of tokens the request will use
            
        Returns:
            Tuple of (can_proceed, limit_info)
        """
        tier_info = await self.get_customer_tier(customer_id)
        
        # Free tier hard limit
        if tier_info["tier"] == PricingTier.FREE.value:
            remaining = tier_info["usage"]["remaining_tokens"]
            if remaining < tokens_to_use:
                return False, {
                    "reason": "token_limit_exceeded",
                    "remaining_tokens": remaining,
                    "requested_tokens": tokens_to_use,
                    "message": "Free tier token limit exceeded. Please upgrade to continue.",
                }
        
        # Check soft limits for paid tiers
        usage_percentage = tier_info["usage"]["usage_percentage"]
        if usage_percentage > 90:
            # Send warning but allow request
            logger.warning(
                f"Customer {customer_id} at {usage_percentage}% of token limit"
            )
        
        return True, {
            "remaining_tokens": tier_info["usage"]["remaining_tokens"],
            "usage_percentage": usage_percentage,
            "will_incur_overage": tier_info["usage"]["current_period_tokens"] + tokens_to_use > tier_info["usage"]["included_tokens"],
        }
    
    async def get_tier_recommendations(
        self,
        customer_id: str,
        lookback_days: int = 30
    ) -> Dict[str, any]:
        """
        Get tier recommendations based on usage patterns
        
        Args:
            customer_id: Customer identifier
            lookback_days: Days to analyze for usage patterns
            
        Returns:
            Tier recommendations with analysis
        """
        # Get usage history
        usage_history = await self._get_usage_history(customer_id, lookback_days)
        current_tier_info = await self.get_customer_tier(customer_id)
        current_tier = PricingTier(current_tier_info["tier"])
        
        # Analyze usage patterns
        avg_daily_tokens = usage_history.get("avg_daily_tokens", 0)
        peak_daily_tokens = usage_history.get("peak_daily_tokens", 0)
        avg_requests_per_day = usage_history.get("avg_requests_per_day", 0)
        models_used = usage_history.get("unique_models", [])
        features_used = usage_history.get("features_used", [])
        
        # Calculate projected monthly usage
        projected_monthly_tokens = avg_daily_tokens * 30
        projected_peak_monthly = peak_daily_tokens * 30
        
        recommendations = []
        
        # Check each tier
        for tier in PricingTier:
            if tier == PricingTier.CUSTOM:
                continue
                
            config = self.tier_config.TIER_CONFIGS[tier]
            included_tokens = config.get("included_tokens", 0)
            
            # Check if tier meets requirements
            meets_token_needs = included_tokens >= projected_monthly_tokens
            meets_peak_needs = included_tokens >= projected_peak_monthly
            meets_model_needs = all(
                model in config.get("models", []) or config.get("models") == "all"
                for model in models_used
            )
            meets_feature_needs = all(
                feature in config.get("features", []) or config.get("features") == "all"
                for feature in features_used
            )
            
            if meets_token_needs and meets_model_needs and meets_feature_needs:
                score = self._calculate_tier_fit_score(
                    tier, 
                    projected_monthly_tokens,
                    models_used,
                    features_used,
                    current_tier
                )
                
                recommendations.append({
                    "tier": tier.value,
                    "fit_score": score,
                    "monthly_cost": float(config.get("monthly_price", 0)),
                    "included_tokens": included_tokens,
                    "meets_requirements": {
                        "tokens": meets_token_needs,
                        "peak_usage": meets_peak_needs,
                        "models": meets_model_needs,
                        "features": meets_feature_needs,
                    },
                    "cost_efficiency": self._calculate_cost_efficiency(
                        tier,
                        projected_monthly_tokens,
                        config
                    ),
                })
        
        # Sort by fit score
        recommendations.sort(key=lambda x: x["fit_score"], reverse=True)
        
        return {
            "current_tier": current_tier.value,
            "usage_analysis": {
                "avg_daily_tokens": avg_daily_tokens,
                "peak_daily_tokens": peak_daily_tokens,
                "projected_monthly_tokens": projected_monthly_tokens,
                "avg_requests_per_day": avg_requests_per_day,
                "models_used": models_used,
                "features_used": features_used,
            },
            "recommendations": recommendations[:3],  # Top 3
            "optimal_tier": recommendations[0]["tier"] if recommendations else current_tier.value,
            "potential_savings": self._calculate_potential_savings(
                current_tier,
                recommendations[0]["tier"] if recommendations else current_tier.value,
                projected_monthly_tokens
            ),
        }
    
    def _get_tier_rank(self, tier: PricingTier) -> int:
        """Get numeric rank for tier comparison"""
        ranks = {
            PricingTier.FREE: 0,
            PricingTier.STARTER: 1,
            PricingTier.PROFESSIONAL: 2,
            PricingTier.ENTERPRISE: 3,
            PricingTier.CUSTOM: 4,
        }
        return ranks.get(tier, 0)
    
    def _get_feature_diff(
        self, 
        current_tier: PricingTier, 
        target_tier: PricingTier,
        diff_type: str
    ) -> List[str]:
        """Get feature differences between tiers"""
        current_config = self.tier_config.TIER_CONFIGS[current_tier]
        target_config = self.tier_config.TIER_CONFIGS[target_tier]
        
        current_features = set(current_config.get("features", []))
        target_features = set(target_config.get("features", []))
        
        if current_features == "all":
            current_features = {"basic_api", "streaming", "embeddings", "function_calling", "fine_tuning"}
        if target_features == "all":
            target_features = {"basic_api", "streaming", "embeddings", "function_calling", "fine_tuning"}
        
        if diff_type == "gained":
            return list(target_features - current_features)
        else:  # lost
            return list(current_features - target_features)
    
    def _generate_transition_warnings(
        self,
        transition_type: TierTransitionType,
        current_tier_info: Dict,
        target_tier: PricingTier
    ) -> List[str]:
        """Generate warnings for tier transitions"""
        warnings = []
        
        if transition_type == TierTransitionType.DOWNGRADE:
            warnings.append("Downgrade will take effect at the end of current billing period")
            
            # Check if current usage exceeds target tier limits
            target_config = self.tier_config.TIER_CONFIGS[target_tier]
            if current_tier_info["usage"]["current_period_tokens"] > target_config.get("included_tokens", 0):
                warnings.append("Current usage exceeds target tier limits - overage charges may apply")
        
        elif transition_type == TierTransitionType.UPGRADE:
            warnings.append("Upgrade will take effect immediately with prorated charges")
        
        return warnings
    
    async def _calculate_pending_overage(self, customer_id: str) -> Decimal:
        """Calculate any pending overage charges"""
        # This would query your database for current period usage
        # Mock implementation
        return Decimal("0")
    
    async def _process_transition_payment(
        self,
        customer_id: str,
        amount: float,
        payment_method_id: Optional[str]
    ) -> Dict[str, any]:
        """Process payment for tier transition"""
        # This would integrate with your payment processor
        # Mock implementation
        return {"success": True, "transaction_id": "txn_mock_123"}
    
    async def _update_subscription_tier(
        self,
        customer_id: str,
        new_tier: PricingTier,
        effective_date: str
    ):
        """Update subscription tier in database"""
        # Database update logic
        pass
    
    async def _update_customer_limits(self, customer_id: str, new_tier: PricingTier):
        """Update customer limits based on new tier"""
        # Update rate limits, token limits, etc.
        pass
    
    async def _send_tier_change_notification(self, customer_id: str, transition: Dict):
        """Send notification about tier change"""
        # Email/webhook notification
        pass
    
    async def _log_tier_transition(self, customer_id: str, transition: Dict):
        """Log tier transition for audit trail"""
        # Audit logging
        pass
    
    async def _get_usage_history(
        self, 
        customer_id: str, 
        lookback_days: int
    ) -> Dict[str, any]:
        """Get usage history for analysis"""
        # This would query your database
        # Mock implementation
        return {
            "avg_daily_tokens": 150_000,
            "peak_daily_tokens": 500_000,
            "avg_requests_per_day": 1000,
            "unique_models": ["llama-2-7b", "llama-2-13b"],
            "features_used": ["streaming", "function_calling"],
        }
    
    def _calculate_tier_fit_score(
        self,
        tier: PricingTier,
        projected_tokens: int,
        models_used: List[str],
        features_used: List[str],
        current_tier: PricingTier
    ) -> float:
        """Calculate how well a tier fits customer needs"""
        config = self.tier_config.TIER_CONFIGS[tier]
        score = 0.0
        
        # Token utilization score (optimal is 70-90%)
        included_tokens = config.get("included_tokens", 0)
        if included_tokens > 0:
            utilization = projected_tokens / included_tokens
            if 0.7 <= utilization <= 0.9:
                score += 40  # Optimal utilization
            elif utilization < 0.7:
                score += 20 * utilization  # Under-utilization penalty
            else:
                score += 20  # Over-utilization penalty
        
        # Feature coverage score
        tier_features = config.get("features", [])
        if tier_features == "all" or all(f in tier_features for f in features_used):
            score += 30
        else:
            coverage = sum(1 for f in features_used if f in tier_features) / len(features_used)
            score += 30 * coverage
        
        # Model coverage score
        tier_models = config.get("models", [])
        if tier_models == "all" or all(m in tier_models for m in models_used):
            score += 20
        else:
            coverage = sum(1 for m in models_used if m in tier_models) / len(models_used)
            score += 20 * coverage
        
        # Cost efficiency score
        if self._get_tier_rank(tier) <= self._get_tier_rank(current_tier):
            score += 10  # Bonus for same or lower tier
        
        return round(score, 2)
    
    def _calculate_cost_efficiency(
        self,
        tier: PricingTier,
        projected_tokens: int,
        config: Dict
    ) -> float:
        """Calculate cost per token for the tier"""
        monthly_price = float(config.get("monthly_price", 0))
        included_tokens = config.get("included_tokens", 0)
        
        if included_tokens >= projected_tokens:
            # All usage covered by subscription
            return monthly_price / projected_tokens if projected_tokens > 0 else 0
        else:
            # Need to account for overage
            # This is simplified - would need full overage calculation
            overage_tokens = projected_tokens - included_tokens
            overage_rate = 0.001  # $1 per 1M tokens as example
            overage_cost = overage_tokens * overage_rate
            total_cost = monthly_price + overage_cost
            return total_cost / projected_tokens if projected_tokens > 0 else 0
    
    def _calculate_potential_savings(
        self,
        current_tier: str,
        recommended_tier: str,
        projected_tokens: int
    ) -> float:
        """Calculate potential monthly savings"""
        # This would do a full cost comparison
        # Mock implementation
        return 50.0 if recommended_tier != current_tier else 0.0