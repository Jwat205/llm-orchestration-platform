"""
Revenue Forecasting Engine
Predicts future revenue, usage patterns, and business metrics
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
import json

logger = logging.getLogger(__name__)

class ForecastPeriod(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

class ForecastMethod(Enum):
    LINEAR_REGRESSION = "linear_regression"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    MOVING_AVERAGE = "moving_average"
    SEASONAL_DECOMPOSITION = "seasonal_decomposition"
    ARIMA = "arima"

@dataclass
class ForecastResult:
    period: ForecastPeriod
    method: ForecastMethod
    predictions: List[float]
    confidence_intervals: List[Tuple[float, float]]
    accuracy_metrics: Dict[str, float]
    dates: List[datetime]
    metadata: Dict[str, Any]

@dataclass
class RevenueMetrics:
    total_revenue: Decimal
    recurring_revenue: Decimal
    one_time_revenue: Decimal
    avg_revenue_per_user: Decimal
    growth_rate: float
    churn_rate: float
    ltv: Decimal  # Customer Lifetime Value
    cac: Decimal  # Customer Acquisition Cost

class ForecastEngine:
    """Advanced revenue and usage forecasting engine"""
    
    def __init__(self):
        self.models = {}
        self.historical_data = {}
        
    async def forecast_revenue(
        self,
        historical_revenue: List[Dict],
        forecast_periods: int,
        method: ForecastMethod = ForecastMethod.EXPONENTIAL_SMOOTHING,
        period: ForecastPeriod = ForecastPeriod.MONTHLY
    ) -> ForecastResult:
        """Generate revenue forecast"""
        try:
            # Prepare data
            df = pd.DataFrame(historical_revenue)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').set_index('date')
            
            # Resample based on period
            period_map = {
                ForecastPeriod.DAILY: 'D',
                ForecastPeriod.WEEKLY: 'W',
                ForecastPeriod.MONTHLY: 'M',
                ForecastPeriod.QUARTERLY: 'Q',
                ForecastPeriod.YEARLY: 'Y'
            }
            
            df_resampled = df.resample(period_map[period]).sum()
            revenue_values = df_resampled['revenue'].values
            
            # Apply forecasting method
            if method == ForecastMethod.LINEAR_REGRESSION:
                predictions, confidence_intervals = self._linear_regression_forecast(
                    revenue_values, forecast_periods
                )
            elif method == ForecastMethod.EXPONENTIAL_SMOOTHING:
                predictions, confidence_intervals = self._exponential_smoothing_forecast(
                    revenue_values, forecast_periods
                )
            elif method == ForecastMethod.MOVING_AVERAGE:
                predictions, confidence_intervals = self._moving_average_forecast(
                    revenue_values, forecast_periods
                )
            elif method == ForecastMethod.SEASONAL_DECOMPOSITION:
                predictions, confidence_intervals = self._seasonal_decomposition_forecast(
                    revenue_values, forecast_periods
                )
            else:
                raise ValueError(f"Unsupported forecasting method: {method}")
            
            # Generate future dates
            last_date = df_resampled.index[-1]
            future_dates = []
            for i in range(1, forecast_periods + 1):
                if period == ForecastPeriod.DAILY:
                    future_dates.append(last_date + timedelta(days=i))
                elif period == ForecastPeriod.WEEKLY:
                    future_dates.append(last_date + timedelta(weeks=i))
                elif period == ForecastPeriod.MONTHLY:
                    future_dates.append(last_date + pd.DateOffset(months=i))
                elif period == ForecastPeriod.QUARTERLY:
                    future_dates.append(last_date + pd.DateOffset(months=i*3))
                elif period == ForecastPeriod.YEARLY:
                    future_dates.append(last_date + pd.DateOffset(years=i))
            
            # Calculate accuracy metrics
            accuracy_metrics = self._calculate_accuracy_metrics(
                revenue_values, method
            )
            
            logger.info(f"Revenue forecast completed: {len(predictions)} periods")
            
            return ForecastResult(
                period=period,
                method=method,
                predictions=predictions,
                confidence_intervals=confidence_intervals,
                accuracy_metrics=accuracy_metrics,
                dates=future_dates,
                metadata={
                    'historical_periods': len(revenue_values),
                    'forecast_periods': forecast_periods,
                    'data_quality_score': self._assess_data_quality(revenue_values)
                }
            )
            
        except Exception as e:
            logger.error(f"Error in revenue forecasting: {str(e)}")
            raise
    
    def _linear_regression_forecast(
        self, 
        data: np.ndarray, 
        periods: int
    ) -> Tuple[List[float], List[Tuple[float, float]]]:
        """Linear regression forecasting"""
        x = np.arange(len(data))
        y = data
        
        # Fit linear regression
        coeffs = np.polyfit(x, y, 1)
        
        # Generate predictions
        future_x = np.arange(len(data), len(data) + periods)
        predictions = np.polyval(coeffs, future_x)
        
        # Calculate residuals for confidence intervals
        fitted_values = np.polyval(coeffs, x)
        residuals = y - fitted_values
        std_error = np.std(residuals)
        
        # Generate confidence intervals (95%)
        confidence_intervals = [
            (pred - 1.96 * std_error, pred + 1.96 * std_error)
            for pred in predictions
        ]
        
        return predictions.tolist(), confidence_intervals
    
    def _exponential_smoothing_forecast(
        self, 
        data: np.ndarray, 
        periods: int,
        alpha: float = 0.3
    ) -> Tuple[List[float], List[Tuple[float, float]]]:
        """Exponential smoothing forecasting"""
        # Initialize
        smoothed = [data[0]]
        
        # Apply exponential smoothing
        for i in range(1, len(data)):
            smoothed.append(alpha * data[i] + (1 - alpha) * smoothed[-1])
        
        # Generate predictions
        predictions = []
        last_smoothed = smoothed[-1]
        
        for _ in range(periods):
            predictions.append(last_smoothed)
        
        # Simple confidence intervals based on historical variance
        variance = np.var(data)
        std_dev = np.sqrt(variance)
        
        confidence_intervals = [
            (pred - 1.96 * std_dev, pred + 1.96 * std_dev)
            for pred in predictions
        ]
        
        return predictions, confidence_intervals
    
    def _moving_average_forecast(
        self, 
        data: np.ndarray, 
        periods: int,
        window: int = 5
    ) -> Tuple[List[float], List[Tuple[float, float]]]:
        """Moving average forecasting"""
        # Calculate moving average
        if len(data) < window:
            window = len(data)
        
        moving_avg = np.mean(data[-window:])
        
        # Generate predictions (flat forecast)
        predictions = [moving_avg] * periods
        
        # Calculate confidence intervals based on historical variance
        variance = np.var(data[-window:])
        std_dev = np.sqrt(variance)
        
        confidence_intervals = [
            (pred - 1.96 * std_dev, pred + 1.96 * std_dev)
            for pred in predictions
        ]
        
        return predictions, confidence_intervals
    
    def _seasonal_decomposition_forecast(
        self, 
        data: np.ndarray, 
        periods: int
    ) -> Tuple[List[float], List[Tuple[float, float]]]:
        """Seasonal decomposition forecasting"""
        # Simple seasonal pattern detection
        if len(data) < 12:
            # Not enough data for seasonal analysis, fall back to linear regression
            return self._linear_regression_forecast(data, periods)
        
        # Detect seasonality (assume monthly data)
        season_length = min(12, len(data) // 2)
        
        # Calculate seasonal indices
        seasonal_indices = []
        for i in range(season_length):
            season_values = [data[j] for j in range(i, len(data), season_length)]
            seasonal_indices.append(np.mean(season_values))
        
        # Deseasonalize data
        deseasonalized = []
        overall_mean = np.mean(data)
        
        for i, value in enumerate(data):
            season_idx = i % season_length
            season_factor = seasonal_indices[season_idx] / overall_mean if overall_mean != 0 else 1
            deseasonalized.append(value / season_factor if season_factor != 0 else value)
        
        # Forecast trend
        trend_predictions, _ = self._linear_regression_forecast(
            np.array(deseasonalized), periods
        )
        
        # Reseasonalize predictions
        predictions = []
        for i, trend_pred in enumerate(trend_predictions):
            season_idx = (len(data) + i) % season_length
            season_factor = seasonal_indices[season_idx] / overall_mean if overall_mean != 0 else 1
            predictions.append(trend_pred * season_factor)
        
        # Calculate confidence intervals
        variance = np.var(data)
        std_dev = np.sqrt(variance)
        
        confidence_intervals = [
            (pred - 1.96 * std_dev, pred + 1.96 * std_dev)
            for pred in predictions
        ]
        
        return predictions, confidence_intervals
    
    def _calculate_accuracy_metrics(
        self, 
        historical_data: np.ndarray, 
        method: ForecastMethod
    ) -> Dict[str, float]:
        """Calculate forecasting accuracy metrics"""
        if len(historical_data) < 4:
            return {'mape': 0, 'rmse': 0, 'mae': 0}
        
        # Use last 25% of data for validation
        split_point = int(len(historical_data) * 0.75)
        train_data = historical_data[:split_point]
        test_data = historical_data[split_point:]
        
        # Generate predictions for test period
        if method == ForecastMethod.LINEAR_REGRESSION:
            predictions, _ = self._linear_regression_forecast(train_data, len(test_data))
        elif method == ForecastMethod.EXPONENTIAL_SMOOTHING:
            predictions, _ = self._exponential_smoothing_forecast(train_data, len(test_data))
        elif method == ForecastMethod.MOVING_AVERAGE:
            predictions, _ = self._moving_average_forecast(train_data, len(test_data))
        else:
            predictions, _ = self._seasonal_decomposition_forecast(train_data, len(test_data))
        
        # Calculate metrics
        predictions = np.array(predictions)
        
        # Mean Absolute Percentage Error
        mape = np.mean(np.abs((test_data - predictions) / test_data)) * 100 if np.all(test_data != 0) else 0
        
        # Root Mean Square Error
        rmse = np.sqrt(np.mean((test_data - predictions) ** 2))
        
        # Mean Absolute Error
        mae = np.mean(np.abs(test_data - predictions))
        
        return {
            'mape': float(mape),
            'rmse': float(rmse),
            'mae': float(mae)
        }
    
    def _assess_data_quality(self, data: np.ndarray) -> float:
        """Assess the quality of historical data for forecasting"""
        if len(data) == 0:
            return 0.0
        
        # Check for sufficient data points
        length_score = min(1.0, len(data) / 24)  # Prefer at least 24 periods
        
        # Check for missing values (assuming no NaN in this simple case)
        completeness_score = 1.0
        
        # Check for variance (data should have some variation)
        variance_score = min(1.0, np.var(data) / (np.mean(data) ** 2)) if np.mean(data) != 0 else 0
        
        # Check for outliers
        q75, q25 = np.percentile(data, [75, 25])
        iqr = q75 - q25
        outlier_bounds = [q25 - 1.5 * iqr, q75 + 1.5 * iqr]
        outlier_count = np.sum((data < outlier_bounds[0]) | (data > outlier_bounds[1]))
        outlier_score = max(0, 1.0 - (outlier_count / len(data)))
        
        # Combine scores
        overall_score = (length_score + completeness_score + variance_score + outlier_score) / 4
        
        return float(overall_score)
    
    async def forecast_usage_patterns(
        self,
        historical_usage: List[Dict],
        forecast_periods: int,
        metrics: List[str] = None
    ) -> Dict[str, ForecastResult]:
        """Forecast usage patterns for multiple metrics"""
        if metrics is None:
            metrics = ['requests', 'tokens', 'users', 'api_calls']
        
        forecasts = {}
        
        for metric in metrics:
            try:
                # Filter data for specific metric
                metric_data = [
                    {'date': item['date'], 'value': item.get(metric, 0)}
                    for item in historical_usage
                ]
                
                # Generate forecast
                forecast = await self._forecast_single_metric(
                    metric_data, forecast_periods, metric
                )
                forecasts[metric] = forecast
                
            except Exception as e:
                logger.error(f"Error forecasting {metric}: {str(e)}")
                continue
        
        return forecasts
    
    async def _forecast_single_metric(
        self,
        metric_data: List[Dict],
        forecast_periods: int,
        metric_name: str
    ) -> ForecastResult:
        """Forecast a single metric"""
        # Convert to revenue format for compatibility
        revenue_format = [
            {'date': item['date'], 'revenue': item['value']}
            for item in metric_data
        ]
        
        # Use exponential smoothing for usage metrics
        return await self.forecast_revenue(
            revenue_format,
            forecast_periods,
            ForecastMethod.EXPONENTIAL_SMOOTHING,
            ForecastPeriod.DAILY
        )
    
    async def calculate_revenue_metrics(
        self,
        customer_data: List[Dict],
        revenue_data: List[Dict],
        period_days: int = 30
    ) -> RevenueMetrics:
        """Calculate comprehensive revenue metrics"""
        try:
            # Calculate total revenue
            total_revenue = sum(Decimal(str(r['amount'])) for r in revenue_data)
            
            # Separate recurring vs one-time revenue
            recurring_revenue = sum(
                Decimal(str(r['amount'])) 
                for r in revenue_data 
                if r.get('type') == 'subscription'
            )
            one_time_revenue = total_revenue - recurring_revenue
            
            # Calculate ARPU (Average Revenue Per User)
            active_users = len(set(c['user_id'] for c in customer_data))
            avg_revenue_per_user = total_revenue / active_users if active_users > 0 else Decimal('0')
            
            # Calculate growth rate
            growth_rate = await self._calculate_growth_rate(revenue_data, period_days)
            
            # Calculate churn rate
            churn_rate = await self._calculate_churn_rate(customer_data, period_days)
            
            # Calculate LTV (Customer Lifetime Value)
            ltv = await self._calculate_ltv(avg_revenue_per_user, churn_rate)
            
            # Calculate CAC (Customer Acquisition Cost)
            cac = await self._calculate_cac(customer_data, revenue_data)
            
            return RevenueMetrics(
                total_revenue=total_revenue,
                recurring_revenue=recurring_revenue,
                one_time_revenue=one_time_revenue,
                avg_revenue_per_user=avg_revenue_per_user,
                growth_rate=growth_rate,
                churn_rate=churn_rate,
                ltv=ltv,
                cac=cac
            )
            
        except Exception as e:
            logger.error(f"Error calculating revenue metrics: {str(e)}")
            raise
    
    async def _calculate_growth_rate(
        self,
        revenue_data: List[Dict],
        period_days: int
    ) -> float:
        """Calculate revenue growth rate"""
        try:
            # Sort by date
            sorted_data = sorted(revenue_data, key=lambda x: x['date'])
            
            if len(sorted_data) < 2:
                return 0.0
            
            # Split into periods
            current_date = datetime.now()
            current_period_start = current_date - timedelta(days=period_days)
            previous_period_start = current_period_start - timedelta(days=period_days)
            
            current_revenue = sum(
                Decimal(str(r['amount']))
                for r in sorted_data
                if datetime.fromisoformat(r['date']) >= current_period_start
            )
            
            previous_revenue = sum(
                Decimal(str(r['amount']))
                for r in sorted_data
                if previous_period_start <= datetime.fromisoformat(r['date']) < current_period_start
            )
            
            if previous_revenue == 0:
                return 100.0 if current_revenue > 0 else 0.0
            
            growth_rate = float((current_revenue - previous_revenue) / previous_revenue * 100)
            return growth_rate
            
        except Exception as e:
            logger.error(f"Error calculating growth rate: {str(e)}")
            return 0.0
    
    async def _calculate_churn_rate(
        self,
        customer_data: List[Dict],
        period_days: int
    ) -> float:
        """Calculate customer churn rate"""
        try:
            current_date = datetime.now()
            period_start = current_date - timedelta(days=period_days)
            
            # Get active customers at start of period
            active_at_start = set()
            for customer in customer_data:
                last_activity = datetime.fromisoformat(customer.get('last_activity', customer['date']))
                if last_activity >= period_start - timedelta(days=period_days):
                    active_at_start.add(customer['user_id'])
            
            # Get churned customers (no activity in current period)
            churned_customers = set()
            for customer_id in active_at_start:
                customer_activities = [
                    c for c in customer_data 
                    if c['user_id'] == customer_id
                ]
                
                last_activity = max(
                    datetime.fromisoformat(c.get('last_activity', c['date']))
                    for c in customer_activities
                )
                
                if last_activity < period_start:
                    churned_customers.add(customer_id)
            
            if len(active_at_start) == 0:
                return 0.0
            
            churn_rate = len(churned_customers) / len(active_at_start) * 100
            return churn_rate
            
        except Exception as e:
            logger.error(f"Error calculating churn rate: {str(e)}")
            return 0.0
    
    async def _calculate_ltv(
        self,
        avg_revenue_per_user: Decimal,
        churn_rate: float
    ) -> Decimal:
        """Calculate Customer Lifetime Value"""
        if churn_rate == 0:
            # Assume 5% monthly churn if no churn data
            churn_rate = 5.0
        
        # Convert annual churn to monthly
        monthly_churn = churn_rate / 12.0 / 100.0
        
        if monthly_churn == 0:
            monthly_churn = 0.05  # Default 5% monthly churn
        
        # LTV = ARPU / Churn Rate
        ltv = avg_revenue_per_user / Decimal(str(monthly_churn))
        
        return ltv
    
    async def _calculate_cac(
        self,
        customer_data: List[Dict],
        revenue_data: List[Dict]
    ) -> Decimal:
        """Calculate Customer Acquisition Cost"""
        try:
            # This is a simplified CAC calculation
            # In practice, you'd need marketing spend data
            
            # Estimate based on revenue and customer count
            total_revenue = sum(Decimal(str(r['amount'])) for r in revenue_data)
            unique_customers = len(set(c['user_id'] for c in customer_data))
            
            if unique_customers == 0:
                return Decimal('0')
            
            # Assume 20% of revenue goes to customer acquisition
            estimated_acquisition_cost = total_revenue * Decimal('0.2')
            cac = estimated_acquisition_cost / unique_customers
            
            return cac
            
        except Exception as e:
            logger.error(f"Error calculating CAC: {str(e)}")
            return Decimal('0')
    
    async def predict_customer_lifetime_value(
        self,
        customer_id: str,
        historical_data: List[Dict]
    ) -> Dict[str, Any]:
        """Predict individual customer lifetime value"""
        try:
            # Filter customer data
            customer_data = [
                d for d in historical_data 
                if d.get('customer_id') == customer_id
            ]
            
            if not customer_data:
                return {'ltv': 0, 'confidence': 0, 'risk_score': 1.0}
            
            # Calculate customer metrics
            total_spent = sum(Decimal(str(d.get('amount', 0))) for d in customer_data)
            purchase_frequency = len(customer_data)
            avg_order_value = total_spent / purchase_frequency if purchase_frequency > 0 else Decimal('0')
            
            # Calculate time span
            dates = [datetime.fromisoformat(d['date']) for d in customer_data]
            date_range = (max(dates) - min(dates)).days
            
            # Predict future behavior
            if date_range > 0:
                purchase_rate = purchase_frequency / date_range
                predicted_lifetime = 365 / (purchase_rate * 365) if purchase_rate > 0 else 365
                predicted_ltv = float(avg_order_value) * purchase_frequency * (predicted_lifetime / date_range)
            else:
                predicted_ltv = float(total_spent)
            
            # Calculate confidence score
            confidence = min(1.0, purchase_frequency / 10.0)  # Higher confidence with more data
            
            # Calculate churn risk
            days_since_last_purchase = (datetime.now() - max(dates)).days
            risk_score = min(1.0, days_since_last_purchase / 90.0)  # Higher risk with longer absence
            
            return {
                'ltv': predicted_ltv,
                'confidence': confidence,
                'risk_score': risk_score,
                'total_spent': float(total_spent),
                'purchase_frequency': purchase_frequency,
                'avg_order_value': float(avg_order_value),
                'days_since_last_purchase': days_since_last_purchase
            }
            
        except Exception as e:
            logger.error(f"Error predicting customer LTV: {str(e)}")
            return {'ltv': 0, 'confidence': 0, 'risk_score': 1.0}
    
    async def forecast_capacity_needs(
        self,
        usage_data: List[Dict],
        forecast_periods: int,
        resource_type: str = "compute"
    ) -> Dict[str, Any]:
        """Forecast infrastructure capacity needs"""
        try:
            # Prepare usage data
            df = pd.DataFrame(usage_data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').set_index('date')
            
            # Resample to daily data
            daily_usage = df.resample('D').sum()
            
            # Forecast usage
            usage_forecast = await self._forecast_single_metric(
                [{'date': str(date), 'value': usage} 
                 for date, usage in daily_usage['usage'].items()],
                forecast_periods,
                'usage'
            )
            
            # Calculate capacity requirements
            peak_usage = max(usage_forecast.predictions)
            avg_usage = np.mean(usage_forecast.predictions)
            
            # Add safety margin
            safety_margin = 0.25  # 25% buffer
            recommended_capacity = peak_usage * (1 + safety_margin)
            
            return {
                'forecast_periods': forecast_periods,
                'predicted_peak_usage': peak_usage,
                'predicted_avg_usage': avg_usage,
                'recommended_capacity': recommended_capacity,
                'current_capacity_utilization': avg_usage / peak_usage if peak_usage > 0 else 0,
                'scaling_recommendations': self._generate_scaling_recommendations(
                    usage_forecast.predictions
                )
            }
            
        except Exception as e:
            logger.error(f"Error forecasting capacity needs: {str(e)}")
            raise
    
    def _generate_scaling_recommendations(
        self,
        usage_predictions: List[float]
    ) -> List[Dict[str, Any]]:
        """Generate infrastructure scaling recommendations"""
        recommendations = []
        
        # Analyze usage patterns
        max_usage = max(usage_predictions)
        min_usage = min(usage_predictions)
        avg_usage = np.mean(usage_predictions)
        
        # Peak usage recommendation
        if max_usage > avg_usage * 2:
            recommendations.append({
                'type': 'auto_scaling',
                'priority': 'high',
                'description': 'High peak usage detected. Enable auto-scaling to handle traffic spikes.',
                'expected_benefit': 'Improved performance during peak times'
            })
        
        # Consistent high usage
        if min_usage > avg_usage * 0.8:
            recommendations.append({
                'type': 'baseline_increase',
                'priority': 'medium',
                'description': 'Consistently high usage. Consider increasing baseline capacity.',
                'expected_benefit': 'Better overall performance and cost efficiency'
            })
        
        # Variable usage patterns
        usage_variance = np.var(usage_predictions)
        if usage_variance > avg_usage:
            recommendations.append({
                'type': 'predictive_scaling',
                'priority': 'medium',
                'description': 'Variable usage patterns detected. Implement predictive scaling.',
                'expected_benefit': 'Proactive scaling based on predicted demand'
            })
        
        return recommendations

# Example usage and utility functions
async def main():
    """Example usage of the ForecastEngine"""
    engine = ForecastEngine()
    
    # Example historical revenue data
    historical_revenue = [
        {'date': '2024-01-01', 'revenue': 10000},
        {'date': '2024-02-01', 'revenue': 12000},
        {'date': '2024-03-01', 'revenue': 11500},
        {'date': '2024-04-01', 'revenue': 13000},
        {'date': '2024-05-01', 'revenue': 14500},
        {'date': '2024-06-01', 'revenue': 15000},
    ]
    
    # Generate revenue forecast
    forecast = await engine.forecast_revenue(
        historical_revenue,
        forecast_periods=6,
        method=ForecastMethod.EXPONENTIAL_SMOOTHING,
        period=ForecastPeriod.MONTHLY
    )
    
    print(f"Revenue Forecast for next 6 months:")
    for i, (date, prediction) in enumerate(zip(forecast.dates, forecast.predictions)):
        lower, upper = forecast.confidence_intervals[i]
        print(f"{date.strftime('%Y-%m')}: ${prediction:,.2f} (${lower:,.2f} - ${upper:,.2f})")
    
    print(f"\nAccuracy Metrics:")
    for metric, value in forecast.accuracy_metrics.items():
        print(f"{metric.upper()}: {value:.2f}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())