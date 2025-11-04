"""
Client Migration Utilities
Provides tools and utilities to help clients migrate between API versions
"""

import json
import yaml
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import logging
from packaging import version
import re

logger = logging.getLogger(__name__)


class MigrationType(Enum):
    """Types of migrations"""
    VERSION_UPGRADE = "version_upgrade"
    VERSION_DOWNGRADE = "version_downgrade"
    ENDPOINT_MIGRATION = "endpoint_migration"
    PARAMETER_MIGRATION = "parameter_migration"
    SCHEMA_MIGRATION = "schema_migration"


class MigrationComplexity(Enum):
    """Migration complexity levels"""
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    BREAKING = "breaking"


@dataclass
class MigrationStep:
    """Represents a single migration step"""
    step_id: str
    title: str
    description: str
    step_type: str  # "code_change", "config_change", "data_migration", etc.
    complexity: MigrationComplexity
    required: bool
    estimated_time_minutes: int
    code_examples: Dict[str, str]  # language -> code example
    validation_steps: List[str]
    dependencies: List[str]  # other step_ids that must be completed first
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['complexity'] = self.complexity.value
        return data


@dataclass
class MigrationPlan:
    """Complete migration plan between versions"""
    plan_id: str
    from_version: str
    to_version: str
    migration_type: MigrationType
    overall_complexity: MigrationComplexity
    estimated_total_time_hours: float
    breaking_changes: List[str]
    steps: List[MigrationStep]
    prerequisites: List[str]
    testing_checklist: List[str]
    rollback_plan: Optional[str]
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['migration_type'] = self.migration_type.value
        data['overall_complexity'] = self.overall_complexity.value
        data['created_at'] = self.created_at.isoformat()
        data['steps'] = [step.to_dict() for step in self.steps]
        return data


