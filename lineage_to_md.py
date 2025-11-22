from __future__ import annotations
import sys
import yaml
import re
import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)

# ============================================
# Domain Layer
# ============================================

# エンティティ・値オブジェクト

@dataclass(frozen=True)
class ModelDefinition:
    """モデル定義のエンティティ"""
    name: str
    type: str
    props: Tuple[str, ...] = field(default_factory=tuple)
    children: Tuple['ModelDefinition', ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LineageEntry:
    """リネージエントリのエンティティ"""
    from_refs: Tuple[str, ...]
    to_ref: str
    transform: Optional[str] = None


@dataclass(frozen=True)
class FieldReference:
    """フィールド参照の値オブジェクト"""
    ref: str
    model: str = field(init=False)
    instance: Optional[str] = field(init=False)
    field: Optional[str] = field(init=False)

    def __post_init__(self):
        model, instance, field_name = self.parse(self.ref)
        object.__setattr__(self, 'model', model)
        object.__setattr__(self, 'instance', instance)
        object.__setattr__(self, 'field', field_name)

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


@dataclass(frozen=True)
class MermaidNode:
    """Mermaidノードの値オブジェクト"""
    node_id: str
    label: str
    style_class: str

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

        Note: This method delegates to DynamicFieldGenerator domain service.

        Args:
            lineage: LineageEntries コレクション

        Returns:
            新しいModelsインスタンス（動的フィールドが追加されたもの）
        """
        generator = DynamicFieldGenerator(self, lineage)
        return generator.generate()

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

        Note: This method delegates to ModelParser domain service.

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
        parser = ModelParser(self, used_fields, csv_model_names, model_instances)
        return parser.parse(parent_prefix, parent_instance, parsed_data)


# ドメインサービス

class DynamicFieldGenerator:
    """動的フィールド生成のドメインサービス

    モデル定義に props が未定義の場合、lineage参照から自動的にフィールドを生成します。
    このクラスは Models の責務を超えた複雑なビジネスロジックを担当します。
    """

    def __init__(self, models: 'Models', lineage: 'LineageEntries'):
        """
        Args:
            models: 既存のModelsコレクション
            lineage: LineageEntriesコレクション
        """
        self.models = models
        self.lineage = lineage

    def generate(self) -> 'Models':
        """動的フィールド生成を実行

        Returns:
            新しいModelsインスタンス（動的フィールドが追加されたもの）
        """
        # モデル定義を取得（新しいリストとして複製）
        model_list = [self._copy_model(m) for m in self.models.to_list()]

        # 既存モデルのマップを構築
        model_map = self._build_model_map(model_list)

        # 動的フィールドを収集
        dynamic_fields = self._collect_dynamic_fields(model_map)

        # モデルを更新（model_mapが更新される）
        self._update_models_with_dynamic_fields(model_map, dynamic_fields)

        # ツリーを再構築（frozenオブジェクトとして）
        updated_models = self._rebuild_tree_from_map(model_list, model_map)

        return Models(updated_models)

    def _copy_model(self, model: ModelDefinition) -> ModelDefinition:
        """ModelDefinitionを再帰的に複製

        Args:
            model: 複製元のModelDefinition

        Returns:
            複製されたModelDefinition
        """
        return ModelDefinition(
            name=model.name,
            type=model.type,
            props=tuple(model.props),  # tupleに変換
            children=tuple(self._copy_model(c) for c in model.children)
        )

    def _build_model_map(self, models: List[ModelDefinition]) -> Dict[str, ModelDefinition]:
        """既存モデルのパスマップを構築

        Args:
            models: モデル定義のリスト

        Returns:
            {model_path: ModelDefinition} のマップ
        """
        model_map: Dict[str, ModelDefinition] = {}

        def collect(model_list: List[ModelDefinition], prefix: str = "") -> None:
            for m in model_list:
                path = f"{prefix}.{m.name}" if prefix else m.name
                model_map[path] = m
                if m.children:
                    collect(m.children, path)

        collect(models)
        return model_map

    def _collect_dynamic_fields(self, model_map: Dict[str, ModelDefinition]) -> Dict[str, Set[str]]:
        """lineageから動的に生成すべきフィールドを収集

        Args:
            model_map: モデルパスのマップ

        Returns:
            {model_path: {field_names}} の辞書
        """
        dynamic_fields: Dict[str, Set[str]] = {}

        for entry in self.lineage:
            # Process 'from' references
            for ref in entry.from_refs:
                self._extract_field_reference(ref, model_map, dynamic_fields)

            # Process 'to' reference
            if entry.to_ref:
                self._extract_field_reference(entry.to_ref, model_map, dynamic_fields)

        return dynamic_fields

    def _extract_field_reference(
        self,
        ref: str,
        model_map: Dict[str, ModelDefinition],
        dynamic_fields: Dict[str, Set[str]]
    ) -> None:
        """フィールド参照を抽出して動的フィールドマップに追加

        Args:
            ref: リネージ参照文字列
            model_map: モデルパスのマップ
            dynamic_fields: 動的フィールドの蓄積先
        """
        # Skip if no field reference
        if '.' not in ref:
            return

        # Check if root model exists
        root_model = ref.split('.')[0].split('#')[0]
        if root_model not in model_map:
            return  # Treat as literal

        # Handle instance notation: Model#instance.field -> Model.field
        if '#' in ref:
            ref_without_instance = ref.replace('#', '.').replace('..', '.')
            parts = ref_without_instance.rsplit('.', 1)
            if len(parts) == 2:
                model_path_with_instance, _ = parts
                model_path = model_path_with_instance.split('.')[0]
                field = ref.split('.')[-1]
            else:
                return
        else:
            parts = ref.rsplit('.', 1)
            if len(parts) != 2:
                return
            model_path, field = parts

        # Check if model path exists
        if model_path in model_map:
            model_def = model_map[model_path]
            # Add field if props is empty or undefined
            if not model_def.props:
                if model_path not in dynamic_fields:
                    dynamic_fields[model_path] = set()
                dynamic_fields[model_path].add(field)
        else:
            # Model path doesn't exist - need to create child model
            if model_path not in dynamic_fields:
                dynamic_fields[model_path] = set()
            dynamic_fields[model_path].add(field)

    def _update_models_with_dynamic_fields(
        self,
        model_map: Dict[str, ModelDefinition],
        dynamic_fields: Dict[str, Set[str]]
    ) -> None:
        """動的フィールドでモデルを更新（frozen対応）

        Args:
            model_map: モデルパスのマップ（更新される）
            dynamic_fields: 動的フィールドのマップ
        """
        for model_path, fields in dynamic_fields.items():
            parts = model_path.split('.')

            if model_path in model_map:
                # Existing model - create new instance with updated props
                model_def = model_map[model_path]
                if not model_def.props:
                    logging.info(f"モデル '{model_path}' はプロパティ未定義のため、lineage参照から動的生成します")
                    # Create new ModelDefinition with updated props
                    updated_model = ModelDefinition(
                        name=model_def.name,
                        type=model_def.type,
                        props=tuple(sorted(fields)),
                        children=model_def.children
                    )
                    model_map[model_path] = updated_model
            else:
                # Need to create missing child models
                self._create_missing_child_models(model_map, parts, fields)

    def _create_missing_child_models(
        self,
        model_map: Dict[str, ModelDefinition],
        path_parts: List[str],
        fields: Set[str]
    ) -> None:
        """不足している子モデルを作成（frozen対応）

        Args:
            model_map: モデルパスのマップ（更新される）
            path_parts: モデルパスを分割したリスト
            fields: 追加するフィールドのセット
        """
        # Find where the path exists and where it breaks
        parent_type = 'program'
        missing_index = -1

        for i, part in enumerate(path_parts):
            partial_path = '.'.join(path_parts[:i+1])
            if partial_path in model_map:
                parent_type = model_map[partial_path].type
            else:
                missing_index = i
                break

        if missing_index < 0:
            return  # All parts exist

        # Create missing child models from missing_index onwards
        for i in range(missing_index, len(path_parts)):
            part = path_parts[i]
            created_path = '.'.join(path_parts[:i+1])

            # Create new child model
            new_model = ModelDefinition(
                name=part,
                type=parent_type,  # Inherit type from parent
                props=tuple(sorted(fields)) if i == len(path_parts) - 1 else tuple(),
                children=tuple()
            )

            # Update model_map
            model_map[created_path] = new_model

            # Log info message
            logging.info(f"モデル '{created_path}' はプロパティ未定義のため、lineage参照から動的生成します")

    def _rebuild_tree_from_map(
        self,
        original_models: List[ModelDefinition],
        model_map: Dict[str, ModelDefinition]
    ) -> List[ModelDefinition]:
        """model_mapから更新されたモデルツリーを再構築

        Args:
            original_models: 元のルートモデルリスト
            model_map: 更新されたモデルマップ

        Returns:
            再構築されたModelDefinitionのリスト
        """
        def rebuild_model(model_path: str) -> ModelDefinition:
            """指定パスのモデルを再帰的に再構築"""
            model = model_map[model_path]

            # 元のchildrenの順序を保持するため、model.childrenから順序を取得
            child_order = {child.name: i for i, child in enumerate(model.children)}

            # 子モデルのパスを見つける
            child_paths = [
                path for path in model_map.keys()
                if path.startswith(model_path + '.') and
                path.count('.') == model_path.count('.') + 1
            ]

            # 元の順序でソート（新しく追加された子は末尾に）
            def get_order(path: str) -> int:
                child_name = path.split('.')[-1]
                return child_order.get(child_name, len(child_order))

            child_paths_sorted = sorted(child_paths, key=get_order)

            # 子モデルを再帰的に再構築
            rebuilt_children = tuple(rebuild_model(child_path) for child_path in child_paths_sorted)

            # 新しいModelDefinitionを生成（childrenを更新）
            return ModelDefinition(
                name=model.name,
                type=model.type,
                props=model.props,
                children=rebuilt_children
            )

        # ルートモデル（'.'を含まないパス）を再構築
        result = []
        for original_model in original_models:
            model_path = original_model.name
            if model_path in model_map:
                result.append(rebuild_model(model_path))

        return result


class ModelParser:
    """モデル構造解析のドメインサービス

    モデル階層を解析し、Mermaid図生成に必要な構造化データを構築します。
    このクラスは Models の責務を超えた複雑な解析ロジックを担当します。
    """

    def __init__(
        self,
        models: 'Models',
        used_fields: Optional['UsedFields'] = None,
        csv_model_names: Set[str] = None,
        model_instances: Optional['ModelInstances'] = None
    ):
        """
        Args:
            models: 解析対象のModelsコレクション
            used_fields: 使用されているフィールド（フィルタリング用）
            csv_model_names: CSV由来のモデル名セット
            model_instances: モデルインスタンスの情報
        """
        self.models = models
        self.used_fields = used_fields
        self.csv_model_names = csv_model_names or set()
        self.model_instances = model_instances

    def parse(
        self,
        parent_prefix: str = "",
        parent_instance: str = "",
        parsed_data: Optional['ParsedModelsData'] = None
    ) -> 'ParsedModelsData':
        """モデル階層を解析してParsedModelsDataを構築

        Args:
            parent_prefix: 親モデルのパス（階層構造用）
            parent_instance: 親モデルのインスタンス識別子
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

        for m in self.models:
            self._parse_model(
                m, parent_prefix, parent_instance, parsed_data
            )

        return parsed_data

    def _parse_model(
        self,
        model: ModelDefinition,
        parent_prefix: str,
        parent_instance: str,
        parsed_data: 'ParsedModelsData'
    ) -> None:
        """単一モデルを解析

        Args:
            model: 解析対象のModelDefinition
            parent_prefix: 親モデルのパス
            parent_instance: 親インスタンス
            parsed_data: 蓄積先のParsedModelsData
        """
        name = model.name
        mtype = model.type
        props = model.props
        children = model.children

        # Build full model path
        full_model_path = f"{parent_prefix}.{name}" if parent_prefix else name

        # Get instances for this model
        instances = self.model_instances.get_instances(name) if self.model_instances else set()
        if not instances:
            instances = {None}

        # Sort instances for deterministic output
        sorted_instances = sorted(instances, key=lambda x: (x is not None, x or ''))

        # Process each instance
        for instance in sorted_instances:
            self._process_model_instance(
                instance, full_model_path, mtype, props, children,
                parent_prefix, parsed_data
            )

        # Recursively parse children
        if children:
            child_parser = ModelParser(
                Models(children),
                self.used_fields,
                self.csv_model_names,
                self.model_instances
            )
            child_parser.parse(full_model_path, parent_instance, parsed_data)

    def _process_model_instance(
        self,
        instance: Optional[str],
        full_model_path: str,
        mtype: str,
        props: List[str],
        children: List[ModelDefinition],
        parent_prefix: str,
        parsed_data: 'ParsedModelsData'
    ) -> None:
        """モデルインスタンスを処理

        Args:
            instance: インスタンス識別子（Noneの場合はデフォルト）
            full_model_path: モデルの完全パス
            mtype: モデルタイプ
            props: プロパティリスト
            children: 子モデルのリスト
            parent_prefix: 親モデルのパス
            parsed_data: 蓄積先のParsedModelsData
        """
        # Build instance-specific paths
        if instance:
            instance_path = f"{full_model_path}#{instance}"
            instance_id_part = f"_{instance}"
        else:
            instance_path = full_model_path
            instance_id_part = ""

        # Store model type
        parsed_data.model_types[instance_path] = mtype

        # Store hierarchy info
        parsed_data.model_hierarchy[instance_path] = {
            'parent': parent_prefix if parent_prefix else None,
            'children': [f"{full_model_path}.{c.name}" for c in children] if children else [],
            'instance': instance
        }

        # Parse fields
        should_filter = self._should_filter_fields(instance_path, full_model_path)
        nodes = self._parse_fields(
            props, full_model_path, instance, instance_id_part,
            should_filter, parsed_data
        )

        parsed_data.field_nodes_by_model[instance_path] = nodes

    def _should_filter_fields(
        self,
        instance_path: str,
        full_model_path: str
    ) -> bool:
        """フィールドをフィルタリングすべきか判定

        Args:
            instance_path: インスタンスパス
            full_model_path: モデルの完全パス

        Returns:
            フィールドリングすべきかどうか
        """
        if self.used_fields is None or not self.csv_model_names:
            return False

        # Extract model name from path (last component)
        model_name = full_model_path.split('.')[-1]

        return (
            model_name in self.csv_model_names and
            self.used_fields.contains(instance_path)
        )

    def _parse_fields(
        self,
        props: List[str],
        full_model_path: str,
        instance: Optional[str],
        instance_id_part: str,
        should_filter: bool,
        parsed_data: 'ParsedModelsData'
    ) -> List[Tuple[str, str]]:
        """フィールドを解析してノードリストを生成

        Args:
            props: プロパティリスト
            full_model_path: モデルの完全パス
            instance: インスタンス識別子
            instance_id_part: インスタンスID部分（ノードID生成用）
            should_filter: フィルタリングすべきかどうか
            parsed_data: field_node_idsを更新するためのParsedModelsData

        Returns:
            (node_id, field_name) のタプルリスト
        """
        nodes = []

        # Build instance path for field reference
        if instance:
            instance_path = f"{full_model_path}#{instance}"
        else:
            instance_path = full_model_path

        for p in props:
            # Apply filtering if applicable
            if should_filter:
                if not self._is_field_used(instance_path, p):
                    continue

            # Generate node ID
            nid = MermaidNode.sanitize_id(
                f"{full_model_path}{instance_id_part}_{p}".replace(".", "_")
            )
            nodes.append((nid, str(p)))

            # Map field reference to node ID
            if instance:
                field_ref = f"{full_model_path}#{instance}.{p}"
            else:
                field_ref = f"{full_model_path}.{p}"
            parsed_data.field_node_ids[field_ref] = nid

        return nodes

    def _is_field_used(
        self,
        instance_path: str,
        field_name: str
    ) -> bool:
        """フィールドが使用されているか判定

        Args:
            instance_path: インスタンスパス
            field_name: フィールド名

        Returns:
            フィールドが使用されているかどうか
        """
        if self.used_fields is None:
            return True

        model_used_fields = self.used_fields.get_fields(instance_path)

        # '*' means all fields are used
        if '*' in model_used_fields:
            return True

        # Check if this specific field is used
        return field_name in model_used_fields


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
        entries = []
        for d in data:
            from_val = d.get('from', [])
            if isinstance(from_val, str):
                from_val = [from_val]
            entries.append(LineageEntry(
                from_refs=tuple(from_val),
                to_ref=d.get('to', ''),
                transform=d.get('transform')
            ))
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


@dataclass(frozen=True)
class UsedFields:
    """使用されているフィールドのマップ {model_path: {field_names}}（Immutable）"""
    _fields: Dict[str, Set[str]] = field(default_factory=dict)

    def get_fields(self, model_path: str) -> Set[str]:
        return set(self._fields.get(model_path, set()))  # 防御的コピー

    def contains(self, model_path: str) -> bool:
        return model_path in self._fields


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
                logging.warning(f"CSV filename '{csv_path}' does not match pattern '論理名__ModelName.csv'")
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
                logging.error(f"Could not decode CSV file '{csv_path}' with any supported encoding")
                return None

            # Parse CSV
            reader = csv.DictReader(content.splitlines())
            for row in reader:
                physical_name = row.get('物理名', '').strip()
                if physical_name:
                    props.append(physical_name)

            if not props:
                logging.warning(f"No properties found in CSV file '{csv_path}'")
                return None

            return ModelDefinition(
                name=model_name,
                type=model_type,
                props=tuple(props)
            )

        except Exception as e:
            logging.error(f"Loading CSV '{csv_path}': {e}")
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
                logging.error(f"OpenAPI spec file '{spec_path}' does not exist")
                return None

            # Load spec file (YAML or JSON)
            with open(path, 'r', encoding='utf-8') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    spec = yaml.safe_load(f)
                elif path.suffix.lower() == '.json':
                    spec = json.load(f)
                else:
                    logging.error(f"Unsupported file format '{path.suffix}' (expected .yaml, .yml, or .json)")
                    return None

            # Navigate to components/schemas
            if 'components' not in spec:
                logging.warning(f"No 'components' section in OpenAPI spec '{spec_path}'")
                return None

            schemas = spec['components'].get('schemas', {})
            if schema_name not in schemas:
                logging.warning(f"Schema '{schema_name}' not found in OpenAPI spec '{spec_path}'")
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
                logging.warning(f"No properties found in schema '{schema_name}' in '{spec_path}'")
                return None

            # Remove duplicates while preserving order
            props = list(dict.fromkeys(props))

            return ModelDefinition(
                name=schema_name,
                type=model_type,
                props=tuple(props)
            )

        except Exception as e:
            logging.error(f"Loading OpenAPI spec '{spec_path}': {e}")
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
                logging.error(f"AsyncAPI spec file '{spec_path}' does not exist")
                return None

            # Load spec file (YAML or JSON)
            with open(path, 'r', encoding='utf-8') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    spec = yaml.safe_load(f)
                elif path.suffix.lower() == '.json':
                    spec = json.load(f)
                else:
                    logging.error(f"Unsupported file format '{path.suffix}' (expected .yaml, .yml, or .json)")
                    return None

            # Navigate to components/schemas
            if 'components' not in spec:
                logging.warning(f"No 'components' section in AsyncAPI spec '{spec_path}'")
                return None

            schemas = spec['components'].get('schemas', {})
            if schema_name not in schemas:
                logging.warning(f"Schema '{schema_name}' not found in AsyncAPI spec '{spec_path}'")
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
                    logging.warning(f"Circular reference detected: {ref_path}")
                    return []
                visited.add(ref_path)

                # External references (http/https)
                if ref_path.startswith('http://') or ref_path.startswith('https://'):
                    logging.warning(f"External reference '{ref_path}' in schema '{schema_name}' is not supported")
                    return []

                # Only handle internal references
                if not ref_path.startswith('#/components/schemas/'):
                    logging.warning(f"Unsupported $ref format '{ref_path}' in schema '{schema_name}' "
                          f"(expected '#/components/schemas/...')")
                    return []

                ref_schema_name = ref_path.split('/')[-1]

                # Schema existence check
                if ref_schema_name not in schemas:
                    logging.warning(f"Referenced schema '{ref_schema_name}' not found in AsyncAPI spec '{spec_path}'")
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
                    logging.info(f"Referenced schema '{ref_schema_name}' has no properties")

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
                logging.warning(f"No properties found in schema '{schema_name}' in '{spec_path}'")
                return None

            # Remove duplicates while preserving order
            props = list(dict.fromkeys(props))

            return ModelDefinition(
                name=schema_name,
                type=model_type,
                props=tuple(props)
            )

        except Exception as e:
            logging.error(f"Loading AsyncAPI spec '{spec_path}': {e}")
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
            props=tuple(data.get('props', [])),
            children=tuple(children)
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
            logging.info(f"The following values will be treated as literals (not found as models): {', '.join(sorted(missing_models))}")

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
                logging.warning(f"OpenAPI spec file '{spec_path}' does not exist")
                continue

            try:
                # Load spec file
                with open(path, 'r', encoding='utf-8') as f:
                    if path.suffix.lower() in ['.yaml', '.yml']:
                        spec = yaml.safe_load(f)
                    elif path.suffix.lower() == '.json':
                        spec = json.load(f)
                    else:
                        logging.warning(f"Unsupported file format '{path.suffix}'")
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
                logging.error(f"Processing OpenAPI spec '{spec_path}': {e}")
                continue

        return Models(models_list)

    def _find_from_asyncapi(self, spec_files: List[str], required_models: Set[str]) -> Models:
        """AsyncAPI仕様からモデルを検索"""
        models_list = []
        found_models = set()

        for spec_path in spec_files:
            path = Path(spec_path)
            if not path.exists():
                logging.warning(f"AsyncAPI spec file '{spec_path}' does not exist")
                continue

            try:
                # Load spec file
                with open(path, 'r', encoding='utf-8') as f:
                    if path.suffix.lower() in ['.yaml', '.yml']:
                        spec = yaml.safe_load(f)
                    elif path.suffix.lower() == '.json':
                        spec = json.load(f)
                    else:
                        logging.warning(f"Unsupported file format '{path.suffix}'")
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
                logging.error(f"Processing AsyncAPI spec '{spec_path}': {e}")
                continue

        return Models(models_list)

    def _find_from_csv(self, program_dirs: List[str], datastore_dirs: List[str], required_models: Set[str]) -> Models:
        """CSVファイルからモデルを検索"""
        models_dict = {}

        # Search program model directories
        for dir_path in program_dirs:
            path = Path(dir_path)
            if not path.exists():
                logging.warning(f"Program model directory '{dir_path}' does not exist")
                continue

            for csv_file in path.rglob("*.csv"):
                model_def = self.csv_adapter.load_model(str(csv_file), 'program')
                if model_def and model_def.name in required_models:
                    if model_def.name in models_dict:
                        logging.warning(f"Duplicate model '{model_def.name}' found in '{csv_file}'")
                    else:
                        models_dict[model_def.name] = model_def

        # Search datastore model directories
        for dir_path in datastore_dirs:
            path = Path(dir_path)
            if not path.exists():
                logging.warning(f"Datastore model directory '{dir_path}' does not exist")
                continue

            for csv_file in path.rglob("*.csv"):
                model_def = self.csv_adapter.load_model(str(csv_file), 'datastore')
                if model_def and model_def.name in required_models:
                    if model_def.name in models_dict:
                        logging.warning(f"Duplicate model '{model_def.name}' found in '{csv_file}'")
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
    """Mermaid図の生成UseCase（ステートレス）"""

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
        literal_counter = 0  # ローカル変数としてカウンターを初期化

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
                logging.warning(f"Unknown reference '{entry.to_ref}' in lineage")
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
                    s_id, literal_counter = self._ensure_literal(lines, src, literal_counter)

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

    def _ensure_literal(self, lines: List[str], label: str, counter: int) -> Tuple[str, int]:
        """リテラルノードを作成（ステートレス）

        Args:
            lines: Mermaid行のリスト
            label: リテラル値
            counter: 現在のカウンター値

        Returns:
            (ノードID, 更新されたカウンター) のタプル
        """
        counter += 1
        nid = MermaidNode.sanitize_id(f"lit_{counter}")
        lines.append(f'  {nid}["{label}"]:::literal')
        return nid, counter


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
