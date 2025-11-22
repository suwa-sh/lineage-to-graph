from __future__ import annotations
import sys
import yaml
import re
import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field

# ============================================
# Domain Layer
# ============================================

# エンティティ・値オブジェクト

@dataclass
class ModelDefinition:
    """モデル定義のエンティティ"""
    name: str
    type: str
    props: List[str] = field(default_factory=list)
    children: List[ModelDefinition] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """自身を辞書に変換（シリアライズ）

        Returns:
            辞書形式のモデル定義
        """
        result = {
            'name': self.name,
            'type': self.type,
            'props': self.props
        }
        if self.children:
            result['children'] = [c.to_dict() for c in self.children]
        return result

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> ModelDefinition:
        """辞書から生成（デシリアライズ）

        Args:
            data: 辞書形式のモデル定義

        Returns:
            ModelDefinitionオブジェクト
        """
        children_data = data.get('children', [])
        children = [ModelDefinition.from_dict(c) for c in children_data]
        return ModelDefinition(
            name=data['name'],
            type=data.get('type', 'datastore'),
            props=data.get('props', []),
            children=children
        )


@dataclass
class LineageEntry:
    """リネージエントリのエンティティ"""
    from_refs: List[str]
    to_ref: str
    transform: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """自身を辞書に変換（シリアライズ）

        Returns:
            辞書形式のリネージエントリ
        """
        result = {
            'from': self.from_refs,
            'to': self.to_ref
        }
        if self.transform:
            result['transform'] = self.transform
        return result

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> LineageEntry:
        """辞書からLineageEntryを生成（デシリアライズ）

        Args:
            data: 辞書形式のリネージエントリ

        Returns:
            LineageEntryオブジェクト
        """
        from_val = data.get('from', [])
        if isinstance(from_val, str):
            from_val = [from_val]
        return LineageEntry(
            from_refs=from_val,
            to_ref=data.get('to', ''),
            transform=data.get('transform')
        )


class FieldReference:
    """フィールド参照の値オブジェクト"""

    def __init__(self, ref: str):
        self.ref = ref
        self.model, self.instance, self.field = self.parse(ref)

    @staticmethod
    def parse(ref: str) -> Tuple[str, Optional[str], Optional[str]]:
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

    @staticmethod
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

    def __str__(self) -> str:
        return self.ref


class ModelPath:
    """モデルパス（階層・インスタンス含む）の値オブジェクト"""

    def __init__(self, path: str):
        self.full_path = path
        self.base_path, self.instance = self._split_instance(path)

    @staticmethod
    def _split_instance(path: str) -> Tuple[str, Optional[str]]:
        """モデルパスからインスタンスを分離"""
        if '#' in path:
            base, instance = path.rsplit('#', 1)
            return base, instance
        return path, None

    def __str__(self) -> str:
        return self.full_path


