import sys
import yaml
import re
import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set

def slug(s: str) -> str:
    """Generate safe Mermaid identifier from string.

    Supports Japanese characters by preserving them in the identifier.
    Only replaces symbols and whitespace with underscores.
    """
    s = str(s).replace("::", "_")
    # 日本語文字を保持しつつ、スペースや記号のみを "_" に変換
    # [\s\-./\\()[\]{}]+ = スペース、ハイフン、ドット、スラッシュ、括弧など
    s = re.sub(r"[\s\-./\\()\[\]{}]+", "_", s)
    # 連続するアンダースコアを1つにまとめる
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "id"
    # 数字で始まる場合は "n_" を付加
    if re.match(r"^[0-9]", s):
        s = "n_" + s
    return s

def load_model_from_csv(csv_path: str, model_type: str) -> Optional[Dict[str, Any]]:
    """Load model definition from CSV file.

    CSV format:
        論理名,物理名,データ型,サイズ,キー,説明
        (Header row is skipped, we extract from '物理名' column)

    Filename format:
        論理名__ModelName.csv
        └─────┘  └───┬───┘
        logical   physical name (used as model name)

    Args:
        csv_path: Path to CSV file
        model_type: 'program' or 'datastore'

    Returns:
        Model definition dict {name, type, props} or None if failed
    """
    try:
        # Extract model name from filename: *__ModelName.csv
        filename = Path(csv_path).stem
        if "__" not in filename:
            print(f"Warning: CSV filename '{csv_path}' does not match pattern '論理名__ModelName.csv'", file=sys.stderr)
            return None

        model_name = filename.split("__")[-1]

        # Read CSV file
        props = []
        encodings = ['utf-8', 'cp932', 'shift_jis']
        content = None

        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if content is None:
            print(f"Error: Could not decode CSV file '{csv_path}' with any supported encoding", file=sys.stderr)
            return None

        # Parse CSV
        reader = csv.DictReader(content.splitlines())
        for row in reader:
            physical_name = row.get('物理名', '').strip()
            if physical_name:
                props.append(physical_name)

        if not props:
            print(f"Warning: No properties found in CSV file '{csv_path}'", file=sys.stderr)
            return None

        return {
            'name': model_name,
            'type': model_type,
            'props': props
        }

    except Exception as e:
        print(f"Error loading CSV '{csv_path}': {e}", file=sys.stderr)
        return None

def load_model_from_openapi(
    spec_path: str,
    schema_name: str,
    model_type: str
) -> Optional[Dict[str, Any]]:
    """Load model definition from OpenAPI specification.

    Supports OpenAPI 3.0.x and 3.1.x in YAML or JSON format.
    Extracts properties from components/schemas/<schema_name>.

    Args:
        spec_path: Path to OpenAPI spec file (.yaml, .yml, .json)
        schema_name: Schema name in components/schemas
        model_type: 'program' or 'datastore'

    Returns:
        Model definition dict {name, type, props} or None if failed

    Example:
        # openapi.yaml:
        components:
          schemas:
            User:
              type: object
              properties:
                id: {type: string}
                name: {type: string}

        load_model_from_openapi('openapi.yaml', 'User', 'program')
        # Returns: {'name': 'User', 'type': 'program', 'props': ['id', 'name']}
    """
    try:
        path = Path(spec_path)
        if not path.exists():
            print(f"Error: OpenAPI spec file '{spec_path}' does not exist", file=sys.stderr)
            return None

        # Load spec file (YAML or JSON)
        with open(path, 'r', encoding='utf-8') as f:
            if path.suffix.lower() in ['.yaml', '.yml']:
                spec = yaml.safe_load(f)
            elif path.suffix.lower() == '.json':
                spec = json.load(f)
            else:
                print(f"Error: Unsupported file format '{path.suffix}' (expected .yaml, .yml, or .json)", file=sys.stderr)
                return None

        # Navigate to components/schemas
        if 'components' not in spec:
            print(f"Warning: No 'components' section in OpenAPI spec '{spec_path}'", file=sys.stderr)
            return None

        schemas = spec['components'].get('schemas', {})
        if schema_name not in schemas:
            print(f"Warning: Schema '{schema_name}' not found in OpenAPI spec '{spec_path}'", file=sys.stderr)
            return None

        schema = schemas[schema_name]

        # Extract properties
        props = []
        if 'properties' in schema:
            props = list(schema['properties'].keys())

        # Handle allOf (merge properties from referenced schemas)
        if 'allOf' in schema:
            for item in schema['allOf']:
                if 'properties' in item:
                    props.extend(item['properties'].keys())
                # Note: $ref resolution is not implemented for simplicity
                # Can be added in future if needed

        if not props:
            print(f"Warning: No properties found in schema '{schema_name}' in '{spec_path}'", file=sys.stderr)
            return None

        return {
            'name': schema_name,
            'type': model_type,
            'props': props
        }

    except Exception as e:
        print(f"Error loading OpenAPI spec '{spec_path}': {e}", file=sys.stderr)
        return None