class CodeGenerator:
    """Generates migration code examples for different languages"""
    
    def __init__(self):
        self.templates = {
            'python': {
                'client_update': '''
# Update API client to version {to_version}
import requests

class APIClient:
    def __init__(self, base_url: str, api_version: str = "{to_version}"):
        self.base_url = base_url
        self.api_version = api_version
        self.session = requests.Session()
        self.session.headers.update({{
            'Accept': f'application/vnd.api+json;version={{api_version}}',
            'Content-Type': 'application/json'
        }})
    
    def make_request(self, method: str, endpoint: str, **kwargs):
        url = f"{{self.base_url}}/{{endpoint}}"
        return self.session.request(method, url, **kwargs)
''',
                'parameter_migration': '''
# Migrate parameters from {from_version} to {to_version}
def migrate_request_params(old_params: dict) -> dict:
    new_params = old_params.copy()
    
    # Parameter migrations
{parameter_changes}
    
    return new_params
''',
                'response_handling': '''
# Handle response format changes from {from_version} to {to_version}
def handle_response(response_data: dict) -> dict:
    # Response format migrations
{response_changes}
    
    return response_data
'''
            },
            'javascript': {
                'client_update': '''
// Update API client to version {to_version}
class APIClient {{
    constructor(baseUrl, apiVersion = '{to_version}') {{
        this.baseUrl = baseUrl;
        this.apiVersion = apiVersion;
        this.defaultHeaders = {{
            'Accept': `application/vnd.api+json;version=${{apiVersion}}`,
            'Content-Type': 'application/json'
        }};
    }}
    
    async makeRequest(method, endpoint, options = {{}}) {{
        const url = `${{this.baseUrl}}/${{endpoint}}`;
        const config = {{
            method,
            headers: {{ ...this.defaultHeaders, ...options.headers }},
            ...options
        }};
        
        return fetch(url, config);
    }}
}}
''',
                'parameter_migration': '''
// Migrate parameters from {from_version} to {to_version}
function migrateRequestParams(oldParams) {{
    const newParams = {{ ...oldParams }};
    
    // Parameter migrations
{parameter_changes}
    
    return newParams;
}}
''',
                'response_handling': '''
// Handle response format changes from {from_version} to {to_version}
function handleResponse(responseData) {{
    // Response format migrations
{response_changes}
    
    return responseData;
}}
'''
            },
            'curl': {
                'request_example': '''
# API request for version {to_version}
curl -X {method} \\
  -H "Accept: application/vnd.api+json;version={to_version}" \\
  -H "Content-Type: application/json" \\
{headers}  "{url}{endpoint}"
'''
            }
        }
    
    def generate_client_update_code(self, language: str, from_version: str, 
                                  to_version: str) -> str:
        """Generate code for updating API client"""
        if language not in self.templates:
            return f"# Update your {language} client to use API version {to_version}"
        
        template = self.templates[language].get('client_update', '')
        return template.format(
            from_version=from_version,
            to_version=to_version
        )
    
    def generate_parameter_migration_code(self, language: str, from_version: str,
                                        to_version: str, changes: List[Dict[str, Any]]) -> str:
        """Generate code for parameter migrations"""
        if language not in self.templates:
            return f"# Migrate parameters for {language} from {from_version} to {to_version}"
        
        template = self.templates[language].get('parameter_migration', '')
        
        # Generate parameter change code
        parameter_changes = []
        for change in changes:
            if change['type'] == 'rename':
                if language == 'python':
                    parameter_changes.append(
                        f"    if '{change['old_name']}' in new_params:\n"
                        f"        new_params['{change['new_name']}'] = new_params.pop('{change['old_name']}')"
                    )
                elif language == 'javascript':
                    parameter_changes.append(
                        f"    if ('{change['old_name']}' in newParams) {{\n"
                        f"        newParams['{change['new_name']}'] = newParams['{change['old_name']}'];\n"
                        f"        delete newParams['{change['old_name']}'];\n"
                        f"    }}"
                    )
            elif change['type'] == 'remove':
                if language == 'python':
                    parameter_changes.append(f"    new_params.pop('{change['name']}', None)")
                elif language == 'javascript':
                    parameter_changes.append(f"    delete newParams['{change['name']}'];")
        
        return template.format(
            from_version=from_version,
            to_version=to_version,
            parameter_changes='\n'.join(parameter_changes)
        )
    
    def generate_curl_example(self, method: str, endpoint: str, version: str,
                            headers: Dict[str, str] = None, base_url: str = "https://api.example.com") -> str:
        """Generate curl example for new version"""
        template = self.templates['curl']['request_example']
        
        header_lines = []
        if headers:
            for key, value in headers.items():
                header_lines.append(f'  -H "{key}: {value}" \\')
        
        return template.format(
            method=method,
            to_version=version,
            headers='\n'.join(header_lines),
            url=base_url,
            endpoint=endpoint
        )


class MigrationValidator:
    """Validates migration completeness and correctness"""
    
    def __init__(self):
        self.validation_rules = {
            'version_format': r'^\d+\.\d+\.\d+$',
            'endpoint_format': r'^/[a-zA-Z0-9/_-]+$'
        }
    
    def validate_migration_plan(self, plan: MigrationPlan) -> Tuple[bool, List[str]]:
        """Validate a migration plan"""
        errors = []
        
        # Validate version formats
        if not re.match(self.validation_rules['version_format'], plan.from_version):
            errors.append(f"Invalid from_version format: {plan.from_version}")
        
        if not re.match(self.validation_rules['version_format'], plan.to_version):
            errors.append(f"Invalid to_version format: {plan.to_version}")
        
        # Validate step dependencies
        step_ids = {step.step_id for step in plan.steps}
        for step in plan.steps:
            for dep_id in step.dependencies:
                if dep_id not in step_ids:
                    errors.append(f"Step {step.step_id} has invalid dependency: {dep_id}")
        
        # Validate complexity assignment
        breaking_steps = [s for s in plan.steps if s.complexity == MigrationComplexity.BREAKING]
        if breaking_steps and plan.overall_complexity != MigrationComplexity.BREAKING:
            errors.append("Plan contains breaking steps but overall complexity is not marked as breaking")
        
        return len(errors) == 0, errors
    
    def validate_api_compatibility(self, client_version: str, server_version: str) -> Dict[str, Any]:
        """Validate API compatibility between versions"""
        try:
            client_ver = version.parse(client_version)
            server_ver = version.parse(server_version)
            
            result = {
                'compatible': True,
                'warnings': [],
                'recommendations': []
            }
            
            if client_ver.major != server_ver.major:
                result['compatible'] = False
                result['warnings'].append("Major version mismatch - breaking changes expected")
                result['recommendations'].append("Perform major version migration")
            
            elif client_ver.minor > server_ver.minor:
                result['warnings'].append("Client version is newer than server")
                result['recommendations'].append("Update server or downgrade client")
            
            elif client_ver.minor < server_ver.minor:
                result['warnings'].append("Client version is older - some features may be unavailable")
                result['recommendations'].append("Upgrade client to latest version")
            
            return result
            
        except Exception as e:
            return {
                'compatible': False,
                'warnings': [f"Version parsing error: {e}"],
                'recommendations': ["Verify version format"]
            }


