"""
Payment Processing Service
Handles payment processing, subscription management, and transaction handling
"""

import logging
import stripe
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class PaymentStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    INCOMPLETE = "incomplete"
    TRIALING = "trialing"

@dataclass
class PaymentResult:
    success: bool
    payment_id: Optional[str] = None
    error_message: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: str = "usd"
    metadata: Optional[Dict] = None

@dataclass
class SubscriptionResult:
    success: bool
    subscription_id: Optional[str] = None
    status: Optional[SubscriptionStatus] = None
    current_period_end: Optional[datetime] = None
    error_message: Optional[str] = None

class PaymentProcessor:
    """Core payment processing functionality using Stripe"""
    
    def __init__(self, stripe_secret_key: str, webhook_secret: str):
        stripe.api_key = stripe_secret_key
        self.webhook_secret = webhook_secret
        
    async def process_one_time_payment(
        self,
        amount: Decimal,
        currency: str,
        customer_id: str,
        description: str,
        metadata: Optional[Dict] = None
    ) -> PaymentResult:
        """Process a one-time payment"""
        try:
            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Stripe uses cents
                currency=currency,
                customer=customer_id,
                description=description,
                metadata=metadata or {},
                automatic_payment_methods={'enabled': True}
            )
            
            # Confirm payment intent
            confirmed_intent = stripe.PaymentIntent.confirm(intent.id)
            
            if confirmed_intent.status == 'succeeded':
                logger.info(f"Payment successful: {intent.id} for customer {customer_id}")
                return PaymentResult(
                    success=True,
                    payment_id=intent.id,
                    amount=amount,
                    currency=currency,
                    metadata=metadata
                )
            else:
                logger.warning(f"Payment incomplete: {intent.id}, status: {confirmed_intent.status}")
                return PaymentResult(
                    success=False,
                    error_message=f"Payment status: {confirmed_intent.status}"
                )
                
        except stripe.error.CardError as e:
            logger.error(f"Card error: {e.user_message}")
            return PaymentResult(
                success=False,
                error_message=e.user_message
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return PaymentResult(
                success=False,
                error_message="Payment processing error"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return PaymentResult(
                success=False,
                error_message="Internal error"
            )
    
    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        trial_days: int = 0,
        metadata: Optional[Dict] = None
    ) -> SubscriptionResult:
        """Create a new subscription"""
        try:
            subscription_params = {
                'customer': customer_id,
                'items': [{'price': price_id}],
                'metadata': metadata or {},
                'expand': ['latest_invoice.payment_intent']
            }
            
            if trial_days > 0:
                subscription_params['trial_period_days'] = trial_days
            
            subscription = stripe.Subscription.create(**subscription_params)
            
            logger.info(f"Subscription created: {subscription.id} for customer {customer_id}")
            
            return SubscriptionResult(
                success=True,
                subscription_id=subscription.id,
                status=SubscriptionStatus(subscription.status),
                current_period_end=datetime.fromtimestamp(subscription.current_period_end)
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating subscription: {str(e)}")
            return SubscriptionResult(
                success=False,
                error_message=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected error creating subscription: {str(e)}")
            return SubscriptionResult(
                success=False,
                error_message="Internal error"
            )
    
    async def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True
    ) -> SubscriptionResult:
        """Cancel a subscription"""
        try:
            if at_period_end:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            else:
                subscription = stripe.Subscription.cancel(subscription_id)
            
            logger.info(f"Subscription cancelled: {subscription_id}")
            
            return SubscriptionResult(
                success=True,
                subscription_id=subscription.id,
                status=SubscriptionStatus(subscription.status),
                current_period_end=datetime.fromtimestamp(subscription.current_period_end)
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Error cancelling subscription: {str(e)}")
            return SubscriptionResult(
                success=False,
                error_message=str(e)
            )
    
    async def update_subscription(
        self,
        subscription_id: str,
        new_price_id: Optional[str] = None,
        quantity: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> SubscriptionResult:
        """Update an existing subscription"""
        try:
            update_params = {}
            
            if new_price_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                update_params['items'] = [{
                    'id': subscription['items']['data'][0].id,
                    'price': new_price_id
                }]
            
            if quantity is not None:
                if 'items' not in update_params:
                    subscription = stripe.Subscription.retrieve(subscription_id)
                    update_params['items'] = [{
                        'id': subscription['items']['data'][0].id,
                        'quantity': quantity
                    }]
                else:
                    update_params['items'][0]['quantity'] = quantity
            
            if metadata:
                update_params['metadata'] = metadata
            
            updated_subscription = stripe.Subscription.modify(
                subscription_id,
                **update_params
            )
            
            logger.info(f"Subscription updated: {subscription_id}")
            
            return SubscriptionResult(
                success=True,
                subscription_id=updated_subscription.id,
                status=SubscriptionStatus(updated_subscription.status),
                current_period_end=datetime.fromtimestamp(updated_subscription.current_period_end)
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Error updating subscription: {str(e)}")
            return SubscriptionResult(
                success=False,
                error_message=str(e)
            )
    
    async def process_refund(
        self,
        payment_intent_id: str,
        amount: Optional[Decimal] = None,
        reason: str = "requested_by_customer"
    ) -> PaymentResult:
        """Process a refund"""
        try:
            refund_params = {
                'payment_intent': payment_intent_id,
                'reason': reason
            }
            
            if amount:
                refund_params['amount'] = int(amount * 100)
            
            refund = stripe.Refund.create(**refund_params)
            
            logger.info(f"Refund processed: {refund.id} for payment {payment_intent_id}")
            
            return PaymentResult(
                success=True,
                payment_id=refund.id,
                amount=Decimal(refund.amount) / 100,
                currency=refund.currency
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Error processing refund: {str(e)}")
            return PaymentResult(
                success=False,
                error_message=str(e)
            )
    
    async def get_customer_payment_methods(self, customer_id: str) -> List[Dict]:
        """Get customer's payment methods"""
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type="card"
            )
            
            return [
                {
                    'id': pm.id,
                    'type': pm.type,
                    'card': {
                        'brand': pm.card.brand,
                        'last4': pm.card.last4,
                        'exp_month': pm.card.exp_month,
                        'exp_year': pm.card.exp_year
                    }
                }
                for pm in payment_methods.data
            ]
            
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving payment methods: {str(e)}")
            return []
    
    async def handle_webhook(self, payload: str, signature: str) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            
            logger.info(f"Received webhook event: {event['type']}")
            
            # Handle different event types
            if event['type'] == 'payment_intent.succeeded':
                return await self._handle_payment_success(event['data']['object'])
            elif event['type'] == 'payment_intent.payment_failed':
                return await self._handle_payment_failure(event['data']['object'])
            elif event['type'] == 'customer.subscription.created':
                return await self._handle_subscription_created(event['data']['object'])
            elif event['type'] == 'customer.subscription.updated':
                return await self._handle_subscription_updated(event['data']['object'])
            elif event['type'] == 'customer.subscription.deleted':
                return await self._handle_subscription_cancelled(event['data']['object'])
            elif event['type'] == 'invoice.payment_succeeded':
                return await self._handle_invoice_payment_success(event['data']['object'])
            elif event['type'] == 'invoice.payment_failed':
                return await self._handle_invoice_payment_failure(event['data']['object'])
            else:
                logger.info(f"Unhandled webhook event type: {event['type']}")
                return {'status': 'ignored', 'event_type': event['type']}
            
        except ValueError as e:
            logger.error(f"Invalid payload: {str(e)}")
            raise
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {str(e)}")
            raise
    
    async def _handle_payment_success(self, payment_intent: Dict) -> Dict[str, Any]:
        """Handle successful payment"""
        logger.info(f"Payment succeeded: {payment_intent['id']}")
        return {
            'status': 'processed',
            'event_type': 'payment_success',
            'payment_id': payment_intent['id'],
            'amount': Decimal(payment_intent['amount']) / 100,
            'customer_id': payment_intent['customer']
        }
    
    async def _handle_payment_failure(self, payment_intent: Dict) -> Dict[str, Any]:
        """Handle failed payment"""
        logger.warning(f"Payment failed: {payment_intent['id']}")
        return {
            'status': 'processed',
            'event_type': 'payment_failure',
            'payment_id': payment_intent['id'],
            'customer_id': payment_intent['customer'],
            'error': payment_intent.get('last_payment_error', {}).get('message')
        }
    
    async def _handle_subscription_created(self, subscription: Dict) -> Dict[str, Any]:
        """Handle new subscription"""
        logger.info(f"Subscription created: {subscription['id']}")
        return {
            'status': 'processed',
            'event_type': 'subscription_created',
            'subscription_id': subscription['id'],
            'customer_id': subscription['customer'],
            'status': subscription['status']
        }
    
    async def _handle_subscription_updated(self, subscription: Dict) -> Dict[str, Any]:
        """Handle subscription update"""
        logger.info(f"Subscription updated: {subscription['id']}")
        return {
            'status': 'processed',
            'event_type': 'subscription_updated',
            'subscription_id': subscription['id'],
            'customer_id': subscription['customer'],
            'status': subscription['status']
        }
    
    async def _handle_subscription_cancelled(self, subscription: Dict) -> Dict[str, Any]:
        """Handle cancelled subscription"""
        logger.info(f"Subscription cancelled: {subscription['id']}")
        return {
            'status': 'processed',
            'event_type': 'subscription_cancelled',
            'subscription_id': subscription['id'],
            'customer_id': subscription['customer']
        }
    
    async def _handle_invoice_payment_success(self, invoice: Dict) -> Dict[str, Any]:
        """Handle successful invoice payment"""
        logger.info(f"Invoice payment succeeded: {invoice['id']}")
        return {
            'status': 'processed',
            'event_type': 'invoice_payment_success',
            'invoice_id': invoice['id'],
            'subscription_id': invoice['subscription'],
            'customer_id': invoice['customer']
        }
    
    async def _handle_invoice_payment_failure(self, invoice: Dict) -> Dict[str, Any]:
        """Handle failed invoice payment"""
        logger.warning(f"Invoice payment failed: {invoice['id']}")
        return {
            'status': 'processed',
            'event_type': 'invoice_payment_failure',
            'invoice_id': invoice['id'],
            'subscription_id': invoice['subscription'],
            'customer_id': invoice['customer']
        }

class CreditProcessor:
    """Handles credit-based payment system"""
    
    def __init__(self, payment_processor: PaymentProcessor):
        self.payment_processor = payment_processor
    
    async def purchase_credits(
        self,
        customer_id: str,
        credit_amount: int,
        price_per_credit: Decimal
    ) -> PaymentResult:
        """Purchase credits for a customer"""
        total_amount = credit_amount * price_per_credit
        
        result = await self.payment_processor.process_one_time_payment(
            amount=total_amount,
            currency="usd",
            customer_id=customer_id,
            description=f"Purchase of {credit_amount} credits",
            metadata={
                'type': 'credit_purchase',
                'credit_amount': str(credit_amount),
                'price_per_credit': str(price_per_credit)
            }
        )
        
        return result
    
    async def apply_credit_discount(
        self,
        customer_id: str,
        discount_amount: Decimal,
        reason: str
    ) -> bool:
        """Apply credit discount to customer account"""
        try:
            # Create credit note in Stripe
            stripe.CreditNote.create(
                invoice=None,  # Apply to account balance
                amount=int(discount_amount * 100),
                currency="usd",
                memo=reason,
                metadata={
                    'type': 'credit_discount',
                    'customer_id': customer_id,
                    'reason': reason
                }
            )
            
            logger.info(f"Credit discount applied: {discount_amount} for customer {customer_id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Error applying credit discount: {str(e)}")
            return False