class MermaidNode:
    """Mermaidノードの値オブジェクト"""

    def __init__(self, node_id: str, label: str, style_class: str):
        self.node_id = node_id
        self.label = label
        self.style_class = style_class

    def to_mermaid_line(self) -> str:
        """Mermaid行を生成"""
        return f'{self.node_id}["{self.label}"]:::{self.style_class}'

    @staticmethod
    def sanitize_id(s: str) -> str:
        """Generate safe Mermaid identifier from string.

        Supports Japanese characters by preserving them in the identifier.
        Only replaces symbols and whitespace with underscores.

        Args:
            s: 元の文字列

        Returns:
            Mermaid識別子として安全な文字列
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


# ファーストクラスコレクション

@dataclass(frozen=True)
class Models:
    """ModelDefinitionのコレクション（Immutable）"""
    _models: List[ModelDefinition] = field(default_factory=list)

    def find_by_name(self, name: str) -> Optional[ModelDefinition]:
        for model in self._models:
            if model.name == name:
                return model
        return None

    def get_names(self) -> Set[str]:
        return {m.name for m in self._models}

    def to_list(self) -> List[ModelDefinition]:
        return list(self._models)  # 防御的コピー

    def __iter__(self):
        return iter(self._models)

    @classmethod
    def merge(cls, models_list: List['Models']) -> 'Models':
        """複数のModelsを結合して新しいModelsを返す

        Args:
            models_list: 結合するModelsのリスト

        Returns:
            新しいModelsインスタンス
        """
        all_models: List[ModelDefinition] = []
        for models in models_list:
            all_models.extend(models.to_list())
        return Models(all_models)

    def with_dynamic_fields(self, lineage: 'LineageEntries') -> 'Models':
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
            lineage: LineageEntries コレクション

        Returns:
            新しいModelsインスタンス（動的フィールドが追加されたもの）
        """
        # Convert to dict for processing
        existing_models = [m.to_dict() for m in self._models]
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
                    # Note: If root model doesn't exist, we already returned earlier
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
            # Process 'from' field (LineageEntry.from_refs is already a list)
            for ref in entry.from_refs:
                extract_field_references(ref)

            # Process 'to' field
            if entry.to_ref:
                extract_field_references(entry.to_ref)

        # Now update existing models with dynamic fields and create missing child models
        for model_path, fields in dynamic_fields.items():
            # Navigate to the model definition and add props
            parts = model_path.split('.')
            current_models = existing_models
            model_def = None
            parent_type = 'program'  # Default type
            missing_part_index = -1

            for i, part in enumerate(parts):
                found = False
                for m in current_models:
                    if m['name'] == part:
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

        # Convert modified dicts back to ModelDefinition objects
        updated_models = [ModelDefinition.from_dict(m) for m in existing_models]

        # Return new Models instance with updated models
        return Models(updated_models)

    def parse_to_structured_data(
        self,
        parent_prefix: str = "",
        used_fields: Optional['UsedFields'] = None,
        csv_model_names: Set[str] = set(),
        model_instances: Optional['ModelInstances'] = None,
        parent_instance: str = "",
        parsed_data: Optional['ParsedModelsData'] = None
    ) -> 'ParsedModelsData':
        """Recursively parse models and their children to build model hierarchy.

        Supports model instances via '#' notation (e.g., 'Money#jpy', 'Money#usd').

        Args:
            parent_prefix: Parent model path (for nested models)
            used_fields: 使用されているフィールド（フィルタリング用）
            csv_model_names: Set of model names loaded from CSV (only these will be filtered)
            model_instances: モデルインスタンスの情報
            parent_instance: Instance identifier from parent model
            parsed_data: 既存のParsedModelsData（再帰呼び出し用）

        Returns:
            ParsedModelsData
        """
        if parsed_data is None:
            parsed_data = ParsedModelsData(
                model_types={},
                field_nodes_by_model={},
                field_node_ids={},
                model_hierarchy={}
            )

        # Convert UsedFields to dict for easier access (if provided)
        used_fields_dict = used_fields.to_dict() if used_fields else None
        model_instances_dict = model_instances.to_dict() if model_instances else {}

        for m in self._models:
            name = m.name
            mtype = m.type
            props = m.props
            children = m.children

            # Build full model path (without instance)
            full_model_path = f"{parent_prefix}.{name}" if parent_prefix else name

            # Get instances for this model (empty set means no instances)
            instances = model_instances_dict.get(name, set())

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

                parsed_data.model_types[instance_path] = mtype

                # Store hierarchy info
                parsed_data.model_hierarchy[instance_path] = {
                    'parent': parent_prefix if parent_prefix else None,
                    'children': [f"{full_model_path}.{c.name}" for c in children] if children else [],
                    'instance': instance
                }

                # Determine if we should filter fields for this model instance
                should_filter = (
                    used_fields_dict is not None and
                    csv_model_names and
                    name in csv_model_names and
                    instance_path in used_fields_dict
                )

                # Parse fields
                nodes = []
                for p in props:
                    # Apply filtering if applicable
                    if should_filter:
                        # Check if this field is actually used
                        model_used_fields = used_fields_dict.get(instance_path, set())
                        # '*' means all fields, otherwise check if field is in the set
                        if '*' not in model_used_fields and p not in model_used_fields:
                            # Skip this field as it's not used in lineage
                            continue

                    # Generate node ID with instance
                    nid = MermaidNode.sanitize_id(f"{full_model_path}{instance_id_part}_{p}".replace(".", "_"))
                    nodes.append((nid, str(p)))

                    # Map field reference to node ID
                    if instance:
                        field_ref = f"{full_model_path}#{instance}.{p}"
                    else:
                        field_ref = f"{full_model_path}.{p}"
                    parsed_data.field_node_ids[field_ref] = nid

                parsed_data.field_nodes_by_model[instance_path] = nodes

            # Recursively parse children (children inherit parent's instance if any)
            if children:
                Models(children).parse_to_structured_data(
                    full_model_path, used_fields, csv_model_names,
                    model_instances, parent_instance, parsed_data
                )

        return parsed_data