class MigrationPlanner:
    """Creates migration plans between API versions"""
    
    def __init__(self):
        self.code_generator = CodeGenerator()
        self.validator = MigrationValidator()
        self.migration_templates = self._load_migration_templates()
    
    def _load_migration_templates(self) -> Dict[str, Any]:
        """Load migration templates for common scenarios"""
        return {
            'version_upgrade': {
                'steps': [
                    {
                        'title': 'Update API Version Header',
                        'description': 'Update your client to send the new API version in headers',
                        'type': 'code_change',
                        'complexity': MigrationComplexity.SIMPLE,
                        'estimated_time': 15
                    },
                    {
                        'title': 'Test Basic Functionality',
                        'description': 'Verify that basic API calls work with the new version',
                        'type': 'testing',
                        'complexity': MigrationComplexity.SIMPLE,
                        'estimated_time': 30
                    }
                ]
            },
            'breaking_change_migration': {
                'steps': [
                    {
                        'title': 'Review Breaking Changes',
                        'description': 'Carefully review all breaking changes in the migration guide',
                        'type': 'analysis',
                        'complexity': MigrationComplexity.MODERATE,
                        'estimated_time': 60
                    },
                    {
                        'title': 'Update Request Format',
                        'description': 'Modify your code to handle request format changes',
                        'type': 'code_change',
                        'complexity': MigrationComplexity.COMPLEX,
                        'estimated_time': 120
                    },
                    {
                        'title': 'Update Response Handling',
                        'description': 'Modify your code to handle response format changes',
                        'type': 'code_change',
                        'complexity': MigrationComplexity.COMPLEX,
                        'estimated_time': 90
                    },
                    {
                        'title': 'Comprehensive Testing',
                        'description': 'Test all functionality to ensure compatibility',
                        'type': 'testing',
                        'complexity': MigrationComplexity.MODERATE,
                        'estimated_time': 180
                    }
                ]
            }
        }
    
    def create_migration_plan(self, from_version: str, to_version: str,
                            breaking_changes: List[str] = None,
                            custom_steps: List[Dict[str, Any]] = None) -> MigrationPlan:
        """Create a migration plan between two versions"""
        
        breaking_changes = breaking_changes or []
        is_breaking = len(breaking_changes) > 0
        
        # Determine migration type and complexity
        migration_type = MigrationType.VERSION_UPGRADE
        if version.parse(from_version) > version.parse(to_version):
            migration_type = MigrationType.VERSION_DOWNGRADE
        
        overall_complexity = MigrationComplexity.BREAKING if is_breaking else MigrationComplexity.SIMPLE
        
        # Select appropriate template
        template_key = 'breaking_change_migration' if is_breaking else 'version_upgrade'
        template = self.migration_templates.get(template_key, self.migration_templates['version_upgrade'])
        
        # Create migration steps
        steps = []
        step_counter = 1
        
        for step_template in template['steps']:
            step = MigrationStep(
                step_id=f"step_{step_counter}",
                title=step_template['title'],
                description=step_template['description'],
                step_type=step_template['type'],
                complexity=step_template['complexity'],
                required=True,
                estimated_time_minutes=step_template['estimated_time'],
                code_examples=self._generate_step_code_examples(step_template, from_version, to_version),
                validation_steps=self._generate_validation_steps(step_template),
                dependencies=[]
            )
            steps.append(step)
            step_counter += 1
        
        # Add custom steps if provided
        if custom_steps:
            for custom_step in custom_steps:
                step = MigrationStep(
                    step_id=f"custom_step_{step_counter}",
                    title=custom_step.get('title', 'Custom Migration Step'),
                    description=custom_step.get('description', ''),
                    step_type=custom_step.get('type', 'code_change'),
                    complexity=MigrationComplexity(custom_step.get('complexity', 'moderate')),
                    required=custom_step.get('required', True),
                    estimated_time_minutes=custom_step.get('estimated_time', 60),
                    code_examples=custom_step.get('code_examples', {}),
                    validation_steps=custom_step.get('validation_steps', []),
                    dependencies=custom_step.get('dependencies', [])
                )
                steps.append(step)
                step_counter += 1
        
        # Calculate total estimated time
        total_time_minutes = sum(step.estimated_time_minutes for step in steps)
        total_time_hours = total_time_minutes / 60.0
        
        # Create plan
        plan = MigrationPlan(
            plan_id=f"migration_{from_version}_to_{to_version}_{int(datetime.utcnow().timestamp())}",
            from_version=from_version,
            to_version=to_version,
            migration_type=migration_type,
            overall_complexity=overall_complexity,
            estimated_total_time_hours=total_time_hours,
            breaking_changes=breaking_changes,
            steps=steps,
            prerequisites=self._generate_prerequisites(from_version, to_version),
            testing_checklist=self._generate_testing_checklist(),
            rollback_plan=self._generate_rollback_plan(from_version, to_version),
            created_at=datetime.utcnow()
        )
        
        return plan
    
    def _generate_step_code_examples(self, step_template: Dict[str, Any], 
                                   from_version: str, to_version: str) -> Dict[str, str]:
        """Generate code examples for a migration step"""
        examples = {}
        
        if step_template['type'] == 'code_change':
            if 'API Version Header' in step_template['title']:
                examples['python'] = self.code_generator.generate_client_update_code(
                    'python', from_version, to_version
                )
                examples['javascript'] = self.code_generator.generate_client_update_code(
                    'javascript', from_version, to_version
                )
                examples['curl'] = self.code_generator.generate_curl_example(
                    'GET', '/api/endpoint', to_version
                )
        
        return examples
    
    def _generate_validation_steps(self, step_template: Dict[str, Any]) -> List[str]:
        """Generate validation steps for a migration step"""
        if step_template['type'] == 'testing':
            return [
                "Make a test API call with the new version",
                "Verify response format is as expected",
                "Check error handling with invalid requests",
                "Validate all critical functionality works"
            ]
        elif step_template['type'] == 'code_change':
            return [
                "Code compiles/runs without errors",
                "Unit tests pass",
                "Integration tests pass"
            ]
        
        return ["Step completed successfully"]
    
    def _generate_prerequisites(self, from_version: str, to_version: str) -> List[str]:
        """Generate prerequisites for migration"""
        return [
            "Access to API documentation for both versions",
            "Test environment for validation",
            "Backup of current implementation",
            "Understanding of your current API usage patterns"
        ]
    
    def _generate_testing_checklist(self) -> List[str]:
        """Generate testing checklist for migration"""
        return [
            "All existing functionality works correctly",
            "New features are accessible and working",
            "Error handling is appropriate",
            "Performance is acceptable",
            "Security requirements are met",
            "Logging and monitoring work correctly"
        ]
    
    def _generate_rollback_plan(self, from_version: str, to_version: str) -> str:
        """Generate rollback plan"""
        return f"""
Rollback Plan for {from_version} -> {to_version} migration:

1. Keep the old client implementation available
2. Change API version header back to {from_version}
3. Revert any code changes specific to {to_version}
4. Test that all functionality works with {from_version}
5. Monitor for any issues after rollback

Note: Ensure your rollback doesn't lose any data or state that was created using {to_version}.
"""


