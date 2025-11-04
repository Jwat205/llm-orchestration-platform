# django-service/apps/billing/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Any
import stripe
import json
from datetime import datetime, timedelta

class PricingTier(models.Model):    
    TIER_TYPES = [
        ('free', 'Free Tier'),
        ('pay_per_use', 'Pay Per Use'),
        ('subscription', 'Monthly Subscription'),
        ('enterprise', 'Enterprise Custom')
    ]
    
    name = models.CharField(max_length=100)
    tier_type = models.CharField(max_length=20, choices=TIER_TYPES)
    description = models.TextField()
    
    # Pricing structure
    base_price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_per_token = models.DecimalField(max_digits=8, decimal_places=6, default=0)
    
    # Limits and features
    monthly_token_limit = models.IntegerField(default=0)  # 0 = unlimited
    requests_per_minute_limit = models.IntegerField(default=60)
    requests_per_day_limit = models.IntegerField(default=1000)
    
    # Feature flags
    has_streaming = models.BooleanField(default=True)
    has_function_calling = models.BooleanField(default=True)
    has_fine_tuning = models.BooleanField(default=False)
    has_priority_support = models.BooleanField(default=False)
    has_dedicated_instance = models.BooleanField(default=False)
    
    # Free tier included tokens
    free_tokens_monthly = models.IntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['base_price_monthly']
    
    def __str__(self):
        return f"{self.name} ({self.get_tier_type_display()})"
    
    def calculate_monthly_cost(self, token_usage: int) -> Decimal:
        """
        Calculate monthly cost - like calculating a restaurant bill
        
        This handles different pricing models:
        - Free tier: $0 up to limit
        - Pay-per-use: Only token costs
        - Subscription: Base fee + overage
        - Enterprise: Custom calculation
        """
        
        if self.tier_type == 'free':
            return Decimal('0.00')
        
        elif self.tier_type == 'pay_per_use':
            return Decimal(str(token_usage)) * self.price_per_token
        
        elif self.tier_type == 'subscription':
            base_cost = self.base_price_monthly
            
            # Calculate overage if usage exceeds included tokens
            if token_usage > self.free_tokens_monthly:
                overage_tokens = token_usage - self.free_tokens_monthly
                overage_cost = Decimal(str(overage_tokens)) * self.price_per_token
                return base_cost + overage_cost
            else:
                return base_cost
        
        elif self.tier_type == 'enterprise':
            # Enterprise pricing would be calculated based on custom contract
            return self.base_price_monthly
        
        return Decimal('0.00')


class UserSubscription(models.Model):
    """
    User subscription management - like restaurant membership cards
    
    This tracks each user's subscription status, billing cycle,
    and current usage against their limits
    """
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('canceled', 'Canceled'),
        ('past_due', 'Past Due'),
        ('suspended', 'Suspended'),
        ('trial', 'Trial Period')
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    pricing_tier = models.ForeignKey(PricingTier, on_delete=models.CASCADE)
    
    # Stripe integration
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    stripe_payment_method_id = models.CharField(max_length=100, blank=True)
    
    # Subscription details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()
    
    # Usage tracking (reset monthly)
    tokens_used_current_period = models.IntegerField(default=0)
    requests_made_current_period = models.IntegerField(default=0)
    
    # Billing
    auto_renew = models.BooleanField(default=True)
    billing_email = models.EmailField(blank=True)
    
    # Credits and discounts
    account_credits = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', 'current_period_end']),
            models.Index(fields=['stripe_customer_id']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.pricing_tier.name}"
    
    def is_within_limits(self) -> Dict[str, bool]:
        """
        Check if user is within their usage limits - like checking table capacity
        
        This prevents users from exceeding their plan limits,
        ensuring fair usage and preventing bill shock
        """
        
        limits_check = {
            'tokens': True,
            'requests_daily': True,
            'requests_monthly': True
        }
        
        # Check token limit
        if self.pricing_tier.monthly_token_limit > 0:
            limits_check['tokens'] = self.tokens_used_current_period < self.pricing_tier.monthly_token_limit
        
        # Check daily request limit
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_requests = Usage.objects.filter(
            subscription=self,
            created_at__gte=today_start
        ).count()
        
        limits_check['requests_daily'] = today_requests < self.pricing_tier.requests_per_day_limit
        
        # Monthly requests already tracked in requests_made_current_period
        limits_check['requests_monthly'] = True  # Could add monthly limit if needed
        
        return limits_check
    
    def get_usage_summary(self) -> Dict[str, Any]:
        """Get current usage summary - like a running bill total"""
        
        limits = self.is_within_limits()
        
        # Calculate current period cost
        current_cost = self.pricing_tier.calculate_monthly_cost(self.tokens_used_current_period)
        
        # Apply account credits
        final_cost = max(current_cost - self.account_credits, Decimal('0.00'))
        
        return {
            'current_period_start': self.current_period_start.isoformat(),
            'current_period_end': self.current_period_end.isoformat(),
            'tokens_used': self.tokens_used_current_period,
            'tokens_limit': self.pricing_tier.monthly_token_limit,
            'tokens_remaining': max(self.pricing_tier.monthly_token_limit - self.tokens_used_current_period, 0) if self.pricing_tier.monthly_token_limit > 0 else None,
            'current_cost': float(current_cost),
            'account_credits': float(self.account_credits),
            'final_cost': float(final_cost),
            'within_limits': limits,
            'days_remaining': (self.current_period_end - timezone.now()).days
        }
    
    def add_usage(self, tokens_used: int):
        """
        Add usage to subscription - like adding items to a bill
        
        This is called every time an API request is made
        to track usage against the user's plan
        """
        self.tokens_used_current_period += tokens_used
        self.requests_made_current_period += 1
        self.save(update_fields=['tokens_used_current_period', 'requests_made_current_period'])
    
    def reset_usage_for_new_period(self):
        """Reset usage counters for new billing period - like starting a fresh bill"""
        self.tokens_used_current_period = 0
        self.requests_made_current_period = 0
        self.current_period_start = timezone.now()
        self.current_period_end = self.current_period_start + timedelta(days=30)
        self.save()