@dataclass(frozen=True)
class LineageEntries:
    """LineageEntryのコレクション（Immutable）"""
    _entries: List[LineageEntry] = field(default_factory=list)

    def to_list(self) -> List[LineageEntry]:
        return list(self._entries)  # 防御的コピー

    def __iter__(self):
        return iter(self._entries)

    @staticmethod
    def from_dicts(data: List[Dict[str, Any]]) -> LineageEntries:
        """辞書リストからLineageEntriesを生成"""
        entries = [LineageEntry.from_dict(d) for d in data]
        return LineageEntries(entries)

    def extract_referenced_fields(self, yaml_models: Models) -> 'UsedFields':
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
            yaml_models: Models コレクション (to identify model-level references)

        Returns:
            UsedFields オブジェクト
            Example: {
                'HttpRequest': {'amount', 'user_id'},
                'Money#jpy': {'amount', 'currency'},
                'Money#usd': {'amount'}
            }
        """
        # Immutable化: Dict[str, Set[str]]を構築してからUsedFieldsを生成
        fields_dict: Dict[str, Set[str]] = {}

        # Build a set of all defined model names (including nested ones) from YAML
        # to distinguish model references from field references
        def collect_model_names(models: List[ModelDefinition], prefix: str = "") -> Set[str]:
            """Recursively collect all model names including nested ones."""
            names = set()
            for m in models:
                model_path = f"{prefix}.{m.name}" if prefix else m.name
                names.add(model_path)
                if m.children:
                    names.update(collect_model_names(m.children, model_path))
            return names

        known_models = collect_model_names(yaml_models.to_list())

        def add_field(ref: str) -> None:
            """Add a field reference to the fields_dict.

            Args:
                ref: Reference string (can be 'Model', 'Model#instance', 'Model.field', 'Model#instance.field')
            """
            # Use FieldReference to parse
            field_ref = FieldReference(ref)
            model = field_ref.model
            instance = field_ref.instance
            field = field_ref.field

            # Build the tracking key (model path with optional instance)
            if instance:
                tracking_key = f"{model}#{instance}"
            else:
                tracking_key = model

            # Check if it's a model-level reference (no field specified)
            if field is None:
                # Model-level reference: mark all fields in this model/instance as used
                fields_dict[tracking_key] = {'*'}
                return

            # It's a field reference - add to fields_dict
            if tracking_key not in fields_dict:
                fields_dict[tracking_key] = set()
            # '*'がすでにある場合は追加しない
            if '*' not in fields_dict[tracking_key]:
                fields_dict[tracking_key].add(field)

        # Process all lineage entries
        for entry in self._entries:
            # Process 'from' field (already normalized as List[str] in LineageEntry)
            for ref in entry.from_refs:
                field_ref = FieldReference(ref)
                model = field_ref.model
                instance = field_ref.instance
                field = field_ref.field
                # Skip literal values (no model or field, and not in known models)
                if model and (field is not None or model in known_models or instance is not None):
                    add_field(ref)

            # Process 'to' field
            if entry.to_ref:
                field_ref = FieldReference(entry.to_ref)
                model = field_ref.model
                instance = field_ref.instance
                field = field_ref.field
                if model and (field is not None or model in known_models or instance is not None):
                    add_field(entry.to_ref)

        return UsedFields(fields_dict)


@dataclass(frozen=True)
class ReferencedModels:
    """参照されているモデル名の集合（Immutable）"""
    _names: Set[str] = field(default_factory=set)

    def contains(self, name: str) -> bool:
        return name in self._names

    def difference(self, other: ReferencedModels) -> ReferencedModels:
        return ReferencedModels(self._names - other._names)

    def to_set(self) -> Set[str]:
        return set(self._names)  # 防御的コピー

    def __iter__(self):
        return iter(self._names)


@dataclass(frozen=True)
class ModelInstances:
    """モデルインスタンスのマップ {model_name: {instance_ids}}（Immutable）"""
    _instances: Dict[str, Set[str]] = field(default_factory=dict)

    def get_instances(self, model: str) -> Set[str]:
        return set(self._instances.get(model, set()))  # 防御的コピー

    def to_dict(self) -> Dict[str, Set[str]]:
        # 防御的コピー: 辞書とSet両方をコピー
        return {k: set(v) for k, v in self._instances.items()}


@dataclass(frozen=True)
class UsedFields:
    """使用されているフィールドのマップ {model_path: {field_names}}（Immutable）"""
    _fields: Dict[str, Set[str]] = field(default_factory=dict)

    def get_fields(self, model_path: str) -> Set[str]:
        return set(self._fields.get(model_path, set()))  # 防御的コピー

    def contains(self, model_path: str) -> bool:
        return model_path in self._fields

    def to_dict(self) -> Dict[str, Set[str]]:
        # 防御的コピー: 辞書とSet両方をコピー
        return {k: set(v) for k, v in self._fields.items()}


# ============================================================================
# Utility Layer - Conversion Helpers (Backward Compatibility Wrappers)
# ============================================================================
# これらの関数はドメインメソッドを呼び出すラッパーです。
# 将来的にはこれらを削除し、ドメインメソッドを直接使用します。

# ============================================================================
# Legacy Functions (to be refactored in Phase 2)
# ============================================================================

# ============================================
# Adapter Layer
# ============================================

class CSVAdapter:
    """CSV形式のモデル定義を読み込むアダプター"""

    def load_model(self, csv_path: str, model_type: str) -> Optional[ModelDefinition]:
        """CSVファイルから単一モデルをロード

        CSV format:
            論理名,物理名,データ型,サイズ,キー,説明
            (Header row is skipped, we extract from '物理名' column)

        Filename format:
            論理名__ModelName.csv
            └─────┘  └───┬───┘
            logical   physical name (used as model name)

        Args:
            csv_path: CSVファイルパス
            model_type: 'program' or 'datastore'

        Returns:
            ModelDefinitionまたはNone
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

            return ModelDefinition(
                name=model_name,
                type=model_type,
                props=props
            )

        except Exception as e:
            print(f"Error loading CSV '{csv_path}': {e}", file=sys.stderr)
            return None