class MigrationGuideGenerator:
    """Generates comprehensive migration guides"""
    
    def __init__(self):
        self.planner = MigrationPlanner()
    
    def generate_markdown_guide(self, plan: MigrationPlan) -> str:
        """Generate a markdown migration guide"""
        
        guide = f"""# Migration Guide: {plan.from_version} → {plan.to_version}

## Overview
This guide will help you migrate your API client from version {plan.from_version} to {plan.to_version}.

**Migration Type:** {plan.migration_type.value}  
**Complexity:** {plan.overall_complexity.value}  
**Estimated Time:** {plan.estimated_total_time_hours:.1f} hours  

"""
        
        if plan.breaking_changes:
            guide += f"""## ⚠️ Breaking Changes
The following breaking changes require your attention:

"""
            for change in plan.breaking_changes:
                guide += f"- {change}\n"
            guide += "\n"
        
        guide += f"""## Prerequisites
Before starting the migration, ensure you have:

"""
        for prereq in plan.prerequisites:
            guide += f"- {prereq}\n"
        
        guide += f"""

## Migration Steps

"""
        
        for i, step in enumerate(plan.steps, 1):
            guide += f"""### Step {i}: {step.title}

**Description:** {step.description}  
**Type:** {step.step_type}  
**Complexity:** {step.complexity.value}  
**Estimated Time:** {step.estimated_time_minutes} minutes  
**Required:** {'Yes' if step.required else 'No'}  

"""
            
            if step.code_examples:
                guide += "**Code Examples:**\n\n"
                for lang, code in step.code_examples.items():
                    guide += f"**{lang.title()}:**\n```{lang}\n{code}\n```\n\n"
            
            if step.validation_steps:
                guide += "**Validation:**\n"
                for validation in step.validation_steps:
                    guide += f"- {validation}\n"
                guide += "\n"
        
        guide += f"""## Testing Checklist

After completing the migration, verify:

"""
        for test in plan.testing_checklist:
            guide += f"- [ ] {test}\n"
        
        if plan.rollback_plan:
            guide += f"""

## Rollback Plan

{plan.rollback_plan}
"""
        
        guide += f"""

## Support

If you encounter issues during migration:
1. Check the API documentation for both versions
2. Review error messages carefully
3. Test in a development environment first
4. Contact support with specific error details

---
*Migration guide generated on {plan.created_at.strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        return guide
    
    def generate_json_guide(self, plan: MigrationPlan) -> str:
        """Generate a JSON migration guide"""
        return json.dumps(plan.to_dict(), indent=2)
    
    def generate_yaml_guide(self, plan: MigrationPlan) -> str:
        """Generate a YAML migration guide"""
        return yaml.dump(plan.to_dict(), default_flow_style=False)


class MigrationToolkit:
    """Main toolkit for migration utilities"""
    
    def __init__(self):
        self.planner = MigrationPlanner()
        self.guide_generator = MigrationGuideGenerator()
        self.validator = MigrationValidator()
        self.code_generator = CodeGenerator()
    
    def create_migration_guide(self, from_version: str, to_version: str,
                             breaking_changes: List[str] = None,
                             format: str = 'markdown') -> str:
        """Create a complete migration guide"""
        
        # Create migration plan
        plan = self.planner.create_migration_plan(from_version, to_version, breaking_changes)
        
        # Validate plan
        is_valid, errors = self.validator.validate_migration_plan(plan)
        if not is_valid:
            logger.warning(f"Migration plan validation errors: {errors}")
        
        # Generate guide in requested format
        if format.lower() == 'json':
            return self.guide_generator.generate_json_guide(plan)
        elif format.lower() == 'yaml':
            return self.guide_generator.generate_yaml_guide(plan)
        else:
            return self.guide_generator.generate_markdown_guide(plan)
    
    def check_migration_readiness(self, client_version: str, target_version: str) -> Dict[str, Any]:
        """Check if client is ready for migration"""
        compatibility = self.validator.validate_api_compatibility(client_version, target_version)
        
        return {
            'ready_for_migration': compatibility['compatible'],
            'required_actions': compatibility.get('recommendations', []),
            'warnings': compatibility.get('warnings', []),
            'suggested_migration_path': self._suggest_migration_path(client_version, target_version)
        }
    
    def _suggest_migration_path(self, from_version: str, to_version: str) -> List[str]:
        """Suggest optimal migration path"""
        # For now, suggest direct migration
        # In practice, you might suggest intermediate versions for large version gaps
        return [from_version, to_version]