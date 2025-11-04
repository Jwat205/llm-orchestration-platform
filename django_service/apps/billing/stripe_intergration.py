import stripe
import logging
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from typing import Dict, Optional, List

from .models import (
    UserSubscription, Invoice, InvoiceLineItem, PaymentMethod, 
    CreditBalance, CreditTransaction, UsageRecord
)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)

class StripeIntegration:
    """
    Think of this as your payment processing center - like the cash register at a store.
    It handles all the complex payment logic so your main app doesn't have to.
    
    This is crucial for your enterprise platform handling 100M+ requests monthly.
    """
    
    @classmethod
    def create_customer(cls, user: User) -> Optional[str]:
        """
        Create a Stripe customer - like opening a new account at a bank.
        Every user needs a Stripe customer ID to process payments.
        """
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip() or user.username,
                metadata={
                    'user_id': user.id,
                    'username': user.username,
                }
            )
            logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f"Error creating Stripe customer for user {user.id}: {e}")
            return None
    
    @classmethod
    def create_subscription(cls, user_subscription: UserSubscription) -> bool:
        """
        Create a recurring subscription - like setting up automatic gym membership payments.
        This handles the complex logic of recurring billing for your SaaS platform.
        """
        try:
            # Ensure user has a Stripe customer ID
            if not user_subscription.stripe_customer_id:
                stripe_customer_id = cls.create_customer(user_subscription.user)
                if not stripe_customer_id:
                    return False
                user_subscription.stripe_customer_id = stripe_customer_id
                user_subscription.save()
            
            # Create the subscription in Stripe
            subscription = stripe.Subscription.create(
                customer=user_subscription.stripe_customer_id,
                items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': user_subscription.pricing_tier.name,
                            'description': f"Monthly subscription to {user_subscription.pricing_tier.name} plan",
                        },
                        'unit_amount': int(user_subscription.pricing_tier.base_monthly_cost * 100),  # Stripe uses cents
                        'recurring': {
                            'interval': 'month',
                        },
                    },
                }],
                metadata={
                    'user_id': user_subscription.user.id,
                    'subscription_id': user_subscription.id,
                },
                # Trial period if specified
                trial_end=user_subscription.trial_end.timestamp() if user_subscription.trial_end else None,
            )
            
            # Update our subscription with Stripe details
            user_subscription.stripe_subscription_id = subscription.id
            user_subscription.current_period_start = timezone.datetime.fromtimestamp(
                subscription.current_period_start, tz=timezone.utc
            )
            user_subscription.current_period_end = timezone.datetime.fromtimestamp(
                subscription.current_period_end, tz=timezone.utc
            )
            user_subscription.save()
            
            logger.info(f"Created Stripe subscription {subscription.id} for user {user_subscription.user.id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Error creating Stripe subscription: {e}")
            return False
    
    @classmethod
    def handle_webhook(cls, event_data: Dict) -> bool:
        """
        Handle Stripe webhooks - like receiving notifications from your bank about transactions.
        This is how Stripe tells us about payment successes, failures, etc.
        
        Critical for maintaining data consistency in your high-volume platform.
        """
        event_type = event_data.get('type')
        data_object = event_data.get('data', {}).get('object', {})
        
        try:
            if event_type == 'invoice.payment_succeeded':
                return cls._handle_payment_succeeded(data_object)
            elif event_type == 'invoice.payment_failed':
                return cls._handle_payment_failed(data_object)
            elif event_type == 'customer.subscription.updated':
                return cls._handle_subscription_updated(data_object)
            elif event_type == 'customer.subscription.deleted':
                return cls._handle_subscription_deleted(data_object)
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                return True
                
        except Exception as e:
            logger.error(f"Error handling webhook {event_type}: {e}")
            return False
    
    @classmethod
    def _handle_payment_succeeded(cls, invoice_data: Dict) -> bool:
        """
        Handle successful payment - like confirming a check cleared the bank.
        Updates our records to show payment was received.
        """
        stripe_invoice_id = invoice_data.get('id')
        stripe_subscription_id = invoice_data.get('subscription')
        
        try:
            # Find our subscription
            subscription = UserSubscription.objects.get(
                stripe_subscription_id=stripe_subscription_id
            )
            
            # Find or create the invoice
            invoice, created = Invoice.objects.get_or_create(
                stripe_invoice_id=stripe_invoice_id,
                defaults={
                    'user': subscription.user,
                    'subscription': subscription,
                    'invoice_number': f"INV-{stripe_invoice_id[-8:]}",
                    'status': 'paid',
                    'period_start': subscription.current_period_start,
                    'period_end': subscription.current_period_end,
                    'total_amount': Decimal(invoice_data.get('amount_paid', 0)) / 100,
                    'amount_paid': Decimal(invoice_data.get('amount_paid', 0)) / 100,
                    'amount_due': Decimal(0),
                    'due_date': timezone.now(),
                    'paid_at': timezone.now(),
                }
            )
            
            if not created:
                # Update existing invoice
                invoice.status = 'paid'
                invoice.amount_paid = Decimal(invoice_data.get('amount_paid', 0)) / 100
                invoice.paid_at = timezone.now()
                invoice.save()
            
            # Reset usage counters for new billing period
            subscription.tokens_used_current_period = 0
            subscription.requests_made_current_period = 0
            subscription.save()
            
            logger.info(f"Payment succeeded for invoice {stripe_invoice_id}")
            return True
            
        except UserSubscription.DoesNotExist:
            logger.error(f"Subscription not found for invoice {stripe_invoice_id}")
            return False
    
    @classmethod
    def _handle_payment_failed(cls, invoice_data: Dict) -> bool:
        """
        Handle failed payment - like a bounced check.
        This might suspend service or send dunning emails.
        """
        stripe_invoice_id = invoice_data.get('id')
        stripe_subscription_id = invoice_data.get('subscription')
        
        try:
            subscription = UserSubscription.objects.get(
                stripe_subscription_id=stripe_subscription_id
            )
            
            # Update subscription status
            subscription.status = 'past_due'
            subscription.save()
            
            # Update invoice status
            try:
                invoice = Invoice.objects.get(stripe_invoice_id=stripe_invoice_id)
                invoice.status = 'past_due'
                invoice.save()
            except Invoice.DoesNotExist:
                pass
            
            logger.warning(f"Payment failed for subscription {stripe_subscription_id}")
            return True
            
        except UserSubscription.DoesNotExist:
            logger.error(f"Subscription not found for failed payment {stripe_invoice_id}")
            return False
    
    @classmethod
    def calculate_usage_charges(cls, subscription: UserSubscription) -> Decimal:
        """
        Calculate overage charges - like data overages on a phone plan.
        This is crucial for your usage-based billing model.
        """
        total_overage = Decimal('0.00')
        
        # Calculate token overage
        if subscription.tokens_used_current_period > subscription.pricing_tier.included_tokens_monthly:
            overage_tokens = subscription.tokens_used_current_period - subscription.pricing_tier.included_tokens_monthly
            overage_cost = (overage_tokens / 1000) * subscription.pricing_tier.cost_per_thousand_tokens
            total_overage += overage_cost
        
        return total_overage
    
    @classmethod
    def create_usage_invoice(cls, subscription: UserSubscription) -> Optional[Invoice]:
        """
        Create an invoice for usage charges - like your monthly utility bill.
        This handles the complex logic of calculating usage-based charges.
        """
        try:
            # Calculate charges
            base_charge = subscription.pricing_tier.base_monthly_cost
            usage_charges = cls.calculate_usage_charges(subscription)
            total_amount = base_charge + usage_charges
            
            # Create invoice
            invoice = Invoice.objects.create(
                user=subscription.user,
                subscription=subscription,
                invoice_number=f"INV-{timezone.now().strftime('%Y%m')}-{subscription.user.id}",
                status='open',
                period_start=subscription.current_period_start,
                period_end=subscription.current_period_end,
                subtotal=total_amount,
                total_amount=total_amount,
                amount_due=total_amount,
                due_date=timezone.now() + timedelta(days=30),
            )
            
            # Create line items
            if base_charge > 0:
                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    description=f"{subscription.pricing_tier.name} - Monthly Subscription",
                    quantity=1,
                    unit_price=base_charge,
                    resource_type='subscription',
                    usage_period_start=subscription.current_period_start,
                    usage_period_end=subscription.current_period_end,
                )
            
            if usage_charges > 0:
                overage_tokens = subscription.tokens_used_current_period - subscription.pricing_tier.included_tokens_monthly
                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    description=f"Token Usage Overage ({overage_tokens:,} tokens)",
                    quantity=overage_tokens / 1000,  # Price is per 1000 tokens
                    unit_price=subscription.pricing_tier.cost_per_thousand_tokens,
                    resource_type='tokens',
                    usage_period_start=subscription.current_period_start,
                    usage_period_end=subscription.current_period_end,
                )
            
            return invoice
            
        except Exception as e:
            logger.error(f"Error creating usage invoice for subscription {subscription.id}: {e}")
            return None
    
    @classmethod
    def add_payment_method(cls, user: User, stripe_payment_method_id: str) -> Optional[PaymentMethod]:
        """
        Add a payment method - like adding a credit card to your Amazon account.
        Essential for subscription and usage-based billing.
        """
        try:
            # Get payment method details from Stripe
            payment_method = stripe.PaymentMethod.retrieve(stripe_payment_method_id)
            
            # Ensure user has a Stripe customer
            try:
                subscription = user.subscription
                if not subscription.stripe_customer_id:
                    stripe_customer_id = cls.create_customer(user)
                    if not stripe_customer_id:
                        return None
                    subscription.stripe_customer_id = stripe_customer_id
                    subscription.save()
                customer_id = subscription.stripe_customer_id
            except UserSubscription.DoesNotExist:
                customer_id = cls.create_customer(user)
                if not customer_id:
                    return None
            
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                stripe_payment_method_id,
                customer=customer_id,
            )
            
            # Create our payment method record
            card_data = payment_method.get('card', {})
            pm = PaymentMethod.objects.create(
                user=user,
                payment_type='card',
                stripe_payment_method_id=stripe_payment_method_id,
                last_four=card_data.get('last4'),
                brand=card_data.get('brand'),
                exp_month=card_data.get('exp_month'),
                exp_year=card_data.get('exp_year'),
                is_default=not PaymentMethod.objects.filter(user=user, is_active=True).exists(),
            )
            
            logger.info(f"Added payment method {stripe_payment_method_id} for user {user.id}")
            return pm
            
        except stripe.error.StripeError as e:
            logger.error(f"Error adding payment method for user {user.id}: {e}")
            return None
    
    @classmethod
    def charge_for_usage(cls, user: User, amount: Decimal, description: str) -> bool:
        """
        Charge user for immediate usage - like paying for a taxi ride.
        This is for pay-as-you-go billing, perfect for your high-volume API platform.
        """
        try:
            # Get user's default payment method
            payment_method = PaymentMethod.objects.filter(
                user=user, 
                is_default=True, 
                is_active=True
            ).first()
            
            if not payment_method:
                logger.error(f"No default payment method for user {user.id}")
                return False
            
            # Get customer ID
            try:
                customer_id = user.subscription.stripe_customer_id
            except UserSubscription.DoesNotExist:
                customer_id = cls.create_customer(user)
                if not customer_id:
                    return False
            
            # Create payment intent
            payment_intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Stripe uses cents
                currency='usd',
                customer=customer_id,
                payment_method=payment_method.stripe_payment_method_id,
                description=description,
                confirm=True,
                metadata={
                    'user_id': user.id,
                    'type': 'usage_charge',
                }
            )
            
            if payment_intent.status == 'succeeded':
                # Record the transaction
                CreditTransaction.objects.create(
                    user=user,
                    transaction_type='debit',
                    amount=amount,
                    description=description,
                    balance_after=user.credit_balance.current_balance if hasattr(user, 'credit_balance') else 0,
                )
                
                logger.info(f"Successfully charged ${amount} to user {user.id}")
                return True
            else:
                logger.warning(f"Payment intent failed for user {user.id}: {payment_intent.status}")
                return False
                
        except stripe.error.StripeError as e:
            logger.error(f"Error charging user {user.id}: {e}")
            return False
    
    @classmethod
    def process_credit_purchase(cls, user: User, credit_amount: Decimal) -> bool:
        """
        Process credit purchase - like buying gift cards or adding money to your Starbucks app.
        Allows users to prepay for API usage, improving cash flow.
        """
        try:
            # Calculate charge amount (you might add fees or discounts here)
            charge_amount = credit_amount  # 1:1 ratio for simplicity
            
            # Process payment
            if cls.charge_for_usage(user, charge_amount, f"Credit purchase: ${credit_amount}"):
                # Add credits to user's balance
                credit_balance, created = CreditBalance.objects.get_or_create(
                    user=user,
                    defaults={'current_balance': Decimal('0.00')}
                )
                
                credit_balance.current_balance += credit_amount
                credit_balance.lifetime_purchased += credit_amount
                credit_balance.save()
                
                # Record transaction
                CreditTransaction.objects.create(
                    user=user,
                    transaction_type='credit',
                    amount=credit_amount,
                    description=f"Credit purchase",
                    balance_after=credit_balance.current_balance,
                )
                
                logger.info(f"Added ${credit_amount} credits to user {user.id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error processing credit purchase for user {user.id}: {e}")
            return False
    
    @classmethod
    def handle_auto_recharge(cls, user: User) -> bool:
        """
        Handle automatic credit recharge - like auto-reload on a metro card.
        This ensures users never run out of credits during high-usage periods.
        """
        try:
            credit_balance = user.credit_balance
            
            if not credit_balance.auto_recharge_enabled:
                return True  # Not an error, just not enabled
            
            if credit_balance.current_balance <= credit_balance.auto_recharge_threshold:
                success = cls.process_credit_purchase(user, credit_balance.auto_recharge_amount)
                
                if success:
                    logger.info(f"Auto-recharged ${credit_balance.auto_recharge_amount} for user {user.id}")
                else:
                    logger.error(f"Auto-recharge failed for user {user.id}")
                    # You might want to notify the user or disable auto-recharge
                
                return success
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling auto-recharge for user {user.id}: {e}")
            return False
    
    @classmethod
    def generate_invoice_pdf(cls, invoice: Invoice) -> Optional[bytes]:
        """
        Generate PDF invoice - like getting a receipt from a store.
        Important for enterprise customers who need formal invoices.
        """
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            from io import BytesIO
            
            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter
            
            # Header
            p.setFont("Helvetica-Bold", 16)
            p.drawString(50, height - 50, "INVOICE")
            
            p.setFont("Helvetica", 12)
            p.drawString(50, height - 80, f"Invoice #: {invoice.invoice_number}")
            p.drawString(50, height - 100, f"Date: {invoice.created_at.strftime('%Y-%m-%d')}")
            p.drawString(50, height - 120, f"Due Date: {invoice.due_date.strftime('%Y-%m-%d')}")
            
            # Customer info
            p.drawString(50, height - 160, "Bill To:")
            p.drawString(50, height - 180, f"{invoice.user.get_full_name() or invoice.user.username}")
            p.drawString(50, height - 200, f"{invoice.user.email}")
            
            # Line items
            y = height - 250
            p.drawString(50, y, "Description")
            p.drawString(300, y, "Quantity")
            p.drawString(400, y, "Unit Price")
            p.drawString(500, y, "Amount")
            
            y -= 20
            for item in invoice.line_items.all():
                p.drawString(50, y, item.description[:40])  # Truncate long descriptions
                p.drawString(300, y, str(item.quantity))
                p.drawString(400, y, f"${item.unit_price}")
                p.drawString(500, y, f"${item.amount}")
                y -= 20
            
            # Totals
            y -= 20
            p.drawString(400, y, f"Subtotal: ${invoice.subtotal}")
            y -= 20
            p.drawString(400, y, f"Tax: ${invoice.tax_amount}")
            y -= 20
            p.setFont("Helvetica-Bold", 12)
            p.drawString(400, y, f"Total: ${invoice.total_amount}")
            
            p.save()
            buffer.seek(0)
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error generating PDF for invoice {invoice.id}: {e}")
            return None
    
    @classmethod
    def get_billing_analytics(cls, user: User, start_date=None, end_date=None) -> Dict:
        """
        Get billing analytics - like your credit card spending report.
        Provides insights into usage patterns and costs for optimization.
        """
        try:
            if not start_date:
                start_date = timezone.now() - timedelta(days=30)
            if not end_date:
                end_date = timezone.now()
            
            # Get usage records for period
            usage_records = UsageRecord.objects.filter(
                user=user,
                timestamp__range=[start_date, end_date]
            )
            
            # Calculate metrics
            total_requests = usage_records.filter(record_type='api_request').count()
            total_tokens = sum(
                record.quantity for record in usage_records.filter(record_type='token_usage')
            )
            total_cost = sum(record.total_cost for record in usage_records)
            
            # Get performance metrics
            response_times = [
                record.response_time_ms for record in usage_records 
                if record.response_time_ms is not None
            ]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            # Get most used endpoints
            endpoint_usage = {}
            for record in usage_records.filter(record_type='api_request'):
                endpoint = record.api_endpoint or 'unknown'
                endpoint_usage[endpoint] = endpoint_usage.get(endpoint, 0) + 1
            
            return {
                'period': {
                    'start': start_date,
                    'end': end_date,
                },
                'usage': {
                    'total_requests': total_requests,
                    'total_tokens': float(total_tokens),
                    'total_cost': float(total_cost),
                    'avg_response_time_ms': avg_response_time,
                },
                'endpoints': dict(sorted(endpoint_usage.items(), key=lambda x: x[1], reverse=True)[:10]),
                'cost_breakdown': {
                    'api_requests': float(sum(
                        record.total_cost for record in usage_records.filter(record_type='api_request')
                    )),
                    'token_usage': float(sum(
                        record.total_cost for record in usage_records.filter(record_type='token_usage')
                    )),
                },
            }
            
        except Exception as e:
            logger.error(f"Error getting billing analytics for user {user.id}: {e}")
            return {}