class OpenAPIAdapter:
    """OpenAPI仕様からモデル定義を読み込むアダプター"""

    def load_model(self, spec_path: str, schema_name: str, model_type: str) -> Optional[ModelDefinition]:
        """OpenAPI仕様から単一モデルをロード

        Supports OpenAPI 3.0.x and 3.1.x in YAML or JSON format.
        Extracts properties from components/schemas/<schema_name>.

        Args:
            spec_path: OpenAPI仕様ファイルパス (.yaml, .yml, .json)
            schema_name: スキーマ名 (components/schemas内)
            model_type: 'program' or 'datastore'

        Returns:
            ModelDefinitionまたはNone
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

            # Remove duplicates while preserving order
            props = list(dict.fromkeys(props))

            return ModelDefinition(
                name=schema_name,
                type=model_type,
                props=props
            )

        except Exception as e:
            print(f"Error loading OpenAPI spec '{spec_path}': {e}", file=sys.stderr)
            return None


class AsyncAPIAdapter:
    """AsyncAPI仕様からモデル定義を読み込むアダプター"""

    def load_model(self, spec_path: str, schema_name: str, model_type: str) -> Optional[ModelDefinition]:
        """AsyncAPI仕様から単一モデルをロード

        Supports AsyncAPI 3.x in YAML or JSON format.
        Extracts properties from components/schemas/<schema_name>.
        Supports $ref resolution for nested schema references.

        Args:
            spec_path: AsyncAPI仕様ファイルパス (.yaml, .yml, .json)
            schema_name: スキーマ名 (components/schemas内)
            model_type: 'program' or 'datastore'

        Returns:
            ModelDefinitionまたはNone
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
                            nested_props = resolve_ref(prop_def['$ref'], visited)
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
                            props.extend(resolve_ref(item['$ref'], visited))

                if not props:
                    print(f"Info: Referenced schema '{ref_schema_name}' has no properties", file=sys.stderr)

                # Remove duplicates while preserving order
                return list(dict.fromkeys(props))

            # Extract properties
            props = []
            # Initialize visited set with current schema to detect circular references
            current_schema_ref = f"#/components/schemas/{schema_name}"
            visited = {current_schema_ref}

            if 'properties' in schema:
                for prop_name, prop_def in schema['properties'].items():
                    if isinstance(prop_def, dict) and '$ref' in prop_def:
                        # Handle $ref in properties
                        nested_props = resolve_ref(prop_def['$ref'], visited)
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
                        props.extend(resolve_ref(item['$ref'], visited))

            if not props:
                print(f"Warning: No properties found in schema '{schema_name}' in '{spec_path}'", file=sys.stderr)
                return None

            # Remove duplicates while preserving order
            props = list(dict.fromkeys(props))

            return ModelDefinition(
                name=schema_name,
                type=model_type,
                props=props
            )

        except Exception as e:
            print(f"Error loading AsyncAPI spec '{spec_path}': {e}", file=sys.stderr)
            return None


class YAMLAdapter:
    """YAMLファイルからリネージ定義を読み込むアダプター"""

    def load_lineage_definition(self, yaml_path: str) -> Tuple[Models, LineageEntries]:
        """YAMLファイルからモデルとリネージをロード

        Args:
            yaml_path: YAMLファイルパス

        Returns:
            (Models, LineageEntries)のタプル
        """
        data = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))

        # モデル定義を変換
        models_data = data.get("models", [])
        models = Models([self._dict_to_model(m) for m in models_data])

        # リネージ定義を変換
        lineage_data = data.get("lineage", [])
        lineage = LineageEntries.from_dicts(lineage_data)

        return models, lineage

    def _dict_to_model(self, data: Dict[str, Any]) -> ModelDefinition:
        """辞書からModelDefinitionを生成（再帰的）"""
        children_data = data.get('children', [])
        children = [self._dict_to_model(c) for c in children_data]

        return ModelDefinition(
            name=data['name'],
            type=data.get('type', 'datastore'),
            props=data.get('props', []),
            children=children
        )


