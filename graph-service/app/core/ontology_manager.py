"""
Ontology Manager for Knowledge Graph.
Manages ontology definitions, validation, and schema evolution.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
import json
from dataclasses import dataclass, asdict
from enum import Enum

class PropertyType(Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    LIST = "list"
    OBJECT = "object"

@dataclass
class OntologyProperty:
    name: str
    property_type: PropertyType
    required: bool = False
    unique: bool = False
    description: str = ""
    constraints: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.constraints is None:
            self.constraints = {}

@dataclass
class OntologyClass:
    name: str
    description: str = ""
    parent_classes: List[str] = None
    properties: List[OntologyProperty] = None
    required_properties: List[str] = None
    constraints: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.parent_classes is None:
            self.parent_classes = []
        if self.properties is None:
            self.properties = []
        if self.required_properties is None:
            self.required_properties = []
        if self.constraints is None:
            self.constraints = {}

@dataclass
class OntologyRelationship:
    name: str
    source_class: str
    target_class: str
    description: str = ""
    properties: List[OntologyProperty] = None
    cardinality: str = "many-to-many"  # "one-to-one", "one-to-many", "many-to-one", "many-to-many"
    inverse_relationship: str = None
    constraints: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.properties is None:
            self.properties = []
        if self.constraints is None:
            self.constraints = {}

class OntologyManager:
    """Manager for ontology definitions and validation."""
    
    def __init__(self, graph_engine):
        self.logger = logging.getLogger(__name__)
        self.graph_engine = graph_engine
        self.ontology_classes = {}
        self.ontology_relationships = {}
        self.ontology_properties = {}
        self.validation_cache = {}
        
        # Initialize base ontology
        self._initialize_base_ontology()
    
    async def initialize(self):
        """Initialize ontology manager"""
        await self._load_ontology()
        self.logger.info("Ontology manager initialized")
    
    async def shutdown(self):
        """Shutdown ontology manager"""
        await self._save_ontology()
        self.logger.info("Ontology manager shutdown")
    
    def _initialize_base_ontology(self):
        """Initialize base ontology classes and relationships"""
        # Base Entity class
        base_entity = OntologyClass(
            name="Entity",
            description="Base class for all entities in the knowledge graph",
            properties=[
                OntologyProperty("id", PropertyType.STRING, required=True, unique=True),
                OntologyProperty("type", PropertyType.STRING, required=True),
                OntologyProperty("created_at", PropertyType.DATETIME, required=True),
                OntologyProperty("updated_at", PropertyType.DATETIME, required=True),
                OntologyProperty("name", PropertyType.STRING),
                OntologyProperty("description", PropertyType.STRING)
            ],
            required_properties=["id", "type", "created_at", "updated_at"]
        )
        self.ontology_classes["Entity"] = base_entity
        
        # Common entity types
        person_class = OntologyClass(
            name="Person",
            description="A person or individual",
            parent_classes=["Entity"],
            properties=[
                OntologyProperty("first_name", PropertyType.STRING),
                OntologyProperty("last_name", PropertyType.STRING),
                OntologyProperty("email", PropertyType.STRING, unique=True),
                OntologyProperty("birth_date", PropertyType.DATE),
                OntologyProperty("nationality", PropertyType.STRING)
            ]
        )
        self.ontology_classes["Person"] = person_class
        
        organization_class = OntologyClass(
            name="Organization",
            description="An organization, company, or institution",
            parent_classes=["Entity"],
            properties=[
                OntologyProperty("legal_name", PropertyType.STRING, required=True),
                OntologyProperty("industry", PropertyType.STRING),
                OntologyProperty("founded_date", PropertyType.DATE),
                OntologyProperty("headquarters", PropertyType.STRING)
            ],
            required_properties=["legal_name"]
        )
        self.ontology_classes["Organization"] = organization_class
        
        location_class = OntologyClass(
            name="Location",
            description="A geographic location",
            parent_classes=["Entity"],
            properties=[
                OntologyProperty("latitude", PropertyType.FLOAT),
                OntologyProperty("longitude", PropertyType.FLOAT),
                OntologyProperty("address", PropertyType.STRING),
                OntologyProperty("city", PropertyType.STRING),
                OntologyProperty("country", PropertyType.STRING)
            ]
        )
        self.ontology_classes["Location"] = location_class
        
        # Base relationships
        related_to = OntologyRelationship(
            name="RELATED_TO",
            source_class="Entity",
            target_class="Entity",
            description="Generic relationship between entities",
            properties=[
                OntologyProperty("strength", PropertyType.FLOAT, constraints={"min": 0.0, "max": 1.0}),
                OntologyProperty("relationship_type", PropertyType.STRING)
            ]
        )
        self.ontology_relationships["RELATED_TO"] = related_to
        
        works_for = OntologyRelationship(
            name="WORKS_FOR",
            source_class="Person",
            target_class="Organization",
            description="Person works for organization",
            cardinality="many-to-one",
            properties=[
                OntologyProperty("position", PropertyType.STRING),
                OntologyProperty("start_date", PropertyType.DATE),
                OntologyProperty("end_date", PropertyType.DATE)
            ]
        )
        self.ontology_relationships["WORKS_FOR"] = works_for
        
        located_in = OntologyRelationship(
            name="LOCATED_IN",
            source_class="Entity",
            target_class="Location",
            description="Entity is located in a location",
            cardinality="many-to-one"
        )
        self.ontology_relationships["LOCATED_IN"] = located_in
    
    async def get_ontology(self) -> Dict[str, Any]:
        """Get complete ontology definition"""
        return {
            "classes": {name: asdict(cls) for name, cls in self.ontology_classes.items()},
            "relationships": {name: asdict(rel) for name, rel in self.ontology_relationships.items()},
            "properties": {name: asdict(prop) for name, prop in self.ontology_properties.items()},
            "metadata": {
                "version": "1.0.0",
                "last_updated": datetime.now().isoformat(),
                "total_classes": len(self.ontology_classes),
                "total_relationships": len(self.ontology_relationships)
            }
        }
    
    async def create_class(self, class_data: Dict[str, Any]) -> OntologyClass:
        """Create a new ontology class"""
        try:
            # Parse properties
            properties = []
            if "properties" in class_data:
                for prop_data in class_data["properties"]:
                    prop = OntologyProperty(
                        name=prop_data["name"],
                        property_type=PropertyType(prop_data["type"]),
                        required=prop_data.get("required", False),
                        unique=prop_data.get("unique", False),
                        description=prop_data.get("description", ""),
                        constraints=prop_data.get("constraints", {})
                    )
                    properties.append(prop)
            
            # Create class
            ontology_class = OntologyClass(
                name=class_data["name"],
                description=class_data.get("description", ""),
                parent_classes=class_data.get("parent_classes", []),
                properties=properties,
                required_properties=class_data.get("required_properties", []),
                constraints=class_data.get("constraints", {})
            )
            
            # Validate class
            await self._validate_class(ontology_class)
            
            # Store class
            self.ontology_classes[ontology_class.name] = ontology_class
            
            self.logger.info(f"Created ontology class: {ontology_class.name}")
            return ontology_class
            
        except Exception as e:
            self.logger.error(f"Error creating ontology class: {e}")
            raise
    
    async def create_property(self, property_data: Dict[str, Any]) -> OntologyProperty:
        """Create a new ontology property"""
        try:
            prop = OntologyProperty(
                name=property_data["name"],
                property_type=PropertyType(property_data["type"]),
                required=property_data.get("required", False),
                unique=property_data.get("unique", False),
                description=property_data.get("description", ""),
                constraints=property_data.get("constraints", {})
            )
            
            # Validate property
            await self._validate_property(prop)
            
            # Store property
            self.ontology_properties[prop.name] = prop
            
            self.logger.info(f"Created ontology property: {prop.name}")
            return prop
            
        except Exception as e:
            self.logger.error(f"Error creating ontology property: {e}")
            raise
    
    async def create_relationship(self, relationship_data: Dict[str, Any]) -> OntologyRelationship:
        """Create a new ontology relationship"""
        try:
            # Parse properties
            properties = []
            if "properties" in relationship_data:
                for prop_data in relationship_data["properties"]:
                    prop = OntologyProperty(
                        name=prop_data["name"],
                        property_type=PropertyType(prop_data["type"]),
                        required=prop_data.get("required", False),
                        unique=prop_data.get("unique", False),
                        description=prop_data.get("description", ""),
                        constraints=prop_data.get("constraints", {})
                    )
                    properties.append(prop)
            
            # Create relationship
            relationship = OntologyRelationship(
                name=relationship_data["name"],
                source_class=relationship_data["source_class"],
                target_class=relationship_data["target_class"],
                description=relationship_data.get("description", ""),
                properties=properties,
                cardinality=relationship_data.get("cardinality", "many-to-many"),
                inverse_relationship=relationship_data.get("inverse_relationship"),
                constraints=relationship_data.get("constraints", {})
            )
            
            # Validate relationship
            await self._validate_relationship(relationship)
            
            # Store relationship
            self.ontology_relationships[relationship.name] = relationship
            
            self.logger.info(f"Created ontology relationship: {relationship.name}")
            return relationship
            
        except Exception as e:
            self.logger.error(f"Error creating ontology relationship: {e}")
            raise
    
    async def validate_entity(self, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate entity against ontology"""
        try:
            entity_type = entity_data.get("type")
            if not entity_type:
                return {"valid": False, "errors": ["Entity type is required"]}
            
            # Get ontology class
            ontology_class = self.ontology_classes.get(entity_type)
            if not ontology_class:
                return {"valid": False, "errors": [f"Unknown entity type: {entity_type}"]}
            
            # Validate against class definition
            validation_result = await self._validate_entity_against_class(entity_data, ontology_class)
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Error validating entity: {e}")
            return {"valid": False, "errors": [f"Validation error: {str(e)}"]}
    
    async def validate_relationship(self, relationship_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate relationship against ontology"""
        try:
            relationship_type = relationship_data.get("type")
            if not relationship_type:
                return {"valid": False, "errors": ["Relationship type is required"]}
            
            # Get ontology relationship
            ontology_rel = self.ontology_relationships.get(relationship_type)
            if not ontology_rel:
                return {"valid": False, "errors": [f"Unknown relationship type: {relationship_type}"]}
            
            # Validate against relationship definition
            validation_result = await self._validate_relationship_against_definition(
                relationship_data, ontology_rel
            )
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Error validating relationship: {e}")
            return {"valid": False, "errors": [f"Validation error: {str(e)}"]}
    
    async def _validate_class(self, ontology_class: OntologyClass):
        """Validate ontology class definition"""
        errors = []
        
        # Check for circular inheritance
        if await self._has_circular_inheritance(ontology_class.name, ontology_class.parent_classes):
            errors.append(f"Circular inheritance detected for class {ontology_class.name}")
        
        # Validate parent classes exist
        for parent in ontology_class.parent_classes:
            if parent not in self.ontology_classes:
                errors.append(f"Parent class {parent} does not exist")
        
        # Validate properties
        for prop in ontology_class.properties:
            prop_errors = await self._validate_property(prop)
            errors.extend(prop_errors)
        
        if errors:
            raise ValueError(f"Class validation failed: {', '.join(errors)}")
    
    async def _validate_property(self, prop: OntologyProperty) -> List[str]:
        """Validate ontology property"""
        errors = []
        
        # Validate constraints based on type
        if prop.property_type == PropertyType.STRING:
            if "max_length" in prop.constraints and prop.constraints["max_length"] <= 0:
                errors.append(f"Invalid max_length for string property {prop.name}")
        
        elif prop.property_type in [PropertyType.INTEGER, PropertyType.FLOAT]:
            if "min" in prop.constraints and "max" in prop.constraints:
                if prop.constraints["min"] > prop.constraints["max"]:
                    errors.append(f"Invalid range for numeric property {prop.name}")
        
        return errors
    
    async def _validate_relationship(self, relationship: OntologyRelationship):
        """Validate ontology relationship definition"""
        errors = []
        
        # Check if source and target classes exist
        if relationship.source_class not in self.ontology_classes:
            errors.append(f"Source class {relationship.source_class} does not exist")
        
        if relationship.target_class not in self.ontology_classes:
            errors.append(f"Target class {relationship.target_class} does not exist")
        
        # Validate cardinality
        valid_cardinalities = ["one-to-one", "one-to-many", "many-to-one", "many-to-many"]
        if relationship.cardinality not in valid_cardinalities:
            errors.append(f"Invalid cardinality: {relationship.cardinality}")
        
        # Validate properties
        for prop in relationship.properties:
            prop_errors = await self._validate_property(prop)
            errors.extend(prop_errors)
        
        if errors:
            raise ValueError(f"Relationship validation failed: {', '.join(errors)}")
    
    async def _validate_entity_against_class(self, entity_data: Dict[str, Any], 
                                           ontology_class: OntologyClass) -> Dict[str, Any]:
        """Validate entity against class definition"""
        errors = []
        warnings = []
        
        # Get all properties (including inherited)
        all_properties = await self._get_all_class_properties(ontology_class)
        all_required = await self._get_all_required_properties(ontology_class)
        
        entity_properties = entity_data.get("properties", {})
        
        # Check required properties
        for required_prop in all_required:
            if required_prop not in entity_properties and required_prop not in entity_data:
                errors.append(f"Missing required property: {required_prop}")
        
        # Validate property types and constraints
        for prop_name, prop_value in entity_properties.items():
            prop_def = next((p for p in all_properties if p.name == prop_name), None)
            
            if not prop_def:
                warnings.append(f"Unknown property: {prop_name}")
                continue
            
            # Type validation
            type_valid, type_error = self._validate_property_type(prop_value, prop_def.property_type)
            if not type_valid:
                errors.append(f"Property {prop_name}: {type_error}")
            
            # Constraint validation
            constraint_valid, constraint_error = self._validate_property_constraints(
                prop_value, prop_def.constraints
            )
            if not constraint_valid:
                errors.append(f"Property {prop_name}: {constraint_error}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    async def _validate_relationship_against_definition(self, relationship_data: Dict[str, Any], 
                                                      ontology_rel: OntologyRelationship) -> Dict[str, Any]:
        """Validate relationship against definition"""
        errors = []
        warnings = []
        
        # Validate source and target entity types
        source_id = relationship_data.get("source_id")
        target_id = relationship_data.get("target_id")
        
        if source_id and target_id:
            # Get entity types
            source_entity = await self.graph_engine.get_entity(source_id)
            target_entity = await self.graph_engine.get_entity(target_id)
            
            if source_entity:
                source_type = source_entity.get("type")
                if not await self._is_instance_of_class(source_type, ontology_rel.source_class):
                    errors.append(f"Source entity type {source_type} is not compatible with {ontology_rel.source_class}")
            
            if target_entity:
                target_type = target_entity.get("type")
                if not await self._is_instance_of_class(target_type, ontology_rel.target_class):
                    errors.append(f"Target entity type {target_type} is not compatible with {ontology_rel.target_class}")
        
        # Validate relationship properties
        rel_properties = relationship_data.get("properties", {})
        
        for prop in ontology_rel.properties:
            if prop.required and prop.name not in rel_properties:
                errors.append(f"Missing required relationship property: {prop.name}")
            
            if prop.name in rel_properties:
                prop_value = rel_properties[prop.name]
                
                # Type validation
                type_valid, type_error = self._validate_property_type(prop_value, prop.property_type)
                if not type_valid:
                    errors.append(f"Relationship property {prop.name}: {type_error}")
                
                # Constraint validation
                constraint_valid, constraint_error = self._validate_property_constraints(
                    prop_value, prop.constraints
                )
                if not constraint_valid:
                    errors.append(f"Relationship property {prop.name}: {constraint_error}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _validate_property_type(self, value: Any, property_type: PropertyType) -> tuple[bool, str]:
        """Validate property value against type"""
        try:
            if property_type == PropertyType.STRING and not isinstance(value, str):
                return False, f"Expected string, got {type(value).__name__}"
            
            elif property_type == PropertyType.INTEGER and not isinstance(value, int):
                return False, f"Expected integer, got {type(value).__name__}"
            
            elif property_type == PropertyType.FLOAT and not isinstance(value, (int, float)):
                return False, f"Expected float, got {type(value).__name__}"
            
            elif property_type == PropertyType.BOOLEAN and not isinstance(value, bool):
                return False, f"Expected boolean, got {type(value).__name__}"
            
            elif property_type == PropertyType.LIST and not isinstance(value, list):
                return False, f"Expected list, got {type(value).__name__}"
            
            elif property_type == PropertyType.OBJECT and not isinstance(value, dict):
                return False, f"Expected object, got {type(value).__name__}"
            
            return True, ""
            
        except Exception as e:
            return False, f"Type validation error: {str(e)}"
    
    def _validate_property_constraints(self, value: Any, constraints: Dict[str, Any]) -> tuple[bool, str]:
        """Validate property value against constraints"""
        try:
            if not constraints:
                return True, ""
            
            # String constraints
            if isinstance(value, str):
                if "max_length" in constraints and len(value) > constraints["max_length"]:
                    return False, f"String too long (max: {constraints['max_length']})"
                
                if "min_length" in constraints and len(value) < constraints["min_length"]:
                    return False, f"String too short (min: {constraints['min_length']})"
                
                if "pattern" in constraints:
                    import re
                    if not re.match(constraints["pattern"], value):
                        return False, f"String does not match pattern: {constraints['pattern']}"
            
            # Numeric constraints
            elif isinstance(value, (int, float)):
                if "min" in constraints and value < constraints["min"]:
                    return False, f"Value too small (min: {constraints['min']})"
                
                if "max" in constraints and value > constraints["max"]:
                    return False, f"Value too large (max: {constraints['max']})"
            
            return True, ""
            
        except Exception as e:
            return False, f"Constraint validation error: {str(e)}"
    
    async def _has_circular_inheritance(self, class_name: str, parent_classes: List[str], 
                                      visited: Set[str] = None) -> bool:
        """Check for circular inheritance"""
        if visited is None:
            visited = set()
        
        if class_name in visited:
            return True
        
        visited.add(class_name)
        
        for parent in parent_classes:
            if parent in self.ontology_classes:
                parent_class = self.ontology_classes[parent]
                if await self._has_circular_inheritance(parent, parent_class.parent_classes, visited.copy()):
                    return True
        
        return False
    
    async def _get_all_class_properties(self, ontology_class: OntologyClass) -> List[OntologyProperty]:
        """Get all properties including inherited ones"""
        all_properties = list(ontology_class.properties)
        
        # Add inherited properties
        for parent_name in ontology_class.parent_classes:
            if parent_name in self.ontology_classes:
                parent_class = self.ontology_classes[parent_name]
                parent_properties = await self._get_all_class_properties(parent_class)
                all_properties.extend(parent_properties)
        
        # Remove duplicates
        unique_properties = {}
        for prop in all_properties:
            unique_properties[prop.name] = prop
        
        return list(unique_properties.values())
    
    async def _get_all_required_properties(self, ontology_class: OntologyClass) -> List[str]:
        """Get all required properties including inherited ones"""
        all_required = list(ontology_class.required_properties)
        
        # Add inherited required properties
        for parent_name in ontology_class.parent_classes:
            if parent_name in self.ontology_classes:
                parent_class = self.ontology_classes[parent_name]
                parent_required = await self._get_all_required_properties(parent_class)
                all_required.extend(parent_required)
        
        # Also add properties marked as required
        all_properties = await self._get_all_class_properties(ontology_class)
        for prop in all_properties:
            if prop.required and prop.name not in all_required:
                all_required.append(prop.name)
        
        return list(set(all_required))
    
    async def _is_instance_of_class(self, entity_type: str, target_class: str) -> bool:
        """Check if entity type is instance of or inherits from target class"""
        if entity_type == target_class:
            return True
        
        if entity_type in self.ontology_classes:
            entity_class = self.ontology_classes[entity_type]
            for parent in entity_class.parent_classes:
                if await self._is_instance_of_class(parent, target_class):
                    return True
        
        return False
    
    async def _load_ontology(self):
        """Load ontology from storage"""
        # This would load ontology from persistent storage
        self.logger.debug("Loading ontology from storage")
    
    async def _save_ontology(self):
        """Save ontology to storage"""
        # This would save ontology to persistent storage
        self.logger.debug("Saving ontology to storage")