"""
Backward Compatibility Handlers
Manages backward compatibility transformations between API versions
"""

import re
import json
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import logging
from packaging import version

logger = logging.getLogger(__name__)


class CompatibilityLevel(Enum):
    """Levels of compatibility"""
    FULL = "full"
    PARTIAL = "partial"
    BREAKING = "breaking"
    NONE = "none"


class TransformationType(Enum):
    """Types of transformations"""
    FIELD_RENAME = "field_rename"
    FIELD_REMOVE = "field_remove"
    FIELD_ADD = "field_add"
    FIELD_TYPE_CHANGE = "field_type_change"
    STRUCTURE_CHANGE = "structure_change"
    FORMAT_CHANGE = "format_change"
    ENUM_CHANGE = "enum_change"


@dataclass
class CompatibilityRule:
    """Defines a compatibility transformation rule"""
    rule_id: str
    from_version: str
    to_version: str
    transformation_type: TransformationType
    source_path: str
    target_path: Optional[str]
    transform_function: Optional[str]
    parameters: Dict[str, Any]
    description: str
    is_reversible: bool
    priority: int = 100


class FieldTransformer:
    """Handles field-level transformations"""
    
    @staticmethod
    def rename_field(data: Dict[str, Any], old_name: str, new_name: str) -> Dict[str, Any]:
        """Rename a field in the data"""
        if old_name in data:
            data[new_name] = data[old_name]
            del data[old_name]
        return data
    
    @staticmethod
    def remove_field(data: Dict[str, Any], field_name: str) -> Dict[str, Any]:
        """Remove a field from the data"""
        if field_name in data:
            del data[field_name]
        return data
    
    @staticmethod
    def add_field(data: Dict[str, Any], field_name: str, default_value: Any) -> Dict[str, Any]:
        """Add a field with default value"""
        if field_name not in data:
            data[field_name] = default_value
        return data
    
    @staticmethod
    def transform_field_type(data: Dict[str, Any], field_name: str, 
                           transformer: Callable[[Any], Any]) -> Dict[str, Any]:
        """Transform field type using a custom function"""
        if field_name in data:
            try:
                data[field_name] = transformer(data[field_name])
            except Exception as e:
                logger.warning(f"Failed to transform field {field_name}: {e}")
        return data
    
    @staticmethod
    def split_field(data: Dict[str, Any], source_field: str, 
                   target_fields: List[str], separator: str = " ") -> Dict[str, Any]:
        """Split a field into multiple fields"""
        if source_field in data and isinstance(data[source_field], str):
            parts = data[source_field].split(separator)
            for i, target_field in enumerate(target_fields):
                if i < len(parts):
                    data[target_field] = parts[i]
                else:
                    data[target_field] = ""
            del data[source_field]
        return data
    
    @staticmethod
    def combine_fields(data: Dict[str, Any], source_fields: List[str], 
                      target_field: str, separator: str = " ") -> Dict[str, Any]:
        """Combine multiple fields into one"""
        values = []
        for field in source_fields:
            if field in data and data[field]:
                values.append(str(data[field]))
                del data[field]
        
        if values:
            data[target_field] = separator.join(values)
        
        return data


