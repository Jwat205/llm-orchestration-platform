"""
Anomaly Detection System
ML-based anomaly detection for security monitoring
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import logging
from collections import defaultdict, deque
import json
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
import pickle


logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of anomalies"""
    USER_BEHAVIOR = "user_behavior"
    NETWORK_TRAFFIC = "network_traffic"
    API_USAGE = "api_usage"
    RESOURCE_CONSUMPTION = "resource_consumption"
    TIME_BASED = "time_based"
    GEOGRAPHIC = "geographic"


class AnomalySeverity(Enum):
    """Anomaly severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class AnomalyEvent:
    """Anomaly event data class"""
    id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    timestamp: datetime
    description: str
    features: Dict[str, float]
    anomaly_score: float
    threshold: float
    affected_entity: str
    context: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['anomaly_type'] = self.anomaly_type.value
        data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


class FeatureExtractor:
    """Extract features for anomaly detection"""
    
    def __init__(self):
        self.feature_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
    
    def extract_user_behavior_features(self, user_events: List[Dict[str, Any]]) -> Dict[str, float]:
        """Extract user behavior features"""
        if not user_events:
            return {}
        
        # Time-based features
        timestamps = [datetime.fromisoformat(event['timestamp']) for event in user_events]
        time_diffs = [(timestamps[i] - timestamps[i-1]).total_seconds() 
                     for i in range(1, len(timestamps))]
        
        # Request patterns
        endpoints = [event.get('endpoint', '') for event in user_events]
        methods = [event.get('method', '') for event in user_events]
        status_codes = [event.get('status_code', 200) for event in user_events]
        
        features = {
            'request_count': len(user_events),
            'avg_time_between_requests': np.mean(time_diffs) if time_diffs else 0,
            'std_time_between_requests': np.std(time_diffs) if time_diffs else 0,
            'unique_endpoints': len(set(endpoints)),
            'error_rate': sum(1 for code in status_codes if code >= 400) / len(status_codes),
            'distinct_methods': len(set(methods)),
            'session_duration': (timestamps[-1] - timestamps[0]).total_seconds() if len(timestamps) > 1 else 0
        }
        
        return features
    
    def extract_api_usage_features(self, api_events: List[Dict[str, Any]]) -> Dict[str, float]:
        """Extract API usage features"""
        if not api_events:
            return {}
        
        # Rate and volume features
        response_times = [event.get('response_time', 0) for event in api_events]
        payload_sizes = [event.get('payload_size', 0) for event in api_events]
        
        # Error patterns
        status_codes = [event.get('status_code', 200) for event in api_events]
        error_events = [event for event in api_events if event.get('status_code', 200) >= 400]
        
        features = {
            'requests_per_minute': len(api_events),
            'avg_response_time': np.mean(response_times),
            'max_response_time': np.max(response_times) if response_times else 0,
            'avg_payload_size': np.mean(payload_sizes) if payload_sizes else 0,
            'error_rate': len(error_events) / len(api_events),
            'rate_limit_hits': sum(1 for event in api_events if event.get('status_code') == 429),
            'unique_user_agents': len(set(event.get('user_agent', '') for event in api_events))
        }
        
        return features
    
    def extract_network_features(self, network_events: List[Dict[str, Any]]) -> Dict[str, float]:
        """Extract network traffic features"""
        if not network_events:
            return {}
        
        # Traffic volume
        bytes_sent = [event.get('bytes_sent', 0) for event in network_events]
        bytes_received = [event.get('bytes_received', 0) for event in network_events]
        
        # Connection patterns
        source_ips = [event.get('source_ip', '') for event in network_events]
        dest_ports = [event.get('dest_port', 0) for event in network_events]
        
        features = {
            'total_connections': len(network_events),
            'total_bytes_sent': sum(bytes_sent),
            'total_bytes_received': sum(bytes_received),
            'avg_bytes_per_connection': np.mean(bytes_sent + bytes_received) if (bytes_sent + bytes_received) else 0,
            'unique_source_ips': len(set(source_ips)),
            'unique_dest_ports': len(set(dest_ports)),
            'traffic_ratio': sum(bytes_sent) / max(sum(bytes_received), 1)
        }
        
        return features


class UserBehaviorAnalyzer:
    """Analyze user behavior patterns"""
    
    def __init__(self):
        self.user_profiles: Dict[str, Dict[str, Any]] = {}
        self.isolation_forest = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100
        )
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def build_user_profile(self, user_id: str, events: List[Dict[str, Any]]):
        """Build behavioral profile for user"""
        extractor = FeatureExtractor()
        features = extractor.extract_user_behavior_features(events)
        
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                'baseline_features': features,
                'event_count': len(events),
                'last_updated': datetime.utcnow(),
                'anomaly_history': []
            }
        else:
            # Update existing profile with exponential moving average
            profile = self.user_profiles[user_id]
            alpha = 0.3  # Learning rate
            
            for feature, value in features.items():
                if feature in profile['baseline_features']:
                    profile['baseline_features'][feature] = (
                        alpha * value + (1 - alpha) * profile['baseline_features'][feature]
                    )
                else:
                    profile['baseline_features'][feature] = value
            
            profile['event_count'] += len(events)
            profile['last_updated'] = datetime.utcnow()
    
    def detect_user_anomalies(self, user_id: str, current_events: List[Dict[str, Any]]) -> List[AnomalyEvent]:
        """Detect anomalies in user behavior"""
        if user_id not in self.user_profiles:
            return []  # No baseline yet
        
        profile = self.user_profiles[user_id]
        baseline = profile['baseline_features']
        
        extractor = FeatureExtractor()
        current_features = extractor.extract_user_behavior_features(current_events)
        
        anomalies = []
        
        # Compare current features with baseline
        for feature, current_value in current_features.items():
            if feature in baseline:
                baseline_value = baseline[feature]
                
                # Calculate deviation
                if baseline_value > 0:
                    deviation = abs(current_value - baseline_value) / baseline_value
                else:
                    deviation = abs(current_value)
                
                # Threshold-based anomaly detection
                if deviation > 2.0:  # 200% deviation
                    severity = AnomalySeverity.HIGH if deviation > 5.0 else AnomalySeverity.MEDIUM
                    
                    anomaly = AnomalyEvent(
                        id=f"user_behavior_{user_id}_{datetime.utcnow().timestamp()}",
                        anomaly_type=AnomalyType.USER_BEHAVIOR,
                        severity=severity,
                        timestamp=datetime.utcnow(),
                        description=f"Unusual {feature} pattern detected for user {user_id}",
                        features=current_features,
                        anomaly_score=deviation,
                        threshold=2.0,
                        affected_entity=user_id,
                        context={
                            'feature': feature,
                            'current_value': current_value,
                            'baseline_value': baseline_value,
                            'deviation': deviation
                        }
                    )
                    
                    anomalies.append(anomaly)
        
        return anomalies


class TimeSeriesAnomalyDetector:
    """Time series based anomaly detection"""
    
    def __init__(self, window_size: int = 60):
        self.window_size = window_size
        self.time_series_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
    
    def add_data_point(self, metric_name: str, value: float, timestamp: datetime):
        """Add data point to time series"""
        self.time_series_data[metric_name].append((timestamp, value))
    
    def detect_anomalies(self, metric_name: str) -> List[AnomalyEvent]:
        """Detect anomalies in time series data"""
        if metric_name not in self.time_series_data:
            return []
        
        data = list(self.time_series_data[metric_name])
        if len(data) < self.window_size:
            return []
        
        # Extract values and calculate rolling statistics
        values = [point[1] for point in data]
        timestamps = [point[0] for point in data]
        
        # Calculate rolling mean and standard deviation
        window_values = values[-self.window_size:]
        mean_value = np.mean(window_values)
        std_value = np.std(window_values)
        
        anomalies = []
        
        # Check recent values for anomalies
        for i in range(max(0, len(values) - 10), len(values)):
            value = values[i]
            timestamp = timestamps[i]
            
            # Z-score based anomaly detection
            if std_value > 0:
                z_score = abs(value - mean_value) / std_value
                
                if z_score > 3.0:  # 3 sigma rule
                    severity = AnomalySeverity.HIGH if z_score > 5.0 else AnomalySeverity.MEDIUM
                    
                    anomaly = AnomalyEvent(
                        id=f"timeseries_{metric_name}_{timestamp.timestamp()}",
                        anomaly_type=AnomalyType.TIME_BASED,
                        severity=severity,
                        timestamp=timestamp,
                        description=f"Unusual value detected in {metric_name}",
                        features={'value': value, 'z_score': z_score},
                        anomaly_score=z_score,
                        threshold=3.0,
                        affected_entity=metric_name,
                        context={
                            'mean': mean_value,
                            'std': std_value,
                            'window_size': self.window_size
                        }
                    )
                    
                    anomalies.append(anomaly)
        
        return anomalies


class GeographicAnomalyDetector:
    """Geographic anomaly detection"""
    
    def __init__(self):
        self.user_locations: Dict[str, List[Tuple[float, float, datetime]]] = defaultdict(list)
    
    def add_user_location(self, user_id: str, latitude: float, longitude: float, timestamp: datetime):
        """Add user location data"""
        self.user_locations[user_id].append((latitude, longitude, timestamp))
        
        # Keep only recent locations (last 30 days)
        cutoff = timestamp - timedelta(days=30)
        self.user_locations[user_id] = [
            loc for loc in self.user_locations[user_id] if loc[2] > cutoff
        ]
    
    def detect_geographic_anomalies(self, user_id: str) -> List[AnomalyEvent]:
        """Detect geographic anomalies"""
        if user_id not in self.user_locations or len(self.user_locations[user_id]) < 2:
            return []
        
        locations = self.user_locations[user_id]
        recent_location = locations[-1]
        previous_locations = locations[:-1]
        
        # Calculate distances from recent location to previous locations
        distances = [
            self._haversine_distance(
                recent_location[0], recent_location[1],
                prev_loc[0], prev_loc[1]
            )
            for prev_loc in previous_locations
        ]
        
        # Calculate typical distance (median of previous distances)
        if len(distances) > 0:
            typical_distance = np.median(distances)
            min_distance = min(distances)
            
            # Check if current location is anomalous
            if min_distance > 1000 and min_distance > typical_distance * 3:  # 1000km and 3x typical
                severity = AnomalySeverity.HIGH if min_distance > 5000 else AnomalySeverity.MEDIUM
                
                anomaly = AnomalyEvent(
                    id=f"geographic_{user_id}_{recent_location[2].timestamp()}",
                    anomaly_type=AnomalyType.GEOGRAPHIC,
                    severity=severity,
                    timestamp=recent_location[2],
                    description=f"Unusual geographic location for user {user_id}",
                    features={
                        'latitude': recent_location[0],
                        'longitude': recent_location[1],
                        'distance_from_typical': min_distance
                    },
                    anomaly_score=min_distance / max(typical_distance, 1),
                    threshold=3.0,
                    affected_entity=user_id,
                    context={
                        'typical_distance': typical_distance,
                        'min_distance_to_previous': min_distance,
                        'location_count': len(locations)
                    }
                )
                
                return [anomaly]
        
        return []
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate haversine distance between two points in kilometers"""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        delta_lat = np.radians(lat2 - lat1)
        delta_lon = np.radians(lon2 - lon1)
        
        a = (np.sin(delta_lat / 2) ** 2 + 
             np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(delta_lon / 2) ** 2)
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        
        return R * c