# ============================================
# Repository Layer
# ============================================

class ModelRepository:
    """外部ソースからモデルを探索・取得するリポジトリ"""

    def __init__(self,
                 csv_adapter: CSVAdapter,
                 openapi_adapter: OpenAPIAdapter,
                 asyncapi_adapter: AsyncAPIAdapter):
        self.csv_adapter = csv_adapter
        self.openapi_adapter = openapi_adapter
        self.asyncapi_adapter = asyncapi_adapter

    def find_models(
        self,
        required_models: ReferencedModels,
        program_dirs: List[str],
        datastore_dirs: List[str],
        openapi_specs: List[str],
        asyncapi_specs: List[str]
    ) -> Tuple[Models, Set[str]]:
        """必要なモデルを外部ソースから検索して取得

        優先順位: OpenAPI → AsyncAPI → CSV

        Args:
            required_models: 必要なモデル名の集合
            program_dirs: programタイプのCSVディレクトリリスト
            datastore_dirs: datastoreタイプのCSVディレクトリリスト
            openapi_specs: OpenAPI仕様ファイルリスト
            asyncapi_specs: AsyncAPI仕様ファイルリスト

        Returns:
            (Models, csv_model_names): 見つかったモデルとCSV由来のモデル名
        """
        # Immutable化: Models.merge()を使用
        models_list = []
        csv_model_names = set()
        missing_models = set(required_models.to_set())

        # 1. OpenAPIから取得
        if openapi_specs:
            openapi_models = self._find_from_openapi(openapi_specs, missing_models)
            models_list.append(openapi_models)
            missing_models -= openapi_models.get_names()

        # 2. AsyncAPIから取得
        if asyncapi_specs:
            asyncapi_models = self._find_from_asyncapi(asyncapi_specs, missing_models)
            models_list.append(asyncapi_models)
            missing_models -= asyncapi_models.get_names()

        # 3. CSVから取得
        if program_dirs or datastore_dirs:
            csv_models = self._find_from_csv(program_dirs, datastore_dirs, missing_models)
            csv_model_names = csv_models.get_names()
            models_list.append(csv_models)
            missing_models -= csv_model_names

        # 見つからなかったモデルを通知
        if missing_models:
            print(f"Info: The following values will be treated as literals (not found as models): {', '.join(sorted(missing_models))}", file=sys.stderr)

        # Models.merge()で結合
        models = Models.merge(models_list) if models_list else Models([])
        return models, csv_model_names

    def _find_from_openapi(self, spec_files: List[str], required_models: Set[str]) -> Models:
        """OpenAPI仕様からモデルを検索"""
        models_list = []
        found_models = set()

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
                    if model_name in schemas and model_name not in found_models:
                        model_def = self.openapi_adapter.load_model(spec_path, model_name, 'program')
                        if model_def:
                            models_list.append(model_def)
                            found_models.add(model_name)

            except Exception as e:
                print(f"Error processing OpenAPI spec '{spec_path}': {e}", file=sys.stderr)
                continue

        return Models(models_list)

    def _find_from_asyncapi(self, spec_files: List[str], required_models: Set[str]) -> Models:
        """AsyncAPI仕様からモデルを検索"""
        models_list = []
        found_models = set()

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
                    if model_name in schemas and model_name not in found_models:
                        model_def = self.asyncapi_adapter.load_model(spec_path, model_name, 'program')
                        if model_def:
                            models_list.append(model_def)
                            found_models.add(model_name)

            except Exception as e:
                print(f"Error processing AsyncAPI spec '{spec_path}': {e}", file=sys.stderr)
                continue

        return Models(models_list)

    def _find_from_csv(self, program_dirs: List[str], datastore_dirs: List[str], required_models: Set[str]) -> Models:
        """CSVファイルからモデルを検索"""
        models_dict = {}

        # Search program model directories
        for dir_path in program_dirs:
            path = Path(dir_path)
            if not path.exists():
                print(f"Warning: Program model directory '{dir_path}' does not exist", file=sys.stderr)
                continue

            for csv_file in path.rglob("*.csv"):
                model_def = self.csv_adapter.load_model(str(csv_file), 'program')
                if model_def and model_def.name in required_models:
                    if model_def.name in models_dict:
                        print(f"Warning: Duplicate model '{model_def.name}' found in '{csv_file}'", file=sys.stderr)
                    else:
                        models_dict[model_def.name] = model_def

        # Search datastore model directories
        for dir_path in datastore_dirs:
            path = Path(dir_path)
            if not path.exists():
                print(f"Warning: Datastore model directory '{dir_path}' does not exist", file=sys.stderr)
                continue

            for csv_file in path.rglob("*.csv"):
                model_def = self.csv_adapter.load_model(str(csv_file), 'datastore')
                if model_def and model_def.name in required_models:
                    if model_def.name in models_dict:
                        print(f"Warning: Duplicate model '{model_def.name}' found in '{csv_file}'", file=sys.stderr)
                    else:
                        models_dict[model_def.name] = model_def

        return Models(list(models_dict.values()))



