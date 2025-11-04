"""
Stripe Payment Handler
Manages payment processing, subscriptions, and webhooks for the LLM API platform
"""

import stripe
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import logging
import asyncio
from enum import Enum

logger = logging.getLogger(__name__)


class PaymentStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class SubscriptionStatus(Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    UNPAID = "unpaid"


class StripeHandler:
    """Handles all Stripe payment operations"""
    
    def __init__(self, api_key: str, webhook_secret: str):
        stripe.api_key = api_key
        self.webhook_secret = webhook_secret
        self._init_products_and_prices()
    
    def _init_products_and_prices(self):
        """Initialize Stripe products and price IDs"""
        # These would be created in Stripe Dashboard and stored here
        self.products = {
            "free": {
                "product_id": "prod_free_tier",
                "price_id": "price_free_tier",
            },
            "starter": {
                "product_id": "prod_starter_tier",
                "price_id": "price_starter_monthly",
            },
            "professional": {
                "product_id": "prod_professional_tier",
                "price_id": "price_professional_monthly",
            },
            "enterprise": {
                "product_id": "prod_enterprise_tier",
                "price_id": "price_enterprise_monthly",
            },
        }
        
        # Usage-based pricing for overages
        self.usage_prices = {
            "token_overage": "price_token_overage_per_million",
        }
    
    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, any]:
        """
        Create a new Stripe customer
        
        Args:
            email: Customer email
            name: Customer name
            metadata: Additional metadata to store
            
        Returns:
            Stripe customer object
        """
        try:
            customer_data = {
                "email": email,
                "metadata": metadata or {},
            }
            
            if name:
                customer_data["name"] = name
            
            # Add platform-specific metadata
            customer_data["metadata"].update({
                "platform": "llm_api",
                "created_at": datetime.utcnow().isoformat(),
            })
            
            customer = await asyncio.to_thread(
                stripe.Customer.create,
                **customer_data
            )
            
            logger.info(f"Created Stripe customer: {customer.id}")
            
            return {
                "customer_id": customer.id,
                "email": customer.email,
                "created": customer.created,
                "metadata": customer.metadata,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation failed: {str(e)}")
            raise
    
    async def create_subscription(
        self,
        customer_id: str,
        tier: str,
        payment_method_id: Optional[str] = None,
        trial_days: int = 0,
        metadata: Optional[Dict] = None
    ) -> Dict[str, any]:
        """
        Create a subscription for a customer
        
        Args:
            customer_id: Stripe customer ID
            tier: Subscription tier
            payment_method_id: Payment method to use
            trial_days: Number of trial days
            metadata: Additional metadata
            
        Returns:
            Subscription details
        """
        try:
            if tier not in self.products:
                raise ValueError(f"Invalid tier: {tier}")
            
            # Attach payment method if provided
            if payment_method_id:
                await self.attach_payment_method(customer_id, payment_method_id)
            
            subscription_data = {
                "customer": customer_id,
                "items": [{
                    "price": self.products[tier]["price_id"],
                }],
                "metadata": metadata or {},
                "expand": ["latest_invoice.payment_intent"],
            }
            
            # Add trial period if specified
            if trial_days > 0:
                subscription_data["trial_period_days"] = trial_days
            
            # Add usage-based component for token overages (except free tier)
            if tier != "free":
                subscription_data["items"].append({
                    "price": self.usage_prices["token_overage"],
                })
            
            subscription = await asyncio.to_thread(
                stripe.Subscription.create,
                **subscription_data
            )
            
            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "trial_end": subscription.trial_end,
                "tier": tier,
                "items": [
                    {
                        "id": item.id,
                        "price": item.price.id,
                        "quantity": item.quantity,
                    }
                    for item in subscription.items.data
                ],
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Subscription creation failed: {str(e)}")
            raise
    
    async def update_subscription(
        self,
        subscription_id: str,
        new_tier: Optional[str] = None,
        cancel_at_period_end: Optional[bool] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, any]:
        """
        Update an existing subscription
        
        Args:
            subscription_id: Stripe subscription ID
            new_tier: New tier to switch to
            cancel_at_period_end: Whether to cancel at period end
            metadata: Updated metadata
            
        Returns:
            Updated subscription details
        """
        try:
            update_data = {}
            
            if new_tier:
                # Get current subscription
                subscription = await asyncio.to_thread(
                    stripe.Subscription.retrieve,
                    subscription_id
                )
                
                # Find the base subscription item (not usage-based)
                base_item = None
                for item in subscription.items.data:
                    if item.price.id in [p["price_id"] for p in self.products.values()]:
                        base_item = item
                        break
                
                if not base_item:
                    raise ValueError("Could not find base subscription item")
                
                # Update to new tier
                update_data["items"] = [{
                    "id": base_item.id,
                    "price": self.products[new_tier]["price_id"],
                }]
                
                # Handle proration
                update_data["proration_behavior"] = "create_prorations"
            
            if cancel_at_period_end is not None:
                update_data["cancel_at_period_end"] = cancel_at_period_end
            
            if metadata:
                update_data["metadata"] = metadata
            
            updated_subscription = await asyncio.to_thread(
                stripe.Subscription.update,
                subscription_id,
                **update_data
            )
            
            return {
                "subscription_id": updated_subscription.id,
                "status": updated_subscription.status,
                "updated": True,
                "new_tier": new_tier,
                "cancel_at_period_end": updated_subscription.cancel_at_period_end,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Subscription update failed: {str(e)}")
            raise
    
    async def record_usage(
        self,
        subscription_item_id: str,
        quantity: int,
        timestamp: Optional[int] = None,
        action: str = "increment"
    ) -> Dict[str, any]:
        """
        Record usage for usage-based billing
        
        Args:
            subscription_item_id: Subscription item ID for usage-based pricing
            quantity: Number of tokens used (in millions)
            timestamp: Unix timestamp for the usage
            action: "increment" or "set"
            
        Returns:
            Usage record details
        """
        try:
            usage_data = {
                "quantity": quantity,
                "action": action,
            }
            
            if timestamp:
                usage_data["timestamp"] = timestamp
            else:
                usage_data["timestamp"] = int(datetime.utcnow().timestamp())
            
            usage_record = await asyncio.to_thread(
                stripe.SubscriptionItem.create_usage_record,
                subscription_item_id,
                **usage_data
            )
            
            return {
                "id": usage_record.id,
                "quantity": usage_record.quantity,
                "timestamp": usage_record.timestamp,
                "subscription_item": usage_record.subscription_item,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Usage recording failed: {str(e)}")
            raise
    
    async def create_payment_intent(
        self,
        amount: int,  # Amount in cents
        currency: str = "usd",
        customer_id: Optional[str] = None,
        payment_method_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, any]:
        """
        Create a payment intent for one-time charges
        
        Args:
            amount: Amount in cents
            currency: Currency code
            customer_id: Stripe customer ID
            payment_method_id: Payment method to use
            description: Payment description
            metadata: Additional metadata
            
        Returns:
            Payment intent details
        """
        try:
            intent_data = {
                "amount": amount,
                "currency": currency,
                "metadata": metadata or {},
            }
            
            if customer_id:
                intent_data["customer"] = customer_id
            
            if payment_method_id:
                intent_data["payment_method"] = payment_method_id
                intent_data["confirm"] = True
            
            if description:
                intent_data["description"] = description
            
            payment_intent = await asyncio.to_thread(
                stripe.PaymentIntent.create,
                **intent_data
            )
            
            return {
                "payment_intent_id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "amount": payment_intent.amount,
                "currency": payment_intent.currency,
                "status": payment_intent.status,
                "requires_action": payment_intent.status == "requires_action",
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Payment intent creation failed: {str(e)}")
            raise
    
    async def attach_payment_method(
        self,
        customer_id: str,
        payment_method_id: str,
        set_as_default: bool = True
    ) -> Dict[str, any]:
        """
        Attach a payment method to a customer
        
        Args:
            customer_id: Stripe customer ID
            payment_method_id: Payment method ID
            set_as_default: Whether to set as default payment method
            
        Returns:
            Payment method details
        """
        try:
            # Attach payment method to customer
            payment_method = await asyncio.to_thread(
                stripe.PaymentMethod.attach,
                payment_method_id,
                customer=customer_id
            )
            
            # Set as default if requested
            if set_as_default:
                await asyncio.to_thread(
                    stripe.Customer.modify,
                    customer_id,
                    invoice_settings={
                        "default_payment_method": payment_method_id
                    }
                )
            
            return {
                "payment_method_id": payment_method.id,
                "type": payment_method.type,
                "card": {
                    "brand": payment_method.card.brand,
                    "last4": payment_method.card.last4,
                    "exp_month": payment_method.card.exp_month,
                    "exp_year": payment_method.card.exp_year,
                } if payment_method.type == "card" else None,
                "is_default": set_as_default,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Payment method attachment failed: {str(e)}")
            raise
    
    async def create_invoice(
        self,
        customer_id: str,
        description: str,
        line_items: List[Dict],
        auto_advance: bool = True,
        metadata: Optional[Dict] = None
    ) -> Dict[str, any]:
        """
        Create a manual invoice
        
        Args:
            customer_id: Stripe customer ID
            description: Invoice description
            line_items: List of line items
            auto_advance: Whether to auto-finalize the invoice
            metadata: Additional metadata
            
        Returns:
            Invoice details
        """
        try:
            # Create invoice
            invoice = await asyncio.to_thread(
                stripe.Invoice.create,
                customer=customer_id,
                description=description,
                auto_advance=auto_advance,
                metadata=metadata or {},
            )
            
            # Add line items
            for item in line_items:
                await asyncio.to_thread(
                    stripe.InvoiceItem.create,
                    customer=customer_id,
                    invoice=invoice.id,
                    amount=int(item["amount"] * 100),  # Convert to cents
                    currency=item.get("currency", "usd"),
                    description=item["description"],
                    quantity=item.get("quantity", 1),
                )
            
            # Finalize if auto_advance is True
            if auto_advance:
                invoice = await asyncio.to_thread(
                    stripe.Invoice.finalize_invoice,
                    invoice.id
                )
            
            return {
                "invoice_id": invoice.id,
                "number": invoice.number,
                "amount_due": invoice.amount_due / 100,  # Convert from cents
                "amount_paid": invoice.amount_paid / 100,
                "status": invoice.status,
                "invoice_pdf": invoice.invoice_pdf,
                "hosted_invoice_url": invoice.hosted_invoice_url,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Invoice creation failed: {str(e)}")
            raise
    
    async def process_webhook(
        self,
        payload: bytes,
        signature: str
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Process incoming Stripe webhook
        
        Args:
            payload: Raw webhook payload
            signature: Stripe signature header
            
        Returns:
            Tuple of (success, event_data)
        """
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                self.webhook_secret
            )
            
            # Process different event types
            event_type = event["type"]
            event_data = event["data"]["object"]
            
            result = {
                "event_id": event["id"],
                "type": event_type,
                "processed": True,
                "data": {},
            }
            
            # Handle specific event types
            if event_type == "payment_intent.succeeded":
                result["data"] = {
                    "payment_intent_id": event_data["id"],
                    "amount": event_data["amount"] / 100,
                    "customer": event_data["customer"],
                }
                
            elif event_type == "payment_intent.payment_failed":
                result["data"] = {
                    "payment_intent_id": event_data["id"],
                    "failure_code": event_data["last_payment_error"]["code"],
                    "failure_message": event_data["last_payment_error"]["message"],
                }
                
            elif event_type == "subscription.created":
                result["data"] = {
                    "subscription_id": event_data["id"],
                    "customer": event_data["customer"],
                    "status": event_data["status"],
                    "items": [item["price"]["id"] for item in event_data["items"]["data"]],
                }
                
            elif event_type == "subscription.updated":
                result["data"] = {
                    "subscription_id": event_data["id"],
                    "customer": event_data["customer"],
                    "status": event_data["status"],
                    "cancel_at_period_end": event_data["cancel_at_period_end"],
                }
                
            elif event_type == "subscription.deleted":
                result["data"] = {
                    "subscription_id": event_data["id"],
                    "customer": event_data["customer"],
                    "canceled_at": event_data["canceled_at"],
                }
                
            elif event_type == "invoice.payment_succeeded":
                result["data"] = {
                    "invoice_id": event_data["id"],
                    "customer": event_data["customer"],
                    "amount_paid": event_data["amount_paid"] / 100,
                    "subscription": event_data["subscription"],
                }
                
            elif event_type == "invoice.payment_failed":
                result["data"] = {
                    "invoice_id": event_data["id"],
                    "customer": event_data["customer"],
                    "amount_due": event_data["amount_due"] / 100,
                    "attempt_count": event_data["attempt_count"],
                }
                
            elif event_type == "customer.subscription.trial_will_end":
                result["data"] = {
                    "subscription_id": event_data["id"],
                    "customer": event_data["customer"],
                    "trial_end": event_data["trial_end"],
                }
            
            logger.info(f"Processed webhook event: {event_type}")
            return True, result
            
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            return False, {"error": "Invalid signature"}
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return False, {"error": str(e)}
    
    async def create_refund(
        self,
        payment_intent_id: Optional[str] = None,
        charge_id: Optional[str] = None,
        amount: Optional[int] = None,
        reason: str = "requested_by_customer",
        metadata: Optional[Dict] = None
    ) -> Dict[str, any]:
        """
        Create a refund for a payment
        
        Args:
            payment_intent_id: Payment intent to refund
            charge_id: Charge to refund (alternative to payment_intent)
            amount: Amount to refund in cents (None for full refund)
            reason: Refund reason
            metadata: Additional metadata
            
        Returns:
            Refund details
        """
        try:
            refund_data = {
                "reason": reason,
                "metadata": metadata or {},
            }
            
            if payment_intent_id:
                refund_data["payment_intent"] = payment_intent_id
            elif charge_id:
                refund_data["charge"] = charge_id
            else:
                raise ValueError("Either payment_intent_id or charge_id must be provided")
            
            if amount:
                refund_data["amount"] = amount
            
            refund = await asyncio.to_thread(
                stripe.Refund.create,
                **refund_data
            )
            
            return {
                "refund_id": refund.id,
                "amount": refund.amount / 100,
                "currency": refund.currency,
                "status": refund.status,
                "reason": refund.reason,
                "created": refund.created,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Refund creation failed: {str(e)}")
            raise
    
    async def get_customer_payment_methods(
        self,
        customer_id: str,
        type: str = "card"
    ) -> List[Dict]:
        """
        Get all payment methods for a customer
        
        Args:
            customer_id: Stripe customer ID
            type: Payment method type to filter
            
        Returns:
            List of payment methods
        """
        try:
            payment_methods = await asyncio.to_thread(
                stripe.PaymentMethod.list,
                customer=customer_id,
                type=type
            )
            
            # Get default payment method
            customer = await asyncio.to_thread(
                stripe.Customer.retrieve,
                customer_id
            )
            default_pm_id = None
            if customer.invoice_settings and customer.invoice_settings.default_payment_method:
                default_pm_id = customer.invoice_settings.default_payment_method
            
            methods = []
            for pm in payment_methods.data:
                method_data = {
                    "id": pm.id,
                    "type": pm.type,
                    "is_default": pm.id == default_pm_id,
                    "created": pm.created,
                }
                
                if pm.type == "card":
                    method_data["card"] = {
                        "brand": pm.card.brand,
                        "last4": pm.card.last4,
                        "exp_month": pm.card.exp_month,
                        "exp_year": pm.card.exp_year,
                        "funding": pm.card.funding,
                    }
                
                methods.append(method_data)
            
            return methods
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get payment methods: {str(e)}")
            raise
    
    async def get_subscription_usage(
        self,
        subscription_item_id: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Get usage records for a subscription item
        
        Args:
            subscription_item_id: Subscription item ID
            start_time: Start timestamp (Unix)
            end_time: End timestamp (Unix)
            
        Returns:
            Usage summary
        """
        try:
            params = {}
            if start_time:
                params["starting_after"] = start_time
            if end_time:
                params["ending_before"] = end_time
            
            usage_records = await asyncio.to_thread(
                stripe.SubscriptionItem.list_usage_record_summaries,
                subscription_item_id,
                **params
            )
            
            total_usage = sum(record.total_usage for record in usage_records.data)
            
            return {
                "subscription_item_id": subscription_item_id,
                "total_usage": total_usage,
                "period_start": usage_records.data[0].period.start if usage_records.data else None,
                "period_end": usage_records.data[0].period.end if usage_records.data else None,
                "records": [
                    {
                        "id": record.id,
                        "total_usage": record.total_usage,
                        "period_start": record.period.start,
                        "period_end": record.period.end,
                    }
                    for record in usage_records.data
                ],
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get usage records: {str(e)}")
            raise


class PaymentProcessor:
    """High-level payment processing logic"""
    
    def __init__(self, stripe_handler: StripeHandler):
        self.stripe = stripe_handler
    
    async def process_tier_upgrade(
        self,
        customer_id: str,
        stripe_customer_id: str,
        current_tier: str,
        new_tier: str,
        subscription_id: str
    ) -> Dict[str, any]:
        """
        Process a tier upgrade with proper proration
        
        Args:
            customer_id: Internal customer ID
            stripe_customer_id: Stripe customer ID
            current_tier: Current subscription tier
            new_tier: New subscription tier
            subscription_id: Current subscription ID
            
        Returns:
            Upgrade result
        """
        try:
            # Update subscription
            result = await self.stripe.update_subscription(
                subscription_id=subscription_id,
                new_tier=new_tier
            )
            
            # Log the upgrade
            logger.info(
                f"Processed tier upgrade for customer {customer_id}: "
                f"{current_tier} -> {new_tier}"
            )
            
            return {
                "success": True,
                "subscription_id": result["subscription_id"],
                "old_tier": current_tier,
                "new_tier": new_tier,
                "status": result["status"],
                "message": f"Successfully upgraded from {current_tier} to {new_tier}",
            }
            
        except Exception as e:
            logger.error(f"Tier upgrade failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to process tier upgrade",
            }
    
    async def process_overage_billing(
        self,
        customer_id: str,
        subscription_item_id: str,
        tokens_used: int,
        included_tokens: int,
        billing_period_start: datetime,
        billing_period_end: datetime
    ) -> Dict[str, any]:
        """
        Process overage billing for token usage
        
        Args:
            customer_id: Internal customer ID
            subscription_item_id: Usage-based subscription item ID
            tokens_used: Total tokens used in period
            included_tokens: Tokens included in subscription
            billing_period_start: Start of billing period
            billing_period_end: End of billing period
            
        Returns:
            Overage billing result
        """
        try:
            overage_tokens = max(0, tokens_used - included_tokens)
            
            if overage_tokens == 0:
                return {
                    "success": True,
                    "overage_tokens": 0,
                    "overage_cost": 0,
                    "message": "No overage to bill",
                }
            
            # Convert to millions for billing (Stripe uses quantity)
            overage_millions = overage_tokens / 1_000_000
            
            # Record usage
            usage_result = await self.stripe.record_usage(
                subscription_item_id=subscription_item_id,
                quantity=int(overage_millions),
                timestamp=int(billing_period_end.timestamp()),
                action="set"
            )
            
            # Calculate estimated cost (assuming $1 per million tokens)
            estimated_cost = overage_millions
            
            logger.info(
                f"Recorded overage usage for customer {customer_id}: "
                f"{overage_tokens:,} tokens (${estimated_cost:.2f})"
            )
            
            return {
                "success": True,
                "overage_tokens": overage_tokens,
                "overage_millions": overage_millions,
                "estimated_cost": estimated_cost,
                "usage_record_id": usage_result["id"],
                "message": f"Recorded {overage_tokens:,} overage tokens",
            }
            
        except Exception as e:
            logger.error(f"Overage billing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to process overage billing",
            }
    
    async def handle_failed_payment(
        self,
        customer_id: str,
        invoice_id: str,
        payment_intent_id: str,
        amount_due: float,
        attempt_count: int
    ) -> Dict[str, any]:
        """
        Handle failed payment with retry logic
        
        Args:
            customer_id: Internal customer ID
            invoice_id: Failed invoice ID
            payment_intent_id: Failed payment intent ID
            amount_due: Amount that failed to charge
            attempt_count: Number of attempts made
            
        Returns:
            Handling result
        """
        try:
            # Define retry policy
            max_attempts = 3
            
            actions = []
            
            if attempt_count < max_attempts:
                # Schedule retry
                actions.append({
                    "action": "retry_scheduled",
                    "attempt": attempt_count + 1,
                    "retry_at": (datetime.utcnow() + timedelta(days=3)).isoformat(),
                })
                
                # Send reminder email
                actions.append({
                    "action": "payment_reminder_sent",
                    "message": f"Payment of ${amount_due:.2f} failed. Retry scheduled.",
                })
            else:
                # Max attempts reached
                actions.append({
                    "action": "subscription_suspended",
                    "reason": "max_payment_attempts_reached",
                })
                
                # Send final notice
                actions.append({
                    "action": "final_notice_sent",
                    "message": "Account suspended due to payment failure",
                })
            
            logger.warning(
                f"Handled failed payment for customer {customer_id}: "
                f"${amount_due:.2f}, attempt {attempt_count}/{max_attempts}"
            )
            
            return {
                "success": True,
                "invoice_id": invoice_id,
                "payment_intent_id": payment_intent_id,
                "amount_due": amount_due,
                "attempt_count": attempt_count,
                "max_attempts": max_attempts,
                "actions": actions,
            }
            
        except Exception as e:
            logger.error(f"Failed payment handling error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to handle payment failure",
            }
    
    async def process_refund_request(
        self,
        customer_id: str,
        payment_intent_id: str,
        amount: Optional[float] = None,
        reason: str = "customer_request",
        description: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Process a refund request
        
        Args:
            customer_id: Internal customer ID
            payment_intent_id: Payment to refund
            amount: Amount to refund (None for full)
            reason: Refund reason
            description: Additional description
            
        Returns:
            Refund result
        """
        try:
            # Convert amount to cents if provided
            amount_cents = int(amount * 100) if amount else None
            
            # Create metadata
            metadata = {
                "customer_id": customer_id,
                "reason": reason,
                "requested_at": datetime.utcnow().isoformat(),
            }
            
            if description:
                metadata["description"] = description
            
            # Process refund
            refund_result = await self.stripe.create_refund(
                payment_intent_id=payment_intent_id,
                amount=amount_cents,
                reason=self._map_refund_reason(reason),
                metadata=metadata
            )
            
            logger.info(
                f"Processed refund for customer {customer_id}: "
                f"${refund_result['amount']:.2f}"
            )
            
            return {
                "success": True,
                "refund_id": refund_result["refund_id"],
                "amount": refund_result["amount"],
                "status": refund_result["status"],
                "message": f"Refund of ${refund_result['amount']:.2f} processed",
            }
            
        except Exception as e:
            logger.error(f"Refund processing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to process refund",
            }
    
    def _map_refund_reason(self, reason: str) -> str:
        """Map internal reasons to Stripe refund reasons"""
        mapping = {
            "customer_request": "requested_by_customer",
            "duplicate_charge": "duplicate",
            "fraudulent": "fraudulent",
            "service_issue": "requested_by_customer",
        }
        return mapping.get(reason, "requested_by_customer")