class Usage(models.Model):
    """
    Detailed usage tracking - like individual receipt line items
    
    This records every API call for detailed billing analysis
    and usage reporting (supporting your 100M+ requests monthly)
    """
    
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name='usage_records')
    
    # Request details
    endpoint = models.CharField(max_length=200)
    model_name = models.CharField(max_length=100)
    tokens_input = models.IntegerField(default=0)
    tokens_output = models.IntegerField(default=0)
    tokens_total = models.IntegerField(default=0)
    
    # Performance metrics
    response_time_ms = models.IntegerField()
    status_code = models.IntegerField()
    
    # Costs
    cost_per_token = models.DecimalField(max_digits=8, decimal_places=6)
    total_cost = models.DecimalField(max_digits=10, decimal_places=4)
    
    # Metadata
    request_id = models.CharField(max_length=100, unique=True)
    user_agent = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['subscription', 'created_at']),
            models.Index(fields=['model_name', 'created_at']),
            models.Index(fields=['request_id']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.subscription.user.username} - {self.model_name} - {self.tokens_total} tokens"


class Invoice(models.Model):
    """
    Invoice management - like restaurant receipts and bills
    
    This generates and tracks invoices for subscription billing,
    overage charges, and one-time payments
    """
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('void', 'Void')
    ]
    
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name='invoices')
    
    # Invoice details
    invoice_number = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Billing period
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credits_applied = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Stripe integration
    stripe_invoice_id = models.CharField(max_length=100, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True)
    
    # Dates
    issue_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField()
    paid_date = models.DateTimeField(blank=True, null=True)
    
    # Files
    pdf_file = models.FileField(upload_to='invoices/', blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.subscription.user.username}"
    
    def generate_invoice_number(self):
        """Generate unique invoice number - like receipt numbering"""
        if not self.invoice_number:
            year_month = timezone.now().strftime('%Y%m')
            count = Invoice.objects.filter(
                invoice_number__startswith=f"INV-{year_month}"
            ).count() + 1
            self.invoice_number = f"INV-{year_month}-{count:04d}"
    
    def calculate_totals(self):
        """Calculate invoice totals - like tallying a restaurant bill"""
        # Get usage for the billing period
        usage_records = Usage.objects.filter(
            subscription=self.subscription,
            created_at__gte=self.period_start,
            created_at__lt=self.period_end
        )
        
        # Calculate base subscription cost
        total_tokens = sum(record.tokens_total for record in usage_records)
        self.subtotal = self.subscription.pricing_tier.calculate_monthly_cost(total_tokens)
        
        # Apply discounts (could be promotional or volume discounts)
        self.discount_amount = self._calculate_discounts()
        
        # Apply account credits
        available_credits = self.subscription.account_credits
        self.credits_applied = min(available_credits, self.subtotal - self.discount_amount)
        
        # Calculate tax (would integrate with tax service for accurate rates)
        taxable_amount = self.subtotal - self.discount_amount - self.credits_applied
        self.tax_amount = self._calculate_tax(taxable_amount)
        
        # Final total
        self.total_amount = max(
            self.subtotal - self.discount_amount - self.credits_applied + self.tax_amount,
            Decimal('0.00')
        )
    
    def _calculate_discounts(self) -> Decimal:
        """Calculate applicable discounts"""
        # This could include:
        # - Volume discounts for high usage
        # - Promotional discounts
        # - First-time user discounts
        # - Annual subscription discounts
        return Decimal('0.00')  # Placeholder
    
    def _calculate_tax(self, taxable_amount: Decimal) -> Decimal:
        """Calculate tax amount (integrate with tax service)"""
        # This would integrate with services like TaxJar or Avalara
        # For now, simple calculation (would need user's location)
        tax_rate = Decimal('0.08')  # 8% example rate
        return (taxable_amount * tax_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class PaymentMethod(models.Model):
    """
    Payment method management - like storing customer payment cards
    
    This securely stores payment method references (not actual card data)
    through Stripe for automatic billing
    """
    
    PAYMENT_TYPES = [
        ('card', 'Credit/Debit Card'),
        ('bank_account', 'Bank Account'),
        ('paypal', 'PayPal'),
        ('apple_pay', 'Apple Pay'),
        ('google_pay', 'Google Pay')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_methods')
    
    # Stripe references (secure - no sensitive data stored)
    stripe_payment_method_id = models.CharField(max_length=100)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    
    # Display information (masked/safe data from Stripe)
    card_brand = models.CharField(max_length=20, blank=True)  # visa, mastercard, etc.
    card_last4 = models.CharField(max_length=4, blank=True)
    card_exp_month = models.IntegerField(blank=True, null=True)
    card_exp_year = models.IntegerField(blank=True, null=True)
    
    # Status
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        if self.payment_type == 'card':
            return f"{self.card_brand.title()} ending in {self.card_last4}"
        return f"{self.get_payment_type_display()}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default payment method per user
        if self.is_default:
            PaymentMethod.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class CreditTransaction(models.Model):
    """
    Account credits management - like restaurant gift cards or store credit
    
    This tracks credit additions, usage, and refunds for flexible billing
    """
    
    TRANSACTION_TYPES = [
        ('credit_purchase', 'Credit Purchase'),
        ('credit_grant', 'Credit Grant'),
        ('credit_usage', 'Credit Usage'),
        ('refund', 'Refund'),
        ('bonus', 'Bonus Credit'),
        ('adjustment', 'Manual Adjustment')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='credit_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    
    # Amount (positive for additions, negative for usage)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Reference information
    reference_invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, blank=True, null=True)
    reference_id = models.CharField(max_length=100, blank=True)  # External reference
    description = models.TextField(blank=True)
    
    # Metadata
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='processed_credits')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_transaction_type_display()} - ${self.amount}"