def load_model_from_asyncapi(
    spec_path: str,
    schema_name: str,
    model_type: str
) -> Optional[Dict[str, Any]]:
    """Load model definition from AsyncAPI 3.0 specification.

    Supports AsyncAPI 3.x in YAML or JSON format.
    Extracts properties from components/schemas/<schema_name>.
    Supports $ref resolution for nested schema references.

    Args:
        spec_path: Path to AsyncAPI spec file (.yaml, .yml, .json)
        schema_name: Schema name in components/schemas
        model_type: 'program' or 'datastore'

    Returns:
        Model definition dict {name, type, props} or None if failed

    Example:
        # asyncapi.yaml (AsyncAPI 3.0):
        components:
          schemas:
            KafkaRemittance:
              type: object
              properties:
                sbSystemId: {type: string}
                remittance:
                  $ref: "#/components/schemas/Remittance"

        load_model_from_asyncapi('asyncapi.yaml', 'KafkaRemittance', 'program')
        # Returns: {'name': 'KafkaRemittance', 'type': 'program', 'props': ['sbSystemId', 'remittance']}
    """
    try:
        path = Path(spec_path)
        if not path.exists():
            print(f"Error: AsyncAPI spec file '{spec_path}' does not exist", file=sys.stderr)
            return None

        # Load spec file (YAML or JSON)
        with open(path, 'r', encoding='utf-8') as f:
            if path.suffix.lower() in ['.yaml', '.yml']:
                spec = yaml.safe_load(f)
            elif path.suffix.lower() == '.json':
                spec = json.load(f)
            else:
                print(f"Error: Unsupported file format '{path.suffix}' (expected .yaml, .yml, or .json)", file=sys.stderr)
                return None

        # Navigate to components/schemas
        if 'components' not in spec:
            print(f"Warning: No 'components' section in AsyncAPI spec '{spec_path}'", file=sys.stderr)
            return None

        schemas = spec['components'].get('schemas', {})
        if schema_name not in schemas:
            print(f"Warning: Schema '{schema_name}' not found in AsyncAPI spec '{spec_path}'", file=sys.stderr)
            return None

        schema = schemas[schema_name]

        # Helper function to resolve $ref recursively
        def resolve_ref(ref_path: str, visited: Optional[set] = None) -> List[str]:
            """Recursively resolve $ref and extract properties.

            Args:
                ref_path: The $ref path (e.g., "#/components/schemas/EventMetadata")
                visited: Set of already visited refs to detect cycles

            Returns:
                List of property names from the referenced schema
            """
            if visited is None:
                visited = set()

            # Cycle detection
            if ref_path in visited:
                print(f"Warning: Circular reference detected: {ref_path}", file=sys.stderr)
                return []
            visited.add(ref_path)

            # External references (http/https)
            if ref_path.startswith('http://') or ref_path.startswith('https://'):
                print(f"Warning: External reference '{ref_path}' in schema '{schema_name}' is not supported",
                      file=sys.stderr)
                return []

            # Only handle internal references
            if not ref_path.startswith('#/components/schemas/'):
                print(f"Warning: Unsupported $ref format '{ref_path}' in schema '{schema_name}' "
                      f"(expected '#/components/schemas/...')", file=sys.stderr)
                return []

            ref_schema_name = ref_path.split('/')[-1]

            # Schema existence check
            if ref_schema_name not in schemas:
                print(f"Warning: Referenced schema '{ref_schema_name}' not found in AsyncAPI spec '{spec_path}'",
                      file=sys.stderr)
                return []

            ref_schema = schemas[ref_schema_name]
            props = []

            # Extract direct properties
            if 'properties' in ref_schema:
                for prop_name, prop_def in ref_schema['properties'].items():
                    if isinstance(prop_def, dict) and '$ref' in prop_def:
                        # Nested $ref: resolve recursively and flatten
                        nested_props = resolve_ref(prop_def['$ref'], visited.copy())
                        # Flatten nested properties with dot notation
                        props.extend([f"{prop_name}.{p}" for p in nested_props] if nested_props else [prop_name])
                    else:
                        props.append(prop_name)

            # Handle allOf
            if 'allOf' in ref_schema:
                for item in ref_schema['allOf']:
                    if 'properties' in item:
                        props.extend(item['properties'].keys())
                    if '$ref' in item:
                        props.extend(resolve_ref(item['$ref'], visited.copy()))

            if not props:
                print(f"Info: Referenced schema '{ref_schema_name}' has no properties", file=sys.stderr)

            return props

        # Extract properties
        props = []
        if 'properties' in schema:
            for prop_name, prop_def in schema['properties'].items():
                if isinstance(prop_def, dict) and '$ref' in prop_def:
                    # Handle $ref in properties
                    nested_props = resolve_ref(prop_def['$ref'])
                    # Flatten nested properties with dot notation
                    props.extend([f"{prop_name}.{p}" for p in nested_props] if nested_props else [prop_name])
                else:
                    props.append(prop_name)

        # Handle allOf (merge properties from referenced schemas)
        if 'allOf' in schema:
            for item in schema['allOf']:
                if 'properties' in item:
                    props.extend(item['properties'].keys())
                # Handle $ref in allOf with improved error handling
                if '$ref' in item:
                    props.extend(resolve_ref(item['$ref']))

        if not props:
            print(f"Warning: No properties found in schema '{schema_name}' in '{spec_path}'", file=sys.stderr)
            return None

        return {
            'name': schema_name,
            'type': model_type,
            'props': props
        }

    except Exception as e:
        print(f"Error loading AsyncAPI spec '{spec_path}': {e}", file=sys.stderr)
        return None