class ResponseTransformer:
    """Handles response format transformations"""
    
    @staticmethod
    def wrap_in_envelope(data: Any, envelope_field: str = "data") -> Dict[str, Any]:
        """Wrap response data in an envelope"""
        return {
            envelope_field: data,
            "meta": {
                "timestamp": datetime.utcnow().isoformat(),
                "version": "envelope_format"
            }
        }
    
    @staticmethod
    def unwrap_envelope(data: Dict[str, Any], envelope_field: str = "data") -> Any:
        """Unwrap response data from envelope"""
        if isinstance(data, dict) and envelope_field in data:
            return data[envelope_field]
        return data
    
    @staticmethod
    def paginate_response(data: List[Any], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Add pagination wrapper to list response"""
        total = len(data)
        start = (page - 1) * per_page
        end = start + per_page
        
        return {
            "items": data[start:end],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page
            }
        }
    
    @staticmethod
    def flatten_nested_object(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """Flatten nested object structure"""
        result = {}
        
        for key, value in data.items():
            new_key = f"{prefix}_{key}" if prefix else key
            
            if isinstance(value, dict):
                result.update(ResponseTransformer.flatten_nested_object(value, new_key))
            else:
                result[new_key] = value
        
        return result


class SchemaTransformer:
    """Handles schema-level transformations"""
    
    @staticmethod
    def transform_enum_values(data: Dict[str, Any], field_name: str, 
                            value_mapping: Dict[str, str]) -> Dict[str, Any]:
        """Transform enum values according to mapping"""
        if field_name in data and data[field_name] in value_mapping:
            data[field_name] = value_mapping[data[field_name]]
        return data
    
    @staticmethod
    def transform_datetime_format(data: Dict[str, Any], field_name: str, 
                                from_format: str, to_format: str) -> Dict[str, Any]:
        """Transform datetime format"""
        if field_name in data and isinstance(data[field_name], str):
            try:
                dt = datetime.strptime(data[field_name], from_format)
                data[field_name] = dt.strftime(to_format)
            except ValueError as e:
                logger.warning(f"Failed to transform datetime format for {field_name}: {e}")
        return data
    
    @staticmethod
    def normalize_boolean_values(data: Dict[str, Any], field_name: str) -> Dict[str, Any]:
        """Normalize boolean values (true/false, 1/0, yes/no)"""
        if field_name in data:
            value = str(data[field_name]).lower()
            if value in ['true', '1', 'yes', 'on']:
                data[field_name] = True
            elif value in ['false', '0', 'no', 'off']:
                data[field_name] = False
        return data


class CompatibilityEngine:
    """Main compatibility transformation engine"""
    
    def __init__(self):
        self.rules: Dict[str, List[CompatibilityRule]] = {}
        self.transformers = {
            TransformationType.FIELD_RENAME: self._apply_field_rename,
            TransformationType.FIELD_REMOVE: self._apply_field_remove,
            TransformationType.FIELD_ADD: self._apply_field_add,
            TransformationType.FIELD_TYPE_CHANGE: self._apply_field_type_change,
            TransformationType.STRUCTURE_CHANGE: self._apply_structure_change,
            TransformationType.FORMAT_CHANGE: self._apply_format_change,
            TransformationType.ENUM_CHANGE: self._apply_enum_change
        }
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Setup default compatibility rules"""
        # Example: v1.0 to v1.1 transformations
        self.add_rule(CompatibilityRule(
            rule_id="user_name_split",
            from_version="1.0.0",
            to_version="1.1.0",
            transformation_type=TransformationType.STRUCTURE_CHANGE,
            source_path="name",
            target_path="first_name,last_name",
            transform_function="split_name",
            parameters={"separator": " "},
            description="Split full name into first and last name",
            is_reversible=True
        ))
        
        self.add_rule(CompatibilityRule(
            rule_id="response_envelope",
            from_version="1.0.0",
            to_version="2.0.0",
            transformation_type=TransformationType.FORMAT_CHANGE,
            source_path="*",
            target_path="data",
            transform_function="wrap_envelope",
            parameters={"envelope_field": "data"},
            description="Wrap response in data envelope",
            is_reversible=True
        ))
        
        self.add_rule(CompatibilityRule(
            rule_id="status_enum_update",
            from_version="1.1.0",
            to_version="2.0.0",
            transformation_type=TransformationType.ENUM_CHANGE,
            source_path="status",
            target_path="status",
            transform_function="transform_status_enum",
            parameters={
                "mapping": {
                    "active": "enabled",
                    "inactive": "disabled",
                    "pending": "processing"
                }
            },
            description="Update status enum values",
            is_reversible=True
        ))
    
    def add_rule(self, rule: CompatibilityRule):
        """Add a compatibility rule"""
        version_key = f"{rule.from_version}->{rule.to_version}"
        if version_key not in self.rules:
            self.rules[version_key] = []
        
        self.rules[version_key].append(rule)
        self.rules[version_key].sort(key=lambda r: r.priority)
        
        logger.info(f"Added compatibility rule: {rule.rule_id}")
    
    def get_compatibility_level(self, from_version: str, to_version: str) -> CompatibilityLevel:
        """Determine compatibility level between versions"""
        try:
            from_ver = version.parse(from_version)
            to_ver = version.parse(to_version)
            
            if from_ver.major != to_ver.major:
                return CompatibilityLevel.BREAKING
            elif from_ver.minor != to_ver.minor:
                return CompatibilityLevel.PARTIAL
            else:
                return CompatibilityLevel.FULL
                
        except Exception:
            return CompatibilityLevel.NONE
    
    def transform_request(self, data: Dict[str, Any], from_version: str, 
                         to_version: str) -> Tuple[Dict[str, Any], List[str]]:
        """Transform request data from one version to another"""
        return self._apply_transformations(data, from_version, to_version, "request")
    
    def transform_response(self, data: Any, from_version: str, 
                          to_version: str) -> Tuple[Any, List[str]]:
        """Transform response data from one version to another"""
        return self._apply_transformations(data, from_version, to_version, "response")
    
    def _apply_transformations(self, data: Any, from_version: str, 
                             to_version: str, direction: str) -> Tuple[Any, List[str]]:
        """Apply all relevant transformations"""
        warnings = []
        
        # Find applicable rules
        version_key = f"{from_version}->{to_version}"
        rules = self.rules.get(version_key, [])
        
        if not rules:
            # Try to find intermediate transformations
            rules = self._find_transformation_path(from_version, to_version)
        
        if not rules:
            warnings.append(f"No transformation rules found for {from_version} -> {to_version}")
            return data, warnings
        
        # Apply transformations
        transformed_data = data
        for rule in rules:
            try:
                transformer = self.transformers.get(rule.transformation_type)
                if transformer:
                    transformed_data = transformer(transformed_data, rule)
                else:
                    warnings.append(f"No transformer found for {rule.transformation_type}")
            except Exception as e:
                warnings.append(f"Failed to apply rule {rule.rule_id}: {e}")
                logger.error(f"Transformation error: {e}")
        
        return transformed_data, warnings
    
    def _find_transformation_path(self, from_version: str, to_version: str) -> List[CompatibilityRule]:
        """Find a path of transformations between versions"""
        # Simple implementation - could be enhanced with graph traversal
        all_rules = []
        
        # Collect all rules that could form a path
        for version_key, rules in self.rules.items():
            from_v, to_v = version_key.split('->')
            
            # Check if this rule is part of the path
            try:
                from_ver = version.parse(from_version)
                to_ver = version.parse(to_version)
                rule_from = version.parse(from_v)
                rule_to = version.parse(to_v)
                
                if rule_from >= from_ver and rule_to <= to_ver:
                    all_rules.extend(rules)
            except Exception:
                continue
        
        return sorted(all_rules, key=lambda r: r.priority)
    
    def _apply_field_rename(self, data: Any, rule: CompatibilityRule) -> Any:
        """Apply field rename transformation"""
        if isinstance(data, dict):
            target_path = rule.target_path or rule.parameters.get('new_name', 'unknown')
            return FieldTransformer.rename_field(data, rule.source_path, target_path)
        return data
    
    def _apply_field_remove(self, data: Any, rule: CompatibilityRule) -> Any:
        """Apply field removal transformation"""
        if isinstance(data, dict):
            return FieldTransformer.remove_field(data, rule.source_path)
        return data
    
    def _apply_field_add(self, data: Any, rule: CompatibilityRule) -> Any:
        """Apply field addition transformation"""
        if isinstance(data, dict):
            default_value = rule.parameters.get('default_value')
            target_field = rule.target_path or rule.source_path
            return FieldTransformer.add_field(data, target_field, default_value)
        return data
    
    def _apply_field_type_change(self, data: Any, rule: CompatibilityRule) -> Any:
        """Apply field type change transformation"""
        if isinstance(data, dict):
            transform_func = rule.parameters.get('transform_function')
            if transform_func == 'string_to_int':
                transformer = lambda x: int(x) if isinstance(x, str) and x.isdigit() else x
            elif transform_func == 'int_to_string':
                transformer = lambda x: str(x)
            elif transform_func == 'normalize_boolean':
                transformer = lambda x: bool(x)
            else:
                return data
            
            return FieldTransformer.transform_field_type(data, rule.source_path, transformer)
        return data
    
    def _apply_structure_change(self, data: Any, rule: CompatibilityRule) -> Any:
        """Apply structure change transformation"""
        if isinstance(data, dict):
            if rule.transform_function == 'split_name':
                target_fields = rule.target_path.split(',')
                separator = rule.parameters.get('separator', ' ')
                return FieldTransformer.split_field(data, rule.source_path, target_fields, separator)
            elif rule.transform_function == 'combine_fields':
                source_fields = rule.source_path.split(',')
                separator = rule.parameters.get('separator', ' ')
                return FieldTransformer.combine_fields(data, source_fields, rule.target_path, separator)
        return data
    
    def _apply_format_change(self, data: Any, rule: CompatibilityRule) -> Any:
        """Apply format change transformation"""
        if rule.transform_function == 'wrap_envelope':
            envelope_field = rule.parameters.get('envelope_field', 'data')
            return ResponseTransformer.wrap_in_envelope(data, envelope_field)
        elif rule.transform_function == 'unwrap_envelope':
            envelope_field = rule.parameters.get('envelope_field', 'data')
            return ResponseTransformer.unwrap_envelope(data, envelope_field)
        elif rule.transform_function == 'paginate':
            if isinstance(data, list):
                page = rule.parameters.get('page', 1)
                per_page = rule.parameters.get('per_page', 20)
                return ResponseTransformer.paginate_response(data, page, per_page)
        return data
    
    def _apply_enum_change(self, data: Any, rule: CompatibilityRule) -> Any:
        """Apply enum value change transformation"""
        if isinstance(data, dict) and rule.transform_function == 'transform_status_enum':
            mapping = rule.parameters.get('mapping', {})
            return SchemaTransformer.transform_enum_values(data, rule.source_path, mapping)
        return data
    
    def get_transformation_summary(self, from_version: str, to_version: str) -> Dict[str, Any]:
        """Get summary of transformations between versions"""
        version_key = f"{from_version}->{to_version}"
        rules = self.rules.get(version_key, [])
        
        compatibility_level = self.get_compatibility_level(from_version, to_version)
        
        transformations = []
        for rule in rules:
            transformations.append({
                'rule_id': rule.rule_id,
                'type': rule.transformation_type.value,
                'description': rule.description,
                'reversible': rule.is_reversible,
                'source_path': rule.source_path,
                'target_path': rule.target_path
            })
        
        return {
            'from_version': from_version,
            'to_version': to_version,
            'compatibility_level': compatibility_level.value,
            'transformation_count': len(transformations),
            'transformations': transformations,
            'breaking_changes': [t for t in transformations if not t['reversible']],
            'supports_rollback': all(t['reversible'] for t in transformations)
        }


class CompatibilityManager:
    """High-level compatibility management"""
    
    def __init__(self):
        self.engine = CompatibilityEngine()
        self.transformation_cache = {}
    
    def register_custom_transformer(self, transformation_type: TransformationType, 
                                  transformer_func: Callable):
        """Register a custom transformation function"""
        self.engine.transformers[transformation_type] = transformer_func
    
    def check_compatibility(self, client_version: str, server_version: str) -> Dict[str, Any]:
        """Check compatibility between client and server versions"""
        compatibility_level = self.engine.get_compatibility_level(client_version, server_version)
        
        result = {
            'compatible': compatibility_level != CompatibilityLevel.NONE,
            'level': compatibility_level.value,
            'requires_transformation': compatibility_level in [
                CompatibilityLevel.PARTIAL, 
                CompatibilityLevel.BREAKING
            ],
            'automatic_transformation_available': False,
            'warnings': [],
            'recommendations': []
        }
        
        # Check if transformations are available
        version_key = f"{client_version}->{server_version}"
        if version_key in self.engine.rules:
            result['automatic_transformation_available'] = True
        
        # Add recommendations based on compatibility level
        if compatibility_level == CompatibilityLevel.BREAKING:
            result['recommendations'].append(
                "Major version differences detected. Review breaking changes carefully."
            )
        elif compatibility_level == CompatibilityLevel.PARTIAL:
            result['recommendations'].append(
                "Minor version differences. Some features may not be available."
            )
        
        return result
    
    def transform_data(self, data: Any, from_version: str, to_version: str, 
                      data_type: str = "response") -> Tuple[Any, List[str]]:
        """Transform data between versions with caching"""
        cache_key = f"{from_version}->{to_version}:{data_type}:{hash(str(data))}"
        
        if cache_key in self.transformation_cache:
            return self.transformation_cache[cache_key]
        
        if data_type == "request":
            result = self.engine.transform_request(data, from_version, to_version)
        else:
            result = self.engine.transform_response(data, from_version, to_version)
        
        # Cache the result (limit cache size)
        if len(self.transformation_cache) < 1000:
            self.transformation_cache[cache_key] = result
        
        return result
    
    def get_migration_guide(self, from_version: str, to_version: str) -> Dict[str, Any]:
        """Generate migration guide between versions"""
        transformation_summary = self.engine.get_transformation_summary(from_version, to_version)
        
        breaking_changes = transformation_summary['breaking_changes']
        
        migration_steps = []
        for transformation in transformation_summary['transformations']:
            if transformation['type'] == 'field_rename':
                migration_steps.append(
                    f"Rename field '{transformation['source_path']}' to '{transformation['target_path']}'"
                )
            elif transformation['type'] == 'field_remove':
                migration_steps.append(
                    f"Remove field '{transformation['source_path']}' (no longer used)"
                )
            elif transformation['type'] == 'field_add':
                migration_steps.append(
                    f"Add field '{transformation['target_path']}' with appropriate default value"
                )
        
        return {
            'from_version': from_version,
            'to_version': to_version,
            'migration_required': len(breaking_changes) > 0,
            'automatic_migration_available': transformation_summary['supports_rollback'],
            'breaking_changes': breaking_changes,
            'migration_steps': migration_steps,
            'estimated_effort': 'low' if len(breaking_changes) == 0 else 'medium' if len(breaking_changes) < 5 else 'high',
            'rollback_supported': transformation_summary['supports_rollback']
        }