# Stripe Integration Service
class StripeIntegration:
    """
    Stripe payment processing integration - like a credit card terminal
    
    This handles all Stripe interactions for payment processing,
    subscription management, and webhook handling
    """
    
    def __init__(self):
        # You'd set this from environment variables
        stripe.api_key = "sk_test_your_stripe_secret_key"  # Replace with actual key
    
    async def create_customer(self, user: User, email: str = None) -> str:
        """Create Stripe customer - like setting up a customer account"""
        try:
            customer = stripe.Customer.create(
                email=email or user.email,
                name=f"{user.first_name} {user.last_name}",
                metadata={
                    'user_id': user.id,
                    'username': user.username
                }
            )
            return customer.id
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create Stripe customer: {str(e)}")
    
    async def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """Create Stripe subscription - like setting up a monthly membership"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                payment_behavior='default_incomplete',
                payment_settings={'save_default_payment_method': 'on_subscription'},
                expand=['latest_invoice.payment_intent']
            )
            
            return {
                'subscription_id': subscription.id,
                'client_secret': subscription.latest_invoice.payment_intent.client_secret,
                'status': subscription.status
            }
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create subscription: {str(e)}")
    
    async def process_usage_billing(self, subscription_id: str, quantity: int) -> Dict[str, Any]:
        """Process usage-based billing - like billing for consumed items"""
        try:
            # Report usage to Stripe for metered billing
            stripe.SubscriptionItem.create_usage_record(
                subscription_id,
                quantity=quantity,
                timestamp=int(timezone.now().timestamp())
            )
            
            return {'success': True, 'quantity': quantity}
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to report usage: {str(e)}")
    
    async def create_invoice(self, customer_id: str, amount: int, description: str) -> Dict[str, Any]:
        """Create one-time invoice - like creating a custom bill"""
        try:
            # Create invoice item
            stripe.InvoiceItem.create(
                customer=customer_id,
                amount=amount,  # Amount in cents
                currency='usd',
                description=description
            )
            
            # Create and finalize invoice
            invoice = stripe.Invoice.create(
                customer=customer_id,
                auto_advance=True  # Automatically finalize and send
            )
            
            return {
                'invoice_id': invoice.id,
                'status': invoice.status,
                'invoice_url': invoice.hosted_invoice_url
            }
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create invoice: {str(e)}")
    
    async def handle_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        """
        Handle Stripe webhooks - like receiving payment confirmations
        
        This processes Stripe events to update subscription statuses,
        handle payment failures, etc.
        """
        endpoint_secret = "whsec_your_webhook_secret"  # Replace with actual secret
        
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError:
            raise Exception("Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise Exception("Invalid signature")
        
        # Handle the event
        if event['type'] == 'payment_intent.succeeded':
            await self._handle_payment_success(event['data']['object'])
        elif event['type'] == 'payment_intent.payment_failed':
            await self._handle_payment_failure(event['data']['object'])
        elif event['type'] == 'customer.subscription.updated':
            await self._handle_subscription_update(event['data']['object'])
        elif event['type'] == 'customer.subscription.deleted':
            await self._handle_subscription_cancellation(event['data']['object'])
        elif event['type'] == 'invoice.payment_succeeded':
            await self._handle_invoice_paid(event['data']['object'])
        elif event['type'] == 'invoice.payment_failed':
            await self._handle_invoice_payment_failed(event['data']['object'])
        
        return {'status': 'success', 'event_type': event['type']}
    
    async def _handle_payment_success(self, payment_intent):
        """Handle successful payment"""
        # Update invoice status, apply credits, etc.
        pass
    
    async def _handle_payment_failure(self, payment_intent):
        """Handle failed payment"""
        # Notify user, suspend service if needed, etc.
        pass
    
    async def _handle_subscription_update(self, subscription):
        """Handle subscription changes"""
        # Update user subscription status
        pass
    
    async def _handle_subscription_cancellation(self, subscription):
        """Handle subscription cancellation"""
        # Update user status, handle cancellation logic
        pass
    
    async def _handle_invoice_paid(self, invoice):
        """Handle successful invoice payment"""
        # Update invoice status, reset usage counters, etc.
        pass
    
    async def _handle_invoice_payment_failed(self, invoice):
        """Handle failed invoice payment"""
        # Notify user, implement retry logic, etc.
        pass


# Billing Service for calculating costs and managing billing cycles
class BillingService:
    """
    Main billing service - like the restaurant's accounting department
    
    This orchestrates all billing operations and ensures accurate
    cost calculation for your high-volume API usage
    """
    
    def __init__(self):
        self.stripe_integration = StripeIntegration()
    
    async def calculate_usage_cost(self, user: User, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Calculate usage cost for a period - like calculating a monthly restaurant bill
        
        This handles the complex pricing logic for different models and usage patterns
        """
        try:
            subscription = UserSubscription.objects.get(user=user)
        except UserSubscription.DoesNotExist:
            return {'error': 'No subscription found'}
        
        # Get usage records for the period
        usage_records = Usage.objects.filter(
            subscription=subscription,
            created_at__gte=start_date,
            created_at__lt=end_date
        )
        
        # Calculate costs by model
        model_costs = {}
        total_tokens = 0
        total_requests = usage_records.count()
        
        for record in usage_records:
            model_name = record.model_name
            if model_name not in model_costs:
                model_costs[model_name] = {
                    'tokens': 0,
                    'requests': 0,
                    'cost': Decimal('0.00')
                }
            
            model_costs[model_name]['tokens'] += record.tokens_total
            model_costs[model_name]['requests'] += 1
            model_costs[model_name]['cost'] += record.total_cost
            total_tokens += record.tokens_total
        
        # Calculate total cost using pricing tier
        total_cost = subscription.pricing_tier.calculate_monthly_cost(total_tokens)
        
        return {
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'total_tokens': total_tokens,
            'total_requests': total_requests,
            'total_cost': float(total_cost),
            'model_breakdown': {
                model: {
                    'tokens': data['tokens'],
                    'requests': data['requests'],
                    'cost': float(data['cost'])
                }
                for model, data in model_costs.items()
            },
            'pricing_tier': subscription.pricing_tier.name
        }
    
    async def generate_monthly_invoice(self, subscription: UserSubscription) -> Invoice:
        """Generate monthly invoice - like preparing a monthly membership bill"""
        
        # Create invoice
        invoice = Invoice(
            subscription=subscription,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            due_date=subscription.current_period_end + timedelta(days=7)
        )
        
        invoice.generate_invoice_number()
        invoice.calculate_totals()
        invoice.save()
        
        # Create Stripe invoice if needed
        if subscription.stripe_customer_id and invoice.total_amount > 0:
            stripe_invoice = await self.stripe_integration.create_invoice(
                customer_id=subscription.stripe_customer_id,
                amount=int(invoice.total_amount * 100),  # Convert to cents
                description=f"API Usage - {invoice.period_start.strftime('%B %Y')}"
            )
            invoice.stripe_invoice_id = stripe_invoice['invoice_id']
            invoice.save()
        
        return invoice
    
    async def process_overage_billing(self, subscription: UserSubscription) -> Optional[Invoice]:
        """Process overage billing for users who exceed their plan limits"""
        
        limits = subscription.is_within_limits()
        
        # Only bill for overages if user has exceeded token limits
        if limits['tokens'] or subscription.pricing_tier.monthly_token_limit == 0:
            return None
        
        # Calculate overage amount
        overage_tokens = subscription.tokens_used_current_period - subscription.pricing_tier.monthly_token_limit
        overage_cost = Decimal(str(overage_tokens)) * subscription.pricing_tier.price_per_token
        
        if overage_cost <= 0:
            return None
        
        # Create overage invoice
        invoice = Invoice(
            subscription=subscription,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            subtotal=overage_cost,
            total_amount=overage_cost,
            due_date=timezone.now() + timedelta(days=7)
        )
        
        invoice.generate_invoice_number()
        invoice.save()
        
        return invoice
    
    async def apply_credits(self, user: User, amount: Decimal, transaction_type: str, description: str = "") -> CreditTransaction:
        """Apply credits to user account - like adding store credit"""
        
        try:
            subscription = UserSubscription.objects.get(user=user)
        except UserSubscription.DoesNotExist:
            raise Exception("No subscription found")
        
        # Calculate new balance
        new_balance = subscription.account_credits + amount
        
        # Create credit transaction
        transaction = CreditTransaction.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=amount,
            balance_after=new_balance,
            description=description
        )
        
        # Update subscription credits
        subscription.account_credits = new_balance
        subscription.save(update_fields=['account_credits'])
        
        return transaction
    
    async def get_billing_analytics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get billing analytics - like restaurant revenue analysis
        
        This provides insights into revenue, usage patterns, and optimization opportunities
        """
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Revenue analytics
        invoices = Invoice.objects.filter(
            created_at__gte=start_date,
            status='paid'
        )
        
        total_revenue = sum(invoice.total_amount for invoice in invoices)
        
        # Usage analytics
        usage_records = Usage.objects.filter(created_at__gte=start_date)
        total_tokens = sum(record.tokens_total for record in usage_records)
        total_requests = usage_records.count()
        
        # Model popularity
        model_usage = {}
        for record in usage_records:
            model_name = record.model_name
            if model_name not in model_usage:
                model_usage[model_name] = {'requests': 0, 'tokens': 0, 'revenue': Decimal('0.00')}
            
            model_usage[model_name]['requests'] += 1
            model_usage[model_name]['tokens'] += record.tokens_total
            model_usage[model_name]['revenue'] += record.total_cost
        
        # Subscription distribution
        subscription_tiers = {}
        for subscription in UserSubscription.objects.filter(status='active'):
            tier_name = subscription.pricing_tier.name
            if tier_name not in subscription_tiers:
                subscription_tiers[tier_name] = 0
            subscription_tiers[tier_name] += 1
        
        return {
            'period_days': days,
            'total_revenue': float(total_revenue),
            'total_tokens': total_tokens,
            'total_requests': total_requests,
            'average_revenue_per_request': float(total_revenue / max(total_requests, 1)),
            'model_usage': {
                model: {
                    'requests': data['requests'],
                    'tokens': data['tokens'],
                    'revenue': float(data['revenue'])
                }
                for model, data in model_usage.items()
            },
            'subscription_distribution': subscription_tiers,
            'invoices_generated': invoices.count()
        }