# ============================================
# UseCase Layer
# ============================================

@dataclass
class ParsedModelsData:
    """ParseModelsUseCaseの出力データ"""
    model_types: Dict[str, str]
    field_nodes_by_model: Dict[str, List[Tuple[str, str]]]
    field_node_ids: Dict[str, str]
    model_hierarchy: Dict[str, Dict[str, Any]]

    def generate_subgraph(
        self,
        model_path: str,
        indent: int = 2
    ) -> List[str]:
        """Generate Mermaid subgraph with proper nesting.

        Supports instance identifiers in model_path (e.g., 'Money#jpy').

        Args:
            model_path: Full path of the model (may include instance like 'Money#jpy')
            indent: Indentation level for formatting

        Returns:
            List of Mermaid diagram lines
        """
        lines = []
        spaces = "  " * indent
        mtype = self.model_types.get(model_path, 'datastore')

        # Extract base model name and instance from model_path
        if '#' in model_path:
            base_path, instance = model_path.rsplit('#', 1)
            model_display_name = base_path.split(".")[-1]
            display_label = f'"{model_display_name} ({instance})"'
        else:
            model_display_name = model_path.split(".")[-1]
            display_label = model_display_name

        # Generate subgraph header
        subgraph_id = MermaidNode.sanitize_id(model_path.replace(".", "_").replace("#", "_"))
        lines.append(f"{spaces}subgraph {subgraph_id}[{display_label}]")

        # Add fields for this model
        nodes = self.field_nodes_by_model.get(model_path, [])
        for nid, label in nodes:
            lines.append(f'{spaces}  {nid}["{label}"]:::property')

        # Add nested children
        children = self.model_hierarchy.get(model_path, {}).get('children', [])
        if children:
            if nodes:
                lines.append("")  # Add spacing between fields and children
            for child in children:
                child_lines = self.generate_subgraph(child, indent + 1)
                lines.extend(child_lines)

        lines.append(f"{spaces}end")
        lines.append(f"{spaces}class {subgraph_id} {mtype}_bg")

        return lines


class ExtractReferencedModelsUseCase:
    """リネージから参照されているモデル・インスタンス・フィールドを抽出するUseCase"""

    def execute(self, lineage: LineageEntries, yaml_models: Models) -> Tuple[ReferencedModels, ModelInstances, UsedFields]:
        """リネージから参照情報を抽出

        Args:
            lineage: リネージエントリのコレクション
            yaml_models: YAML定義のモデル（フィールド参照抽出用）

        Returns:
            (ReferencedModels, ModelInstances, UsedFields)
        """
        # Immutable化: 1回のループで3つのデータ構造を構築
        model_names: Set[str] = set()
        instances_dict: Dict[str, Set[str]] = {}

        for entry in lineage:
            # from側
            for ref in entry.from_refs:
                field_ref = FieldReference(ref)
                if field_ref.model:
                    model_names.add(field_ref.model)
                    # インスタンス処理
                    if field_ref.instance:
                        if field_ref.model not in instances_dict:
                            instances_dict[field_ref.model] = set()
                        instances_dict[field_ref.model].add(field_ref.instance)
                    else:
                        # インスタンスなしでモデルが使われることをマーク
                        if field_ref.model not in instances_dict:
                            instances_dict[field_ref.model] = set()

            # to側
            if entry.to_ref:
                field_ref = FieldReference(entry.to_ref)
                if field_ref.model:
                    model_names.add(field_ref.model)
                    # インスタンス処理
                    if field_ref.instance:
                        if field_ref.model not in instances_dict:
                            instances_dict[field_ref.model] = set()
                        instances_dict[field_ref.model].add(field_ref.instance)
                    else:
                        # インスタンスなしでモデルが使われることをマーク
                        if field_ref.model not in instances_dict:
                            instances_dict[field_ref.model] = set()

        # 使用フィールドを抽出（ドメインメソッドを使用）
        used_fields = lineage.extract_referenced_fields(yaml_models)

        # Immutableオブジェクトを生成
        return (
            ReferencedModels(model_names),
            ModelInstances(instances_dict),
            used_fields
        )