class AnomalyDetectionSystem:
    """Main anomaly detection system"""
    
    def __init__(self):
        self.user_behavior_analyzer = UserBehaviorAnalyzer()
        self.timeseries_detector = TimeSeriesAnomalyDetector()
        self.geographic_detector = GeographicAnomalyDetector()
        self.feature_extractor = FeatureExtractor()
        self.anomaly_events: List[AnomalyEvent] = []
        self.model_cache: Dict[str, Any] = {}
    
    def train_models(self, training_data: Dict[str, List[Dict[str, Any]]]):
        """Train anomaly detection models"""
        logger.info("Training anomaly detection models...")
        
        # Train user behavior models
        if 'user_events' in training_data:
            user_events_by_user = defaultdict(list)
            for event in training_data['user_events']:
                user_events_by_user[event['user_id']].append(event)
            
            for user_id, events in user_events_by_user.items():
                self.user_behavior_analyzer.build_user_profile(user_id, events)
        
        # Train time series models
        if 'metrics' in training_data:
            for metric_data in training_data['metrics']:
                self.timeseries_detector.add_data_point(
                    metric_data['name'],
                    metric_data['value'],
                    datetime.fromisoformat(metric_data['timestamp'])
                )
        
        logger.info("Anomaly detection models trained successfully")
    
    def detect_anomalies(self, 
                        user_events: List[Dict[str, Any]] = None,
                        api_events: List[Dict[str, Any]] = None,
                        network_events: List[Dict[str, Any]] = None,
                        user_location: Tuple[str, float, float] = None) -> List[AnomalyEvent]:
        """Detect anomalies across all systems"""
        all_anomalies = []
        
        # User behavior anomalies
        if user_events:
            user_events_by_user = defaultdict(list)
            for event in user_events:
                user_events_by_user[event['user_id']].append(event)
            
            for user_id, events in user_events_by_user.items():
                anomalies = self.user_behavior_analyzer.detect_user_anomalies(user_id, events)
                all_anomalies.extend(anomalies)
        
        # API usage anomalies
        if api_events:
            features = self.feature_extractor.extract_api_usage_features(api_events)
            api_anomalies = self._detect_api_anomalies(features)
            all_anomalies.extend(api_anomalies)
        
        # Network anomalies
        if network_events:
            features = self.feature_extractor.extract_network_features(network_events)
            network_anomalies = self._detect_network_anomalies(features)
            all_anomalies.extend(network_anomalies)
        
        # Geographic anomalies
        if user_location:
            user_id, lat, lon = user_location
            self.geographic_detector.add_user_location(user_id, lat, lon, datetime.utcnow())
            geo_anomalies = self.geographic_detector.detect_geographic_anomalies(user_id)
            all_anomalies.extend(geo_anomalies)
        
        # Store detected anomalies
        self.anomaly_events.extend(all_anomalies)
        
        return all_anomalies
    
    def _detect_api_anomalies(self, features: Dict[str, float]) -> List[AnomalyEvent]:
        """Detect API usage anomalies"""
        anomalies = []
        
        # Simple threshold-based detection
        thresholds = {
            'requests_per_minute': 1000,
            'avg_response_time': 5.0,
            'error_rate': 0.1,
            'rate_limit_hits': 10
        }
        
        for feature, threshold in thresholds.items():
            if feature in features and features[feature] > threshold:
                severity = AnomalySeverity.HIGH if features[feature] > threshold * 2 else AnomalySeverity.MEDIUM
                
                anomaly = AnomalyEvent(
                    id=f"api_{feature}_{datetime.utcnow().timestamp()}",
                    anomaly_type=AnomalyType.API_USAGE,
                    severity=severity,
                    timestamp=datetime.utcnow(),
                    description=f"Unusual API {feature} detected",
                    features=features,
                    anomaly_score=features[feature] / threshold,
                    threshold=threshold,
                    affected_entity="api",
                    context={'feature': feature, 'value': features[feature]}
                )
                
                anomalies.append(anomaly)
        
        return anomalies
    
    def _detect_network_anomalies(self, features: Dict[str, float]) -> List[AnomalyEvent]:
        """Detect network traffic anomalies"""
        anomalies = []
        
        # Simple threshold-based detection
        thresholds = {
            'total_connections': 10000,
            'total_bytes_sent': 1e9,  # 1GB
            'total_bytes_received': 1e9,  # 1GB
            'unique_source_ips': 1000
        }
        
        for feature, threshold in thresholds.items():
            if feature in features and features[feature] > threshold:
                severity = AnomalySeverity.HIGH if features[feature] > threshold * 2 else AnomalySeverity.MEDIUM
                
                anomaly = AnomalyEvent(
                    id=f"network_{feature}_{datetime.utcnow().timestamp()}",
                    anomaly_type=AnomalyType.NETWORK_TRAFFIC,
                    severity=severity,
                    timestamp=datetime.utcnow(),
                    description=f"Unusual network {feature} detected",
                    features=features,
                    anomaly_score=features[feature] / threshold,
                    threshold=threshold,
                    affected_entity="network",
                    context={'feature': feature, 'value': features[feature]}
                )
                
                anomalies.append(anomaly)
        
        return anomalies
    
    def get_anomaly_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get anomaly summary for specified time period"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_anomalies = [a for a in self.anomaly_events if a.timestamp > cutoff]
        
        summary = {
            'total_anomalies': len(recent_anomalies),
            'by_type': defaultdict(int),
            'by_severity': defaultdict(int),
            'affected_entities': set(),
            'average_anomaly_score': 0
        }
        
        if recent_anomalies:
            for anomaly in recent_anomalies:
                summary['by_type'][anomaly.anomaly_type.value] += 1
                summary['by_severity'][anomaly.severity.value] += 1
                summary['affected_entities'].add(anomaly.affected_entity)
            
            summary['average_anomaly_score'] = np.mean([a.anomaly_score for a in recent_anomalies])
            summary['affected_entities'] = list(summary['affected_entities'])
            summary['by_type'] = dict(summary['by_type'])
            summary['by_severity'] = dict(summary['by_severity'])
        
        return summary
    
    def save_models(self, file_path: str):
        """Save trained models to file"""
        model_data = {
            'user_profiles': self.user_behavior_analyzer.user_profiles,
            'timeseries_data': dict(self.timeseries_detector.time_series_data),
            'user_locations': dict(self.geographic_detector.user_locations),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        with open(file_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Models saved to {file_path}")
    
    def load_models(self, file_path: str):
        """Load trained models from file"""
        try:
            with open(file_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self.user_behavior_analyzer.user_profiles = model_data.get('user_profiles', {})
            
            # Restore time series data
            for metric, data in model_data.get('timeseries_data', {}).items():
                self.timeseries_detector.time_series_data[metric] = deque(data, maxlen=1000)
            
            # Restore user locations
            for user_id, locations in model_data.get('user_locations', {}).items():
                self.geographic_detector.user_locations[user_id] = locations
            
            logger.info(f"Models loaded from {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to load models from {file_path}: {e}")