def parse_reference(ref: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Parse a reference string into model, instance, and field components.

    Supports:
    - 'Model.field' → ('Model', None, 'field')
    - 'Model#instance.field' → ('Model', 'instance', 'field')
    - 'Model' → ('Model', None, None)
    - 'Model#instance' → ('Model', 'instance', None)

    Args:
        ref: Reference string

    Returns:
        Tuple of (model_name, instance_id, field_name)
        Any component can be None if not present
    """
    # Check for instance identifier '#'
    if '#' in ref:
        # Split on '#' first
        model_part, rest = ref.split('#', 1)

        # Check if there's a field after the instance
        if '.' in rest:
            instance, field = rest.split('.', 1)
            return (model_part, instance, field)
        else:
            # Just model#instance, no field
            return (model_part, rest, None)
    else:
        # No instance identifier
        if '.' in ref:
            model, field = ref.split('.', 1)
            return (model, None, field)
        else:
            # Just model name
            return (ref, None, None)

def extract_referenced_models(lineage: List[Dict[str, Any]]) -> Set[str]:
    """Extract all model names referenced in lineage definitions.

    Strips instance identifiers to get the base model names for CSV loading.

    Args:
        lineage: List of lineage entries with 'from' and 'to' fields

    Returns:
        Set of model names (top-level only, e.g., 'Parent' from 'Parent.Child.field')
    """
    models = set()

    for entry in lineage:
        # Extract from 'from' field (can be string or list)
        from_val = entry.get('from')
        if isinstance(from_val, str):
            from_list = [from_val]
        elif isinstance(from_val, list):
            from_list = from_val
        else:
            from_list = []

        for ref in from_list:
            model, instance, field = parse_reference(ref)
            if model:
                models.add(model)

        # Extract from 'to' field
        to_val = entry.get('to', '')
        if to_val:
            model, instance, field = parse_reference(to_val)
            if model:
                models.add(model)

    return models

def extract_model_instances(lineage: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
    """Extract all model instances referenced in lineage definitions.

    Args:
        lineage: List of lineage entries with 'from' and 'to' fields

    Returns:
        Dict mapping model names to sets of instance identifiers
        Example: {'Money': {'jpy', 'usd'}, 'Transaction': set()}
        Empty set means model is used without instance identifiers
    """
    from collections import defaultdict
    instances: Dict[str, Set[str]] = defaultdict(set)

    for entry in lineage:
        # Process 'from' field (can be string or list)
        from_val = entry.get('from')
        if isinstance(from_val, str):
            from_list = [from_val]
        elif isinstance(from_val, list):
            from_list = from_val
        else:
            from_list = []

        for ref in from_list:
            model, instance, field = parse_reference(ref)
            if model and instance:
                instances[model].add(instance)
            elif model and not instance:
                # Model without instance - mark with empty set
                if model not in instances:
                    instances[model] = set()

        # Process 'to' field
        to_val = entry.get('to', '')
        if to_val:
            model, instance, field = parse_reference(to_val)
            if model and instance:
                instances[model].add(instance)
            elif model and not instance:
                if model not in instances:
                    instances[model] = set()

    return dict(instances)

def extract_referenced_fields(lineage: List[Dict[str, Any]], yaml_models: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
    """Extract all fields referenced in lineage definitions.

    This function analyzes lineage entries to determine which fields are actually used.
    It handles:
    - Direct field references (e.g., 'Model.field', 'Model#instance.field')
    - Model-level references (e.g., 'Model', 'Model#instance' -> all fields in that model)
    - Nested model references (e.g., 'Parent.Child.field')

    For models with instances, fields are tracked per instance:
    - 'Money#jpy': {'amount', 'currency'}
    - 'Money#usd': {'amount'}

    Args:
        lineage: List of lineage entries with 'from' and 'to' fields
        yaml_models: List of model definitions from YAML (to identify model-level references)

    Returns:
        Dict mapping model paths (with optional instance) to sets of field names
        Example: {
            'HttpRequest': {'amount', 'user_id'},
            'Money#jpy': {'amount', 'currency'},
            'Money#usd': {'amount'}
        }
    """
    used_fields: Dict[str, Set[str]] = {}

    # Build a set of all defined model names (including nested ones) from YAML
    # to distinguish model references from field references
    def collect_model_names(models: List[Dict[str, Any]], prefix: str = "") -> Set[str]:
        """Recursively collect all model names including nested ones."""
        names = set()
        for m in models:
            model_path = f"{prefix}.{m['name']}" if prefix else m['name']
            names.add(model_path)
            if 'children' in m:
                names.update(collect_model_names(m['children'], model_path))
        return names

    known_models = collect_model_names(yaml_models)

    def add_field(ref: str, is_from: bool = True) -> None:
        """Add a field reference to the used_fields dictionary.

        Args:
            ref: Reference string (can be 'Model', 'Model#instance', 'Model.field', 'Model#instance.field')
            is_from: True if this is a 'from' reference, False if 'to'
        """
        model, instance, field = parse_reference(ref)

        # Build the tracking key (model path with optional instance)
        if instance:
            tracking_key = f"{model}#{instance}"
        else:
            tracking_key = model

        # Check if it's a model-level reference (no field specified)
        if field is None:
            # Model-level reference: mark all fields in this model/instance as used
            if tracking_key not in used_fields:
                used_fields[tracking_key] = set(['*'])  # '*' means all fields
            else:
                used_fields[tracking_key].add('*')
            return

        # It's a field reference
        if tracking_key not in used_fields:
            used_fields[tracking_key] = set()

        # Don't add field if we already marked all fields with '*'
        if '*' not in used_fields[tracking_key]:
            used_fields[tracking_key].add(field)

    # Process all lineage entries
    for entry in lineage:
        # Process 'from' field (can be string or list)
        from_val = entry.get('from')
        if isinstance(from_val, str):
            from_list = [from_val]
        elif isinstance(from_val, list):
            from_list = from_val
        else:
            from_list = []

        for ref in from_list:
            model, instance, field = parse_reference(ref)
            # Skip literal values (no model or field, and not in known models)
            if model and (field is not None or model in known_models or instance is not None):
                add_field(ref, is_from=True)

        # Process 'to' field
        to_val = entry.get('to', '')
        if to_val:
            model, instance, field = parse_reference(to_val)
            if model and (field is not None or model in known_models or instance is not None):
                add_field(to_val, is_from=False)

    return used_fields

def create_dynamic_models_from_lineage(
    lineage: List[Dict[str, Any]],
    existing_models: List[Dict[str, Any]],
    model_types: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Create dynamic model definitions for models referenced in lineage but not defined in models.

    This function enables users to define models with only name and type,
    then have their fields automatically generated from lineage references.

    Example:
        models:
          - name: EmptyModel
            type: program
            # props omitted

        lineage:
          - from: value
            to: EmptyModel.field1
          - from: another
            to: EmptyModel.Child.field2

        Result: EmptyModel will have field1, and a child model Child with field2

    Args:
        lineage: List of lineage entries
        existing_models: List of existing model definitions from YAML
        model_types: Dict of already registered model types (to detect defined models)

    Returns:
        List of new model definitions to be added (or updated existing models with props)
    """
    # Build a map of existing models for quick lookup
    existing_model_map: Dict[str, Dict[str, Any]] = {}

    def collect_existing_models(models: List[Dict[str, Any]], prefix: str = "") -> None:
        """Recursively collect existing models into a map."""
        for m in models:
            model_path = f"{prefix}.{m['name']}" if prefix else m['name']
            existing_model_map[model_path] = m
            if 'children' in m:
                collect_existing_models(m['children'], model_path)

    collect_existing_models(existing_models)

    # Track which models need dynamic field generation
    # Format: {model_path: {field_names_set}}
    dynamic_fields: Dict[str, Set[str]] = {}

    def extract_field_references(ref: str) -> None:
        """Extract field references from a lineage reference string.

        Handles:
        - 'Model.field' -> adds field to Model
        - 'Model.Child.field' -> adds field to Model.Child (and creates Child if needed)
        - 'Model#instance.field' -> adds field to Model
        - 'Model' or 'literal' -> skip (model-level reference or literal)
        """
        # Skip literals and model-level references
        if '.' not in ref:
            return

        # Check if root model exists in existing_model_map
        # This prevents literals like "v1.0" from being treated as model references
        root_model = ref.split('.')[0].split('#')[0]  # Extract root, remove instance if present
        if root_model not in existing_model_map:
            # Root model not defined → treat as literal, skip dynamic generation
            return

        # Handle instance notation: Model#instance.field -> Model.field
        if '#' in ref:
            # Remove instance part for model path extraction
            ref_without_instance = ref.replace('#', '.').replace('..', '.')
            parts = ref_without_instance.rsplit('.', 1)
            if len(parts) == 2:
                model_path_with_instance, field = parts
                # Remove instance identifier from model path
                model_path = model_path_with_instance.split('.')[0]

                # Find the actual field name (last part after the last dot in original ref)
                field = ref.split('.')[-1]
        else:
            # No instance: split normally
            parts = ref.rsplit('.', 1)
            if len(parts) != 2:
                return
            model_path, field = parts

        # Try to traverse the full model path to see if it exists
        check_parts = model_path.split('.')
        current_models = existing_models
        model_def = None

        for i, part in enumerate(check_parts):
            found = False
            for m in current_models:
                if m['name'] == part:
                    model_def = m
                    current_models = m.get('children', [])
                    found = True
                    break
            if not found:
                # This part of the path doesn't exist
                # Note: If root model doesn't exist, we already returned at line 546-548
                # So here, we know that a parent model exists but child doesn't
                # Add to dynamic_fields for child creation
                if model_path not in dynamic_fields:
                    dynamic_fields[model_path] = set()
                dynamic_fields[model_path].add(field)
                return

        # Full path exists, check if it has props
        if model_def is not None:
            if 'props' not in model_def or not model_def.get('props'):
                if model_path not in dynamic_fields:
                    dynamic_fields[model_path] = set()
                dynamic_fields[model_path].add(field)

    # Process all lineage entries
    for entry in lineage:
        # Process 'from' field (can be string or list)
        from_val = entry.get('from')
        if isinstance(from_val, str):
            from_list = [from_val]
        elif isinstance(from_val, list):
            from_list = from_val
        else:
            from_list = []

        for ref in from_list:
            extract_field_references(ref)

        # Process 'to' field
        to_val = entry.get('to', '')
        if to_val:
            extract_field_references(to_val)

    # Now update existing models with dynamic fields and create missing child models
    models_to_update = []

    for model_path, fields in dynamic_fields.items():
        # Navigate to the model definition and add props
        parts = model_path.split('.')
        current_models = existing_models
        model_def = None
        parent_def = None
        parent_type = 'program'  # Default type
        missing_part_index = -1

        for i, part in enumerate(parts):
            found = False
            for m in current_models:
                if m['name'] == part:
                    parent_def = model_def  # Remember parent before moving to child
                    if model_def:
                        parent_type = model_def.get('type', parent_type)
                    model_def = m
                    if i < len(parts) - 1:  # Not the last part, go deeper
                        if 'children' not in m:
                            m['children'] = []
                        current_models = m['children']
                    found = True
                    break
            if not found:
                # Model part not found, need to create it
                missing_part_index = i
                break

        if model_def is not None and missing_part_index < 0:
            # Full model path exists, update its props
            if 'props' not in model_def or not model_def.get('props'):
                # Print info message
                print(f"Info: モデル '{model_path}' はプロパティ未定義のため、lineage参照から動的生成します")
                model_def['props'] = sorted(list(fields))
        elif missing_part_index >= 0 or (model_def is not None and missing_part_index >= 0):
            # Need to create missing child models
            # Rebuild from where we left off
            current_models = existing_models
            model_def = None

            for i in range(missing_part_index):
                for m in current_models:
                    if m['name'] == parts[i]:
                        model_def = m
                        parent_type = m.get('type', parent_type)
                        if 'children' not in m:
                            m['children'] = []
                        current_models = m['children']
                        break

            # Now create the missing parts
            for i in range(missing_part_index, len(parts)):
                part = parts[i]
                # Determine the full path for this model
                created_path = '.'.join(parts[:i+1])

                # Create new child model with inherited type
                new_model = {
                    'name': part,
                    'type': parent_type,  # Inherit from parent
                    'props': sorted(list(fields)) if i == len(parts) - 1 else []
                }

                # Add to parent's children
                current_models.append(new_model)

                # Print info message
                print(f"Info: モデル '{created_path}' はプロパティ未定義のため、lineage参照から動的生成します")

                # Prepare for next iteration
                if i < len(parts) - 1:
                    new_model['children'] = []
                    current_models = new_model['children']

    # Return empty list as we modified existing_models in place
    return []

def find_openapi_models(
    spec_files: List[str],
    required_models: Set[str],
    default_type: str = 'program'
) -> Dict[str, Dict[str, Any]]:
    """Find and load model definitions from OpenAPI specification files.

    Args:
        spec_files: List of OpenAPI spec file paths
        required_models: Set of model names that are referenced in lineage
        default_type: Default model type ('program' or 'datastore')

    Returns:
        Dict mapping model names to model definitions {name, type, props}
    """
    models = {}

    for spec_path in spec_files:
        path = Path(spec_path)
        if not path.exists():
            print(f"Warning: OpenAPI spec file '{spec_path}' does not exist", file=sys.stderr)
            continue

        try:
            # Load spec file
            with open(path, 'r', encoding='utf-8') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    spec = yaml.safe_load(f)
                elif path.suffix.lower() == '.json':
                    spec = json.load(f)
                else:
                    print(f"Warning: Unsupported file format '{path.suffix}'", file=sys.stderr)
                    continue

            # Get all schemas
            if 'components' not in spec or 'schemas' not in spec['components']:
                continue

            schemas = spec['components']['schemas']

            # Load required models
            for model_name in required_models:
                if model_name in schemas and model_name not in models:
                    model_def = load_model_from_openapi(spec_path, model_name, default_type)
                    if model_def:
                        models[model_name] = model_def

        except Exception as e:
            print(f"Error processing OpenAPI spec '{spec_path}': {e}", file=sys.stderr)
            continue

    return models

def find_asyncapi_models(
    spec_files: List[str],
    required_models: Set[str],
    default_type: str = 'program'
) -> Dict[str, Dict[str, Any]]:
    """Find and load model definitions from AsyncAPI 3.0 specification files.

    Searches components/schemas for model definitions.

    Args:
        spec_files: List of AsyncAPI spec file paths
        required_models: Set of model names that are referenced in lineage
        default_type: Default model type ('program' or 'datastore')

    Returns:
        Dict mapping model names to model definitions {name, type, props}
    """
    models = {}

    for spec_path in spec_files:
        path = Path(spec_path)
        if not path.exists():
            print(f"Warning: AsyncAPI spec file '{spec_path}' does not exist", file=sys.stderr)
            continue

        try:
            # Load spec file
            with open(path, 'r', encoding='utf-8') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    spec = yaml.safe_load(f)
                elif path.suffix.lower() == '.json':
                    spec = json.load(f)
                else:
                    print(f"Warning: Unsupported file format '{path.suffix}'", file=sys.stderr)
                    continue

            # Get all schemas from components/schemas (AsyncAPI 3.0)
            if 'components' not in spec or 'schemas' not in spec['components']:
                continue

            schemas = spec['components']['schemas']

            # Load required models
            for model_name in required_models:
                if model_name in schemas and model_name not in models:
                    model_def = load_model_from_asyncapi(spec_path, model_name, default_type)
                    if model_def:
                        models[model_name] = model_def

        except Exception as e:
            print(f"Error processing AsyncAPI spec '{spec_path}': {e}", file=sys.stderr)
            continue

    return models

def find_model_csvs(
    program_dirs: List[str],
    datastore_dirs: List[str],
    required_models: Set[str]
) -> Dict[str, Dict[str, Any]]:
    """Find and load CSV model definitions from specified directories.

    Args:
        program_dirs: List of directories containing program model CSVs
        datastore_dirs: List of directories containing datastore model CSVs
        required_models: Set of model names that are referenced in lineage

    Returns:
        Dict mapping model names to model definitions {name, type, props}
    """
    models = {}

    # Search program model directories
    for dir_path in program_dirs:
        path = Path(dir_path)
        if not path.exists():
            print(f"Warning: Program model directory '{dir_path}' does not exist", file=sys.stderr)
            continue

        for csv_file in path.rglob("*.csv"):
            model_def = load_model_from_csv(str(csv_file), 'program')
            if model_def and model_def['name'] in required_models:
                if model_def['name'] in models:
                    print(f"Warning: Duplicate model '{model_def['name']}' found in '{csv_file}'", file=sys.stderr)
                else:
                    models[model_def['name']] = model_def

    # Search datastore model directories
    for dir_path in datastore_dirs:
        path = Path(dir_path)
        if not path.exists():
            print(f"Warning: Datastore model directory '{dir_path}' does not exist", file=sys.stderr)
            continue

        for csv_file in path.rglob("*.csv"):
            model_def = load_model_from_csv(str(csv_file), 'datastore')
            if model_def and model_def['name'] in required_models:
                if model_def['name'] in models:
                    print(f"Warning: Duplicate model '{model_def['name']}' found in '{csv_file}'", file=sys.stderr)
                else:
                    models[model_def['name']] = model_def

    return models

def parse_field(ref: str) -> Tuple[str, str]:
    """Parse field reference into model path and field name.

    Args:
        ref: Field reference in format 'Model.field' or 'Model.Child.field'

    Returns:
        Tuple of (model_path, field_name)
    """
    if "." not in ref:
        raise ValueError(f"Field reference must be 'Model.field' or 'Model.Child.field': {ref}")
    parts = ref.split(".")
    field = parts[-1]
    model_path = ".".join(parts[:-1])
    return model_path, field

def parse_models_recursive(
    models: List[Dict[str, Any]],
    parent_prefix: str = "",
    model_types: Optional[Dict[str, str]] = None,
    field_nodes_by_model: Optional[Dict[str, List[Tuple[str, str]]]] = None,
    field_node_ids: Optional[Dict[str, str]] = None,
    model_hierarchy: Optional[Dict[str, Dict[str, Any]]] = None,
    used_fields: Optional[Dict[str, Set[str]]] = None,
    csv_model_names: Optional[Set[str]] = None,
    model_instances: Optional[Dict[str, Set[str]]] = None,
    parent_instance: str = ""
) -> Tuple[Dict[str, str], Dict[str, List[Tuple[str, str]]], Dict[str, str], Dict[str, Dict[str, Any]]]:
    """Recursively parse models and their children to build model hierarchy.

    Supports model instances via '#' notation (e.g., 'Money#jpy', 'Money#usd').

    Args:
        models: List of model definitions
        parent_prefix: Parent model path (for nested models)
        model_types: Dict mapping model paths (with instance) to their types
        field_nodes_by_model: Dict mapping model paths (with instance) to field nodes
        field_node_ids: Dict mapping field references (with instance) to node IDs
        model_hierarchy: Dict storing parent-child relationships
        used_fields: Dict mapping model paths (with instance) to sets of actually used field names
        csv_model_names: Set of model names loaded from CSV (only these will be filtered)
        model_instances: Dict mapping model names to sets of instance identifiers
        parent_instance: Instance identifier from parent model

    Returns:
        Tuple of (model_types, field_nodes_by_model, field_node_ids, model_hierarchy)
    """
    if model_types is None:
        model_types = {}
    if field_nodes_by_model is None:
        field_nodes_by_model = {}
    if field_node_ids is None:
        field_node_ids = {}
    if model_hierarchy is None:
        model_hierarchy = {}
    if model_instances is None:
        model_instances = {}

    for m in models:
        name = m["name"]
        mtype = m.get("type", "datastore")
        props = m.get("props", [])
        children = m.get("children", [])

        # Build full model path (without instance)
        full_model_path = f"{parent_prefix}.{name}" if parent_prefix else name

        # Get instances for this model (empty set means no instances)
        instances = model_instances.get(name, set())

        # If this model has no instances, treat it as a single default instance
        if not instances:
            instances = {None}

        # Sort instances alphabetically for deterministic output (None sorts first)
        sorted_instances = sorted(instances, key=lambda x: (x is not None, x or ''))

        # Process each instance of this model
        for instance in sorted_instances:
            # Build instance-specific paths
            if instance:
                instance_path = f"{full_model_path}#{instance}"
                instance_id_part = f"_{instance}"
            else:
                instance_path = full_model_path
                instance_id_part = ""

            model_types[instance_path] = mtype

            # Store hierarchy info
            model_hierarchy[instance_path] = {
                'parent': parent_prefix if parent_prefix else None,
                'children': [f"{full_model_path}.{c['name']}" for c in children] if children else [],
                'instance': instance
            }

            # Determine if we should filter fields for this model instance
            should_filter = (
                used_fields is not None and
                csv_model_names is not None and
                name in csv_model_names and
                instance_path in used_fields
            )

            # Parse fields
            nodes = []
            for p in props:
                # Apply filtering if applicable
                if should_filter:
                    # Check if this field is actually used
                    model_used_fields = used_fields.get(instance_path, set())
                    # '*' means all fields, otherwise check if field is in the set
                    if '*' not in model_used_fields and p not in model_used_fields:
                        # Skip this field as it's not used in lineage
                        continue

                # Generate node ID with instance
                nid = slug(f"{full_model_path}{instance_id_part}_{p}".replace(".", "_"))
                nodes.append((nid, str(p)))

                # Map field reference to node ID
                if instance:
                    field_ref = f"{full_model_path}#{instance}.{p}"
                else:
                    field_ref = f"{full_model_path}.{p}"
                field_node_ids[field_ref] = nid

            field_nodes_by_model[instance_path] = nodes

        # Recursively parse children (children inherit parent's instance if any)
        if children:
            parse_models_recursive(
                children, full_model_path, model_types, field_nodes_by_model,
                field_node_ids, model_hierarchy, used_fields, csv_model_names,
                model_instances, parent_instance
            )

    return model_types, field_nodes_by_model, field_node_ids, model_hierarchy

def generate_subgraph(
    model_path: str,
    model_types: Dict[str, str],
    field_nodes_by_model: Dict[str, List[Tuple[str, str]]],
    model_hierarchy: Dict[str, Dict[str, Any]],
    indent: int = 2
) -> List[str]:
    """Generate Mermaid subgraph with proper nesting.

    Supports instance identifiers in model_path (e.g., 'Money#jpy').

    Args:
        model_path: Full path of the model (may include instance like 'Money#jpy')
        model_types: Dict mapping model paths to their types
        field_nodes_by_model: Dict mapping model paths to field nodes
        model_hierarchy: Dict storing parent-child relationships
        indent: Indentation level for formatting

    Returns:
        List of Mermaid diagram lines
    """
    lines = []
    spaces = "  " * indent
    mtype = model_types.get(model_path, 'datastore')

    # Extract base model name and instance from model_path
    if '#' in model_path:
        base_path, instance = model_path.rsplit('#', 1)
        model_display_name = base_path.split(".")[-1]
        display_label = f'"{model_display_name} ({instance})"'
    else:
        model_display_name = model_path.split(".")[-1]
        display_label = model_display_name

    # Generate subgraph header
    subgraph_id = slug(model_path.replace(".", "_").replace("#", "_"))
    lines.append(f"{spaces}subgraph {subgraph_id}[{display_label}]")

    # Add fields for this model
    nodes = field_nodes_by_model.get(model_path, [])
    for nid, label in nodes:
        lines.append(f'{spaces}  {nid}["{label}"]:::property')

    # Add nested children
    children = model_hierarchy.get(model_path, {}).get('children', [])
    if children:
        if nodes:
            lines.append("")  # Add spacing between fields and children
        for child in children:
            child_lines = generate_subgraph(child, model_types, field_nodes_by_model, model_hierarchy, indent + 1)
            lines.extend(child_lines)

    lines.append(f"{spaces}end")
    lines.append(f"{spaces}class {subgraph_id} {mtype}_bg")

    return lines

def main(
    input_yaml: str,
    output_md: str,
    program_model_dirs: Optional[List[str]] = None,
    datastore_model_dirs: Optional[List[str]] = None,
    openapi_specs: Optional[List[str]] = None,
    asyncapi_specs: Optional[List[str]] = None,
    show_all_props: bool = False
) -> None:
    """Convert YAML lineage definition to Mermaid Markdown diagram.

    Args:
        input_yaml: Path to input YAML file
        output_md: Path to output Markdown file
        program_model_dirs: List of directories containing program model CSVs
        datastore_model_dirs: List of directories containing datastore model CSVs
        openapi_specs: List of OpenAPI specification files
        asyncapi_specs: List of AsyncAPI specification files
        show_all_props: If True, show all properties; if False, show only used fields for CSV models
    """
    data = yaml.safe_load(Path(input_yaml).read_text(encoding="utf-8"))

    yaml_models = data.get("models", [])
    lineage = data.get("lineage", [])

    # Extract model names already defined in YAML
    yaml_model_names = set()
    for m in yaml_models:
        yaml_model_names.add(m['name'])

    # Extract all referenced models from lineage
    referenced_models = extract_referenced_models(lineage)

    # Find models that need to be loaded from external sources
    missing_models = referenced_models - yaml_model_names

    # Merge YAML models with external models if sources are specified
    models = list(yaml_models)  # Start with YAML-defined models
    csv_model_names = set()  # Track which models came from CSV
    external_model_names = set()  # Track models from OpenAPI/AsyncAPI

    if missing_models:
        # Priority order: OpenAPI -> AsyncAPI -> CSV
        # This ensures that API specs take precedence over CSV files

        # 1. Load from OpenAPI specs (program type by default)
        if openapi_specs:
            openapi_models = find_openapi_models(
                openapi_specs or [],
                missing_models,
                default_type='program'
            )
            external_model_names.update(openapi_models.keys())
            models.extend(openapi_models.values())
            missing_models -= set(openapi_models.keys())

        # 2. Load from AsyncAPI specs (program type by default)
        if asyncapi_specs:
            asyncapi_models = find_asyncapi_models(
                asyncapi_specs or [],
                missing_models,
                default_type='program'
            )
            external_model_names.update(asyncapi_models.keys())
            models.extend(asyncapi_models.values())
            missing_models -= set(asyncapi_models.keys())

        # 3. Load from CSV directories (last resort)
        if program_model_dirs or datastore_model_dirs:
            csv_models = find_model_csvs(
                program_model_dirs or [],
                datastore_model_dirs or [],
                missing_models
            )

            # Track CSV model names
            csv_model_names = set(csv_models.keys())

            # Add CSV models to the list
            models.extend(csv_models.values())
            missing_models -= csv_model_names

        # Warn about models that couldn't be found (likely literals)
        if missing_models:
            print(f"Info: The following values will be treated as literals (not found as models): {', '.join(sorted(missing_models))}", file=sys.stderr)

    # Extract model instances from lineage
    model_instances = extract_model_instances(lineage)

    # Create dynamic fields for models without props
    # This must be done before parse_models_recursive so the fields are available
    # Build initial model_types for dynamic field generation
    temp_model_types = {}
    def build_model_types(model_list: List[Dict[str, Any]], prefix: str = "") -> None:
        for m in model_list:
            model_path = f"{prefix}.{m['name']}" if prefix else m['name']
            temp_model_types[model_path] = m.get('type', 'datastore')
            if 'children' in m:
                build_model_types(m['children'], model_path)
    build_model_types(models)

    # Generate dynamic fields from lineage references
    create_dynamic_models_from_lineage(lineage, models, temp_model_types)

    # Extract used fields from lineage (for filtering CSV models)
    used_fields = None
    if not show_all_props and csv_model_names:
        # We need to pass all models (including CSV-loaded ones) to correctly identify model references
        # Also need to add CSV model names to the known models list
        all_models_for_ref_extraction = list(models)
        used_fields = extract_referenced_fields(lineage, all_models_for_ref_extraction)

    # Use recursive parser to handle nested models
    model_types, field_nodes_by_model, field_node_ids, model_hierarchy = parse_models_recursive(
        models,
        used_fields=used_fields,
        csv_model_names=csv_model_names,
        model_instances=model_instances
    )

    lines = [
        "```mermaid",
        "graph LR",
        "  classDef program_bg fill:#E3F2FD,stroke:#1565C0,stroke-width:2px;",
        "  classDef datastore_bg fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px;",
        "  classDef property fill:#F5F5F5,stroke:#9E9E9E,stroke-width:1px,color:#424242;",
        "  classDef literal fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px,color:#BF360C;",
        ""
    ]

    # Generate subgraphs only for root-level models (those without parents)
    # Sort model paths for deterministic output order
    for model_path in sorted(model_hierarchy.keys()):
        if model_hierarchy[model_path]['parent'] is None:
            subgraph_lines = generate_subgraph(model_path, model_types, field_nodes_by_model, model_hierarchy)
            lines.extend(subgraph_lines)
            lines.append("")

    literal_counter = 0
    def ensure_literal(label: str) -> str:
        """Create a unique literal node for each lineage entry with same label."""
        nonlocal literal_counter
        literal_counter += 1
        nid = slug(f"lit_{literal_counter}")  # ノードIDは連番で一意に
        lines.append(f'  {nid}["{label}"]:::literal')  # ラベルは元のテキスト
        return nid

    def is_model_field(token: str) -> bool:
        """Check if token is a field reference (may include instance like 'Model#instance.field')"""
        return token in field_node_ids

    def is_model_reference(token: str) -> bool:
        """Check if token is a model reference (may include instance like 'Model#instance')"""
        # Check if it's a known model path (including instance)
        return token in model_types

    # Track which model references need style overrides
    model_ref_styles = {}

    for e in lineage:
        to_ref = e.get("to")
        if not to_ref: continue

        # Determine target: field reference or model reference
        # Check field reference first (most specific)
        if is_model_field(to_ref):
            # Direct field reference
            t_id = field_node_ids[to_ref]
        elif is_model_reference(to_ref):
            # Model reference: use subgraph ID
            t_id = slug(to_ref.replace(".", "_").replace("#", "_"))
            # Track this model reference for style override
            if to_ref not in model_ref_styles:
                model_ref_styles[to_ref] = model_types[to_ref]
        else:
            print(f"Warning: Unknown reference '{to_ref}' in lineage", file=sys.stderr)
            continue

        srcs = e.get("from")
        if isinstance(srcs, str): srcs = [srcs]
        transform = e.get("transform", "")

        for i, src in enumerate(srcs):
            # Determine source: model reference, field reference, or literal
            # Check model reference first (before field) to handle nested models correctly
            if is_model_reference(src):
                # Model reference: use subgraph ID as node (creates implicit node)
                s_id = slug(src.replace(".", "_").replace("#", "_"))
                # Track this model reference for style override
                if src not in model_ref_styles:
                    model_ref_styles[src] = model_types[src]
            elif is_model_field(src):
                s_id = field_node_ids[src]
            else:
                # Literal value
                s_id = ensure_literal(src)

            label = transform if i == 0 and transform else ""
            if label:
                lines.append(f'  {s_id} -->|"{label}"| {t_id}')
            else:
                lines.append(f'  {s_id} --> {t_id}')

    # Add style directives for model references to fix color issue
    if model_ref_styles:
        lines.append("")
        for model_ref, model_type in model_ref_styles.items():
            node_id = slug(model_ref.replace(".", "_").replace("#", "_"))
            if model_type == "program":
                lines.append(f'  style {node_id} fill:#E3F2FD,stroke:#1565C0,stroke-width:2px')
            else:  # datastore
                lines.append(f'  style {node_id} fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px')

    lines.append("```")
    Path(output_md).write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert YAML lineage definition to Mermaid Markdown diagram",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full YAML mode (traditional)
  python lineage_to_md.py data/sample.yml output.md

  # CSV mode
  python lineage_to_md.py lineage.yml output.md \\
    --program-model-dirs data/レイアウト \\
    --datastore-model-dirs data/テーブル定義

  # OpenAPI mode
  python lineage_to_md.py lineage.yml output.md \\
    --openapi-specs data/openapi/user-api.yaml

  # AsyncAPI mode
  python lineage_to_md.py lineage.yml output.md \\
    --asyncapi-specs data/asyncapi/events.yaml

  # Mixed mode (YAML + CSV + OpenAPI + AsyncAPI)
  python lineage_to_md.py lineage.yml output.md \\
    --program-model-dirs data/レイアウト \\
    --openapi-specs data/openapi/api.yaml \\
    --asyncapi-specs data/asyncapi/events.yaml
"""
    )

    parser.add_argument("input_yaml", help="Path to input YAML file")
    parser.add_argument("output_md", help="Path to output Markdown file")
    parser.add_argument(
        "--program-model-dirs", "-p",
        action="append",
        dest="program_model_dirs",
        help="Directory containing program model CSV files (can be specified multiple times)"
    )
    parser.add_argument(
        "--datastore-model-dirs", "-d",
        action="append",
        dest="datastore_model_dirs",
        help="Directory containing datastore model CSV files (can be specified multiple times)"
    )
    parser.add_argument(
        "--openapi-specs", "-o",
        action="append",
        dest="openapi_specs",
        help="OpenAPI specification file (YAML/JSON) (can be specified multiple times)"
    )
    parser.add_argument(
        "--asyncapi-specs", "-a",
        action="append",
        dest="asyncapi_specs",
        help="AsyncAPI specification file (YAML/JSON) (can be specified multiple times)"
    )
    parser.add_argument(
        "--show-all-props",
        action="store_true",
        help="Show all properties from CSV models (default: show only fields used in lineage)"
    )

    args = parser.parse_args()

    main(
        args.input_yaml,
        args.output_md,
        program_model_dirs=args.program_model_dirs or [],
        datastore_model_dirs=args.datastore_model_dirs or [],
        openapi_specs=args.openapi_specs or [],
        asyncapi_specs=args.asyncapi_specs or [],
        show_all_props=args.show_all_props
    )