class GenerateDynamicFieldsUseCase:
    """props省略モデルの動的フィールド生成UseCase"""

    def execute(self, lineage: LineageEntries, models: Models) -> Models:
        """動的フィールドを生成（新しいModelsを返す）

        Args:
            lineage: リネージエントリのコレクション
            models: モデルのコレクション

        Returns:
            動的フィールドが追加された新しいModels
        """
        # 動的フィールド生成（ドメインメソッドを使用、新しいインスタンスを返す）
        return models.with_dynamic_fields(lineage)


class ParseModelsUseCase:
    """モデル階層のパース・ノードID生成UseCase"""

    def execute(
        self,
        models: Models,
        used_fields: Optional[UsedFields],
        csv_model_names: Set[str],
        model_instances: ModelInstances
    ) -> ParsedModelsData:
        """モデルをパースしてMermaid生成用のデータ構造を作成

        Args:
            models: モデルのコレクション
            used_fields: 使用されているフィールド（フィルタリング用、Noneなら全表示）
            csv_model_names: CSV由来のモデル名（フィルタリング対象）
            model_instances: モデルインスタンスの情報

        Returns:
            ParsedModelsData
        """
        # Models.parse_to_structured_data() メソッドを使用
        return models.parse_to_structured_data(
            used_fields=used_fields,
            csv_model_names=csv_model_names,
            model_instances=model_instances
        )