class BillingCalculator:
    """
    A specialized calculator for complex billing scenarios - like a tax calculator.
    This handles the intricate math behind usage-based pricing for your platform.
    """
    
    @staticmethod
    def calculate_tiered_pricing(usage_amount: int, pricing_tiers: List[Dict]) -> Decimal:
        """
        Calculate tiered pricing - like progressive tax brackets.
        More usage = higher rates, encouraging efficient API usage.
        
        Example:
        - First 10K tokens: $0.001 per token
        - Next 90K tokens: $0.0008 per token  
        - Above 100K tokens: $0.0006 per token
        """
        total_cost = Decimal('0.00')
        remaining_usage = usage_amount
        
        for tier in sorted(pricing_tiers, key=lambda x: x['tier_start']):
            tier_start = tier['tier_start']
            tier_end = tier.get('tier_end')
            cost_per_unit = Decimal(str(tier['cost_per_unit']))
            
            if remaining_usage <= 0:
                break
            
            # Calculate usage in this tier
            if tier_end is None:
                # Unlimited tier
                tier_usage = remaining_usage
            else:
                tier_usage = min(remaining_usage, tier_end - tier_start)
            
            if tier_usage > 0:
                total_cost += tier_usage * cost_per_unit
                remaining_usage -= tier_usage
        
        return total_cost
    
    @staticmethod
    def estimate_monthly_cost(
        daily_requests: int, 
        avg_tokens_per_request: int, 
        pricing_tier
    ) -> Dict:
        """
        Estimate monthly costs - like a budget calculator for API usage.
        Helps users understand their potential costs before they hit limits.
        """
        monthly_requests = daily_requests * 30
        monthly_tokens = monthly_requests * avg_tokens_per_request
        
        base_cost = pricing_tier.base_monthly_cost
        
        # Calculate overage costs
        if monthly_tokens > pricing_tier.included_tokens_monthly:
            overage_tokens = monthly_tokens - pricing_tier.included_tokens_monthly
            overage_cost = (overage_tokens / 1000) * pricing_tier.cost_per_thousand_tokens
        else:
            overage_cost = Decimal('0.00')
        
        total_estimated_cost = base_cost + overage_cost
        
        return {
            'base_subscription': float(base_cost),
            'overage_charges': float(overage_cost),
            'total_estimated': float(total_estimated_cost),
            'usage_breakdown': {
                'monthly_requests': monthly_requests,
                'monthly_tokens': monthly_tokens,
                'included_tokens': pricing_tier.included_tokens_monthly,
                'overage_tokens': max(0, monthly_tokens - pricing_tier.included_tokens_monthly),
            }
        }