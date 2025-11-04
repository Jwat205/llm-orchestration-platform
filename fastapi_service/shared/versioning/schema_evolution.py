"""
Schema Evolution Management
Manages API schema changes, validation, and evolution between versions
"""

import json
import copy
from typing import Dict, Any, List, Optional, Set, Union, Type
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict, field
import logging
from packaging import version
import jsonschema
from jsonschema import validate, ValidationError
import re

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of schema changes"""
    FIELD_ADDED = "field_added"
    FIELD_REMOVED = "field_removed"
    FIELD_RENAMED = "field_renamed"
    FIELD_TYPE_CHANGED = "field_type_changed"
    FIELD_REQUIRED_CHANGED = "field_required_changed"
    ENUM_VALUE_ADDED = "enum_value_added"
    ENUM_VALUE_REMOVED = "enum_value_removed"
    OBJECT_STRUCTURE_CHANGED = "object_structure_changed"
    VALIDATION_RULE_CHANGED = "validation_rule_changed"
    DEFAULT_VALUE_CHANGED = "default_value_changed"


class CompatibilityImpact(Enum):
    """Impact levels for schema changes"""
    NONE = "none"
    BACKWARD_COMPATIBLE = "backward_compatible"
    FORWARD_COMPATIBLE = "forward_compatible"
    BREAKING = "breaking"


@dataclass
class SchemaChange:
    """Represents a change in schema between versions"""
    change_id: str
    change_type: ChangeType
    path: str  # JSON path to the changed element
    old_value: Any
    new_value: Any
    compatibility_impact: CompatibilityImpact
    description: str
    migration_notes: str
    version_introduced: str
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['change_type'] = self.change_type.value
        data['compatibility_impact'] = self.compatibility_impact.value
        return data


@dataclass
class SchemaVersion:
    """Represents a version of an API schema"""
    version: str
    schema_id: str
    schema_data: Dict[str, Any]
    created_at: datetime
    status: str  # "draft", "active", "deprecated", "retired"
    changes_from_previous: List[SchemaChange] = field(default_factory=list)
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['changes_from_previous'] = [change.to_dict() for change in self.changes_from_previous]
        return data


class SchemaComparator:
    """Compares schemas and identifies changes"""
    
    def __init__(self):
        self.compatibility_rules = {
            ChangeType.FIELD_ADDED: self._assess_field_addition,
            ChangeType.FIELD_REMOVED: self._assess_field_removal,
            ChangeType.FIELD_RENAMED: self._assess_field_rename,
            ChangeType.FIELD_TYPE_CHANGED: self._assess_type_change,
            ChangeType.FIELD_REQUIRED_CHANGED: self._assess_required_change,
            ChangeType.ENUM_VALUE_ADDED: self._assess_enum_addition,
            ChangeType.ENUM_VALUE_REMOVED: self._assess_enum_removal,
            ChangeType.VALIDATION_RULE_CHANGED: self._assess_validation_change,
            ChangeType.DEFAULT_VALUE_CHANGED: self._assess_default_change
        }
    
    def compare_schemas(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any],
                       old_version: str, new_version: str) -> List[SchemaChange]:
        """Compare two schemas and identify changes"""
        changes = []
        
        # Compare properties
        changes.extend(self._compare_properties(old_schema, new_schema, "", old_version))
        
        # Compare required fields
        changes.extend(self._compare_required_fields(old_schema, new_schema, old_version))
        
        # Compare enum values
        changes.extend(self._compare_enum_values(old_schema, new_schema, "", old_version))
        
        # Compare validation rules
        changes.extend(self._compare_validation_rules(old_schema, new_schema, old_version))
        
        return changes
    
    def _compare_properties(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any],
                          path: str, version: str) -> List[SchemaChange]:
        """Compare properties section of schemas"""
        changes = []
        
        old_props = old_schema.get('properties', {})
        new_props = new_schema.get('properties', {})
        
        # Find added properties
        for prop_name in new_props:
            if prop_name not in old_props:
                change_path = f"{path}.properties.{prop_name}" if path else f"properties.{prop_name}"
                changes.append(self._create_change(
                    ChangeType.FIELD_ADDED,
                    change_path,
                    None,
                    new_props[prop_name],
                    version,
                    f"Added property '{prop_name}'"
                ))
        
        # Find removed properties
        for prop_name in old_props:
            if prop_name not in new_props:
                change_path = f"{path}.properties.{prop_name}" if path else f"properties.{prop_name}"
                changes.append(self._create_change(
                    ChangeType.FIELD_REMOVED,
                    change_path,
                    old_props[prop_name],
                    None,
                    version,
                    f"Removed property '{prop_name}'"
                ))
        
        # Find modified properties
        for prop_name in old_props:
            if prop_name in new_props:
                old_prop = old_props[prop_name]
                new_prop = new_props[prop_name]
                
                change_path = f"{path}.properties.{prop_name}" if path else f"properties.{prop_name}"
                
                # Check type changes
                old_type = old_prop.get('type')
                new_type = new_prop.get('type')
                if old_type != new_type:
                    changes.append(self._create_change(
                        ChangeType.FIELD_TYPE_CHANGED,
                        f"{change_path}.type",
                        old_type,
                        new_type,
                        version,
                        f"Changed type of '{prop_name}' from {old_type} to {new_type}"
                    ))
                
                # Recursively compare nested objects
                if isinstance(old_prop, dict) and isinstance(new_prop, dict):
                    if 'properties' in old_prop or 'properties' in new_prop:
                        changes.extend(self._compare_properties(
                            old_prop, new_prop, change_path, version
                        ))
        
        return changes
    
    def _compare_required_fields(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any],
                               version: str) -> List[SchemaChange]:
        """Compare required fields"""
        changes = []
        
        old_required = set(old_schema.get('required', []))
        new_required = set(new_schema.get('required', []))
        
        # Fields that became required
        newly_required = new_required - old_required
        for field in newly_required:
            changes.append(self._create_change(
                ChangeType.FIELD_REQUIRED_CHANGED,
                f"required.{field}",
                False,
                True,
                version,
                f"Field '{field}' is now required"
            ))
        
        # Fields that are no longer required
        no_longer_required = old_required - new_required
        for field in no_longer_required:
            changes.append(self._create_change(
                ChangeType.FIELD_REQUIRED_CHANGED,
                f"required.{field}",
                True,
                False,
                version,
                f"Field '{field}' is no longer required"
            ))
        
        return changes
    
    def _compare_enum_values(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any],
                           path: str, version: str) -> List[SchemaChange]:
        """Compare enum values"""
        changes = []
        
        def find_enums_recursive(schema: Dict[str, Any], current_path: str) -> List[Tuple[str, List]]:
            enums = []
            
            if 'enum' in schema:
                enums.append((current_path, schema['enum']))
            
            if 'properties' in schema:
                for prop_name, prop_schema in schema['properties'].items():
                    prop_path = f"{current_path}.properties.{prop_name}" if current_path else f"properties.{prop_name}"
                    enums.extend(find_enums_recursive(prop_schema, prop_path))
            
            return enums
        
        old_enums = dict(find_enums_recursive(old_schema, path))
        new_enums = dict(find_enums_recursive(new_schema, path))
        
        # Compare enum values
        for enum_path in set(old_enums.keys()) | set(new_enums.keys()):
            old_values = set(old_enums.get(enum_path, []))
            new_values = set(new_enums.get(enum_path, []))
            
            # Added enum values
            added_values = new_values - old_values
            for value in added_values:
                changes.append(self._create_change(
                    ChangeType.ENUM_VALUE_ADDED,
                    f"{enum_path}.enum",
                    None,
                    value,
                    version,
                    f"Added enum value '{value}' to {enum_path}"
                ))
            
            # Removed enum values
            removed_values = old_values - new_values
            for value in removed_values:
                changes.append(self._create_change(
                    ChangeType.ENUM_VALUE_REMOVED,
                    f"{enum_path}.enum",
                    value,
                    None,
                    version,
                    f"Removed enum value '{value}' from {enum_path}"
                ))
        
        return changes
    
    def _compare_validation_rules(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any],
                                version: str) -> List[SchemaChange]:
        """Compare validation rules like min/max length, pattern, etc."""
        changes = []
        
        validation_fields = ['minLength', 'maxLength', 'minimum', 'maximum', 'pattern', 'format']
        
        for field in validation_fields:
            old_value = old_schema.get(field)
            new_value = new_schema.get(field)
            
            if old_value != new_value:
                changes.append(self._create_change(
                    ChangeType.VALIDATION_RULE_CHANGED,
                    field,
                    old_value,
                    new_value,
                    version,
                    f"Validation rule '{field}' changed from {old_value} to {new_value}"
                ))
        
        return changes
    
    def _create_change(self, change_type: ChangeType, path: str, old_value: Any,
                      new_value: Any, version: str, description: str) -> SchemaChange:
        """Create a schema change object with compatibility assessment"""
        
        # Assess compatibility impact
        compatibility_impact = self.compatibility_rules.get(
            change_type, 
            lambda *args: CompatibilityImpact.BREAKING
        )(old_value, new_value, path)
        
        # Generate migration notes
        migration_notes = self._generate_migration_notes(change_type, path, old_value, new_value)
        
        change_id = f"{change_type.value}_{path}_{version}".replace(".", "_")
        
        return SchemaChange(
            change_id=change_id,
            change_type=change_type,
            path=path,
            old_value=old_value,
            new_value=new_value,
            compatibility_impact=compatibility_impact,
            description=description,
            migration_notes=migration_notes,
            version_introduced=version
        )
    
    def _assess_field_addition(self, old_value: Any, new_value: Any, path: str) -> CompatibilityImpact:
        """Assess impact of field addition"""
        return CompatibilityImpact.BACKWARD_COMPATIBLE
    
    def _assess_field_removal(self, old_value: Any, new_value: Any, path: str) -> CompatibilityImpact:
        """Assess impact of field removal"""
        return CompatibilityImpact.BREAKING
    
    def _assess_field_rename(self, old_value: Any, new_value: Any, path: str) -> CompatibilityImpact:
        """Assess impact of field rename"""
        return CompatibilityImpact.BREAKING
    
    def _assess_type_change(self, old_value: Any, new_value: Any, path: str) -> CompatibilityImpact:
        """Assess impact of type change"""
        # Some type changes might be compatible (e.g., integer to number)
        compatible_changes = [
            ('integer', 'number'),
            ('string', 'object'),  # if the string was actually JSON
        ]
        
        change_pair = (old_value, new_value)
        if change_pair in compatible_changes:
            return CompatibilityImpact.BACKWARD_COMPATIBLE
        
        return CompatibilityImpact.BREAKING
    
    def _assess_required_change(self, old_value: Any, new_value: Any, path: str) -> CompatibilityImpact:
        """Assess impact of required field change"""
        if not old_value and new_value:  # Became required
            return CompatibilityImpact.BREAKING
        elif old_value and not new_value:  # No longer required
            return CompatibilityImpact.BACKWARD_COMPATIBLE
        
        return CompatibilityImpact.NONE
    
    def _assess_enum_addition(self, old_value: Any, new_value: Any, path: str) -> CompatibilityImpact:
        """Assess impact of enum value addition"""
        return CompatibilityImpact.FORWARD_COMPATIBLE
    
    def _assess_enum_removal(self, old_value: Any, new_value: Any, path: str) -> CompatibilityImpact:
        """Assess impact of enum value removal"""
        return CompatibilityImpact.BREAKING
    
    def _assess_validation_change(self, old_value: Any, new_value: Any, path: str) -> CompatibilityImpact:
        """Assess impact of validation rule change"""
        if path in ['minLength', 'minimum']:
            if new_value is None or (old_value is not None and new_value < old_value):
                return CompatibilityImpact.BACKWARD_COMPATIBLE
            else:
                return CompatibilityImpact.BREAKING
        elif path in ['maxLength', 'maximum']:
            if new_value is None or (old_value is not None and new_value > old_value):
                return CompatibilityImpact.BACKWARD_COMPATIBLE
            else:
                return CompatibilityImpact.BREAKING
        
        return CompatibilityImpact.BREAKING
    
    def _assess_default_change(self, old_value: Any, new_value: Any, path: str) -> CompatibilityImpact:
        """Assess impact of default value change"""
        return CompatibilityImpact.BACKWARD_COMPATIBLE
    
    def _generate_migration_notes(self, change_type: ChangeType, path: str,
                                old_value: Any, new_value: Any) -> str:
        """Generate migration notes for a change"""
        
        if change_type == ChangeType.FIELD_ADDED:
            return f"New field '{path}' added. Update your code to handle this field if needed."
        
        elif change_type == ChangeType.FIELD_REMOVED:
            return f"Field '{path}' removed. Remove references to this field in your code."
        
        elif change_type == ChangeType.FIELD_TYPE_CHANGED:
            return f"Field '{path}' type changed from {old_value} to {new_value}. Update your data handling code."
        
        elif change_type == ChangeType.FIELD_REQUIRED_CHANGED:
            if new_value:
                return f"Field '{path}' is now required. Ensure your requests include this field."
            else:
                return f"Field '{path}' is no longer required. You can optionally remove it from requests."
        
        elif change_type == ChangeType.ENUM_VALUE_ADDED:
            return f"New enum value '{new_value}' added to '{path}'. Update your code to handle this value."
        
        elif change_type == ChangeType.ENUM_VALUE_REMOVED:
            return f"Enum value '{old_value}' removed from '{path}'. Update your code to avoid using this value."
        
        elif change_type == ChangeType.VALIDATION_RULE_CHANGED:
            return f"Validation rule for '{path}' changed from {old_value} to {new_value}. Update your data validation."
        
        return "Review this change and update your code accordingly."


class SchemaValidator:
    """Validates data against versioned schemas"""
    
    def __init__(self):
        self.schemas: Dict[str, Dict[str, Any]] = {}
    
    def register_schema(self, schema_id: str, version: str, schema_data: Dict[str, Any]):
        """Register a schema version"""
        key = f"{schema_id}:{version}"
        self.schemas[key] = schema_data
        logger.info(f"Registered schema {schema_id} version {version}")
    
    def validate_data(self, data: Any, schema_id: str, version: str) -> Tuple[bool, List[str]]:
        """Validate data against a specific schema version"""
        key = f"{schema_id}:{version}"
        
        if key not in self.schemas:
            return False, [f"Schema {schema_id} version {version} not found"]
        
        schema = self.schemas[key]
        errors = []
        
        try:
            validate(instance=data, schema=schema)
            return True, []
        except ValidationError as e:
            errors.append(str(e))
            return False, errors
        except Exception as e:
            errors.append(f"Validation error: {e}")
            return False, errors
    
    def get_validation_errors(self, data: Any, schema_id: str, version: str) -> List[Dict[str, Any]]:
        """Get detailed validation errors"""
        key = f"{schema_id}:{version}"
        
        if key not in self.schemas:
            return [{"error": f"Schema {schema_id} version {version} not found"}]
        
        schema = self.schemas[key]
        errors = []
        
        try:
            validate(instance=data, schema=schema)
        except ValidationError as e:
            for error in jsonschema.ErrorTree(e).errors:
                errors.append({
                    "path": ".".join(str(p) for p in error.absolute_path),
                    "message": error.message,
                    "failed_value": error.instance,
                    "schema_path": ".".join(str(p) for p in error.schema_path)
                })
        
        return errors


class SchemaEvolutionManager:
    """Manages schema evolution across versions"""
    
    def __init__(self):
        self.schema_versions: Dict[str, List[SchemaVersion]] = {}
        self.comparator = SchemaComparator()
        self.validator = SchemaValidator()
    
    def register_schema_version(self, schema_version: SchemaVersion):
        """Register a new schema version"""
        schema_id = schema_version.schema_id
        
        if schema_id not in self.schema_versions:
            self.schema_versions[schema_id] = []
        
        # Find previous version for comparison
        previous_version = self._get_previous_version(schema_id, schema_version.version)
        
        if previous_version:
            # Compare with previous version
            changes = self.comparator.compare_schemas(
                previous_version.schema_data,
                schema_version.schema_data,
                previous_version.version,
                schema_version.version
            )
            schema_version.changes_from_previous = changes
        
        self.schema_versions[schema_id].append(schema_version)
        
        # Sort by version
        self.schema_versions[schema_id].sort(
            key=lambda sv: version.parse(sv.version)
        )
        
        # Register with validator
        self.validator.register_schema(
            schema_id, 
            schema_version.version, 
            schema_version.schema_data
        )
        
        logger.info(f"Registered schema version {schema_id}:{schema_version.version}")
    
    def get_schema_version(self, schema_id: str, version_str: str) -> Optional[SchemaVersion]:
        """Get a specific schema version"""
        if schema_id not in self.schema_versions:
            return None
        
        for schema_version in self.schema_versions[schema_id]:
            if schema_version.version == version_str:
                return schema_version
        
        return None
    
    def get_latest_schema(self, schema_id: str) -> Optional[SchemaVersion]:
        """Get the latest version of a schema"""
        if schema_id not in self.schema_versions:
            return None
        
        versions = self.schema_versions[schema_id]
        if not versions:
            return None
        
        return max(versions, key=lambda sv: version.parse(sv.version))
    
    def get_schema_evolution_history(self, schema_id: str) -> List[Dict[str, Any]]:
        """Get the evolution history of a schema"""
        if schema_id not in self.schema_versions:
            return []
        
        history = []
        for schema_version in self.schema_versions[schema_id]:
            history.append({
                'version': schema_version.version,
                'created_at': schema_version.created_at.isoformat(),
                'status': schema_version.status,
                'changes_count': len(schema_version.changes_from_previous),
                'breaking_changes': len([
                    c for c in schema_version.changes_from_previous 
                    if c.compatibility_impact == CompatibilityImpact.BREAKING
                ]),
                'changes': [change.to_dict() for change in schema_version.changes_from_previous]
            })
        
        return history
    
    def analyze_compatibility(self, schema_id: str, from_version: str, 
                            to_version: str) -> Dict[str, Any]:
        """Analyze compatibility between two schema versions"""
        from_schema = self.get_schema_version(schema_id, from_version)
        to_schema = self.get_schema_version(schema_id, to_version)
        
        if not from_schema or not to_schema:
            return {
                'compatible': False,
                'error': 'One or both schema versions not found'
            }
        
        # Get all changes between versions
        all_changes = []
        
        # Collect changes from intermediate versions
        versions = [sv for sv in self.schema_versions[schema_id] 
                   if version.parse(from_version) < version.parse(sv.version) <= version.parse(to_version)]
        
        for schema_version in versions:
            all_changes.extend(schema_version.changes_from_previous)
        
        # Analyze compatibility
        breaking_changes = [c for c in all_changes if c.compatibility_impact == CompatibilityImpact.BREAKING]
        backward_compatible = [c for c in all_changes if c.compatibility_impact == CompatibilityImpact.BACKWARD_COMPATIBLE]
        forward_compatible = [c for c in all_changes if c.compatibility_impact == CompatibilityImpact.FORWARD_COMPATIBLE]
        
        overall_compatibility = "fully_compatible"
        if breaking_changes:
            overall_compatibility = "breaking"
        elif forward_compatible and not backward_compatible:
            overall_compatibility = "forward_compatible_only"
        elif backward_compatible:
            overall_compatibility = "backward_compatible"
        
        return {
            'compatible': len(breaking_changes) == 0,
            'overall_compatibility': overall_compatibility,
            'total_changes': len(all_changes),
            'breaking_changes': len(breaking_changes),
            'backward_compatible_changes': len(backward_compatible),
            'forward_compatible_changes': len(forward_compatible),
            'changes': [change.to_dict() for change in all_changes],
            'migration_required': len(breaking_changes) > 0,
            'recommendations': self._generate_compatibility_recommendations(all_changes)
        }
    
    def validate_against_version(self, data: Any, schema_id: str, 
                               version_str: str) -> Tuple[bool, List[str]]:
        """Validate data against a specific schema version"""
        return self.validator.validate_data(data, schema_id, version_str)
    
    def find_compatible_versions(self, schema_id: str, data: Any) -> List[str]:
        """Find all schema versions that validate the given data"""
        if schema_id not in self.schema_versions:
            return []
        
        compatible_versions = []
        
        for schema_version in self.schema_versions[schema_id]:
            is_valid, _ = self.validator.validate_data(data, schema_id, schema_version.version)
            if is_valid:
                compatible_versions.append(schema_version.version)
        
        return compatible_versions
    
    def get_schema_diff(self, schema_id: str, from_version: str, to_version: str) -> Dict[str, Any]:
        """Get detailed diff between two schema versions"""
        from_schema = self.get_schema_version(schema_id, from_version)
        to_schema = self.get_schema_version(schema_id, to_version)
        
        if not from_schema or not to_schema:
            return {'error': 'One or both schema versions not found'}
        
        changes = self.comparator.compare_schemas(
            from_schema.schema_data,
            to_schema.schema_data,
            from_version,
            to_version
        )
        
        return {
            'from_version': from_version,
            'to_version': to_version,
            'changes': [change.to_dict() for change in changes],
            'summary': {
                'total_changes': len(changes),
                'breaking_changes': len([c for c in changes if c.compatibility_impact == CompatibilityImpact.BREAKING]),
                'change_types': list(set(c.change_type.value for c in changes))
            }
        }
    
    def _get_previous_version(self, schema_id: str, current_version: str) -> Optional[SchemaVersion]:
        """Get the previous version of a schema"""
        if schema_id not in self.schema_versions:
            return None
        
        current_ver = version.parse(current_version)
        previous_versions = [
            sv for sv in self.schema_versions[schema_id]
            if version.parse(sv.version) < current_ver
        ]
        
        if not previous_versions:
            return None
        
        return max(previous_versions, key=lambda sv: version.parse(sv.version))
    
    def _generate_compatibility_recommendations(self, changes: List[SchemaChange]) -> List[str]:
        """Generate recommendations based on schema changes"""
        recommendations = []
        
        breaking_changes = [c for c in changes if c.compatibility_impact == CompatibilityImpact.BREAKING]
        
        if breaking_changes:
            recommendations.append("Breaking changes detected. Plan for a major version upgrade.")
            recommendations.append("Test all client integrations thoroughly.")
            recommendations.append("Consider implementing backward compatibility adapters.")
        
        field_removals = [c for c in changes if c.change_type == ChangeType.FIELD_REMOVED]
        if field_removals:
            recommendations.append("Fields have been removed. Update client code to handle missing fields gracefully.")
        
        new_required_fields = [
            c for c in changes 
            if c.change_type == ChangeType.FIELD_REQUIRED_CHANGED and c.new_value
        ]
        if new_required_fields:
            recommendations.append("New required fields added. Update client code to provide these fields.")
        
        type_changes = [c for c in changes if c.change_type == ChangeType.FIELD_TYPE_CHANGED]
        if type_changes:
            recommendations.append("Field types have changed. Update data serialization/deserialization code.")
        
        return recommendations