class GenerateMermaidDiagramUseCase:
    """Mermaid図の生成UseCase"""

    def __init__(self):
        self.literal_counter = 0

    def execute(self, parsed_data: ParsedModelsData, lineage: LineageEntries) -> str:
        """Mermaid図の文字列を生成

        Args:
            parsed_data: パース済みモデルデータ
            lineage: リネージエントリのコレクション

        Returns:
            Mermaid図のMarkdown文字列
        """
        lines = [
            "```mermaid",
            "graph LR",
            "  classDef program_bg fill:#E3F2FD,stroke:#1565C0,stroke-width:2px;",
            "  classDef datastore_bg fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px;",
            "  classDef property fill:#F5F5F5,stroke:#9E9E9E,stroke-width:1px,color:#424242;",
            "  classDef literal fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px,color:#BF360C;",
            ""
        ]

        # サブグラフ生成
        for model_path in sorted(parsed_data.model_hierarchy.keys()):
            if parsed_data.model_hierarchy[model_path]['parent'] is None:
                subgraph_lines = parsed_data.generate_subgraph(model_path)
                lines.extend(subgraph_lines)
                lines.append("")

        # リネージエッジ生成
        model_ref_styles = {}

        for entry in lineage:
            if not entry.to_ref:
                continue

            # ターゲット決定
            if entry.to_ref in parsed_data.field_node_ids:
                t_id = parsed_data.field_node_ids[entry.to_ref]
            elif entry.to_ref in parsed_data.model_types:
                t_id = MermaidNode.sanitize_id(entry.to_ref.replace(".", "_").replace("#", "_"))
                if entry.to_ref not in model_ref_styles:
                    model_ref_styles[entry.to_ref] = parsed_data.model_types[entry.to_ref]
            else:
                print(f"Warning: Unknown reference '{entry.to_ref}' in lineage", file=sys.stderr)
                continue

            # ソース処理
            for i, src in enumerate(entry.from_refs):
                # モデル参照チェック（フィールド参照より優先）
                if src in parsed_data.model_types:
                    s_id = MermaidNode.sanitize_id(src.replace(".", "_").replace("#", "_"))
                    if src not in model_ref_styles:
                        model_ref_styles[src] = parsed_data.model_types[src]
                elif src in parsed_data.field_node_ids:
                    s_id = parsed_data.field_node_ids[src]
                else:
                    # リテラル値
                    s_id = self._ensure_literal(lines, src)

                # エッジ追加
                label = entry.transform if i == 0 and entry.transform else ""
                if label:
                    lines.append(f'  {s_id} -->|"{label}"| {t_id}')
                else:
                    lines.append(f'  {s_id} --> {t_id}')

        # モデル参照のスタイル追加
        if model_ref_styles:
            lines.append("")
            for model_ref, model_type in model_ref_styles.items():
                node_id = MermaidNode.sanitize_id(model_ref.replace(".", "_").replace("#", "_"))
                if model_type == "program":
                    lines.append(f'  style {node_id} fill:#E3F2FD,stroke:#1565C0,stroke-width:2px')
                else:  # datastore
                    lines.append(f'  style {node_id} fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px')

        lines.append("```")
        return "\n".join(lines)

    def _ensure_literal(self, lines: List[str], label: str) -> str:
        """リテラルノードを作成"""
        self.literal_counter += 1
        nid = MermaidNode.sanitize_id(f"lit_{self.literal_counter}")
        lines.append(f'  {nid}["{label}"]:::literal')
        return nid


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
        program_model_dir: List of directories containing program model CSVs
        datastore_model_dir: List of directories containing datastore model CSVs
        openapi_spec: List of OpenAPI specification files
        asyncapi_spec: List of AsyncAPI specification files
        show_all_props: If True, show all properties; if False, show only used fields for CSV models
    """
    # 1. YAMLロード
    yaml_adapter = YAMLAdapter()
    yaml_models, lineage = yaml_adapter.load_lineage_definition(input_yaml)

    # 2. リネージ解析（参照モデル・インスタンス・フィールド抽出）
    extract_usecase = ExtractReferencedModelsUseCase()
    referenced_models, model_instances, _ = extract_usecase.execute(lineage, yaml_models)

    # 3. 外部モデル取得
    repository = ModelRepository(
        CSVAdapter(),
        OpenAPIAdapter(),
        AsyncAPIAdapter()
    )
    missing_models = referenced_models.difference(ReferencedModels(yaml_models.get_names()))
    external_models, csv_model_names = repository.find_models(
        missing_models,
        program_model_dirs or [],
        datastore_model_dirs or [],
        openapi_specs or [],
        asyncapi_specs or []
    )

    # 4. モデル統合（Immutable化: Models.merge()使用）
    all_models = Models.merge([yaml_models, external_models])

    # 5. 動的フィールド生成（Immutable化: 新しいModelsを受け取る）
    dynamic_usecase = GenerateDynamicFieldsUseCase()
    all_models = dynamic_usecase.execute(lineage, all_models)

    # 6. 使用フィールド抽出（フィルタリング用）
    used_fields = None
    if not show_all_props and csv_model_names:
        # 動的フィールド生成後に再度抽出
        _, _, used_fields = extract_usecase.execute(lineage, all_models)

    # 7. モデルパース
    parse_usecase = ParseModelsUseCase()
    parsed_data = parse_usecase.execute(
        all_models,
        used_fields,
        csv_model_names,
        model_instances
    )

    # 8. Mermaid図生成
    generate_diagram_usecase = GenerateMermaidDiagramUseCase()
    diagram = generate_diagram_usecase.execute(parsed_data, lineage)

    # 9. ファイル出力
    Path(output_md).write_text(diagram, encoding='utf-8')

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
    --program-model-dir data/レイアウト \\
    --datastore-model-dir data/テーブル定義

  # OpenAPI mode
  python lineage_to_md.py lineage.yml output.md \\
    --openapi-spec data/openapi/user-api.yaml

  # AsyncAPI mode
  python lineage_to_md.py lineage.yml output.md \\
    --asyncapi-spec data/asyncapi/events.yaml

  # Mixed mode (YAML + CSV + OpenAPI + AsyncAPI)
  python lineage_to_md.py lineage.yml output.md \\
    --program-model-dir data/レイアウト \\
    --openapi-spec data/openapi/api.yaml \\
    --asyncapi-spec data/asyncapi/events.yaml
"""
    )

    parser.add_argument("input_yaml", help="Path to input YAML file")
    parser.add_argument("output_md", help="Path to output Markdown file")
    parser.add_argument(
        "--program-model-dir", "-p",
        action="append",
        dest="program_model_dir",
        help="Directory containing program model CSV files (can be specified multiple times)"
    )
    parser.add_argument(
        "--datastore-model-dir", "-d",
        action="append",
        dest="datastore_model_dir",
        help="Directory containing datastore model CSV files (can be specified multiple times)"
    )
    parser.add_argument(
        "--openapi-spec", "-o",
        action="append",
        dest="openapi_spec",
        help="OpenAPI specification file (YAML/JSON) (can be specified multiple times)"
    )
    parser.add_argument(
        "--asyncapi-spec", "-a",
        action="append",
        dest="asyncapi_spec",
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
        program_model_dirs=args.program_model_dir or [],
        datastore_model_dirs=args.datastore_model_dir or [],
        openapi_specs=args.openapi_spec or [],
        asyncapi_specs=args.asyncapi_spec or [],
        show_all_props=args.show_all_props
    )
