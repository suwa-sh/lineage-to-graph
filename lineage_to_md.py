import sys
import yaml
import re
import csv
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

def extract_referenced_models(lineage: List[Dict[str, Any]]) -> Set[str]:
    """Extract all model names referenced in lineage definitions.

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
            if '.' in ref:  # Field reference like 'Model.field'
                model_name = ref.split('.')[0]
                models.add(model_name)

        # Extract from 'to' field
        to_val = entry.get('to', '')
        if '.' in to_val:
            model_name = to_val.split('.')[0]
            models.add(model_name)

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
    model_hierarchy: Optional[Dict[str, Dict[str, Any]]] = None
) -> Tuple[Dict[str, str], Dict[str, List[Tuple[str, str]]], Dict[str, str], Dict[str, Dict[str, Any]]]:
    """Recursively parse models and their children to build model hierarchy.

    Args:
        models: List of model definitions
        parent_prefix: Parent model path (for nested models)
        model_types: Dict mapping model paths to their types
        field_nodes_by_model: Dict mapping model paths to field nodes
        field_node_ids: Dict mapping field references to node IDs
        model_hierarchy: Dict storing parent-child relationships

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

    for m in models:
        name = m["name"]
        mtype = m.get("type", "datastore")
        props = m.get("props", [])
        children = m.get("children", [])

        # Build full model path
        full_model_path = f"{parent_prefix}.{name}" if parent_prefix else name
        model_types[full_model_path] = mtype

        # Store hierarchy info
        model_hierarchy[full_model_path] = {
            'parent': parent_prefix if parent_prefix else None,
            'children': [f"{full_model_path}.{c['name']}" for c in children] if children else []
        }

        # Parse fields
        nodes = []
        for p in props:
            nid = slug(f"{full_model_path}_{p}".replace(".", "_"))
            nodes.append((nid, str(p)))
            field_node_ids[f"{full_model_path}.{p}"] = nid
        field_nodes_by_model[full_model_path] = nodes

        # Recursively parse children
        if children:
            parse_models_recursive(children, full_model_path, model_types, field_nodes_by_model, field_node_ids, model_hierarchy)

    return model_types, field_nodes_by_model, field_node_ids, model_hierarchy

def generate_subgraph(
    model_path: str,
    model_types: Dict[str, str],
    field_nodes_by_model: Dict[str, List[Tuple[str, str]]],
    model_hierarchy: Dict[str, Dict[str, Any]],
    indent: int = 2
) -> List[str]:
    """Generate Mermaid subgraph with proper nesting.

    Args:
        model_path: Full path of the model
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

    # Get just the last part of the model path for display
    model_display_name = model_path.split(".")[-1]

    # Generate subgraph header
    subgraph_id = slug(model_path.replace(".", "_"))
    lines.append(f"{spaces}subgraph {subgraph_id}[{model_display_name}]")

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
    datastore_model_dirs: Optional[List[str]] = None
) -> None:
    """Convert YAML lineage definition to Mermaid Markdown diagram.

    Args:
        input_yaml: Path to input YAML file
        output_md: Path to output Markdown file
        program_model_dirs: List of directories containing program model CSVs
        datastore_model_dirs: List of directories containing datastore model CSVs
    """
    data = yaml.safe_load(Path(input_yaml).read_text(encoding="utf-8"))

    yaml_models = data.get("models", [])
    lineage = data.get("lineage", [])

    # Merge YAML models with CSV models if directories are specified
    models = list(yaml_models)  # Start with YAML-defined models

    if program_model_dirs or datastore_model_dirs:
        # Extract model names already defined in YAML
        yaml_model_names = set()
        for m in yaml_models:
            yaml_model_names.add(m['name'])

        # Extract all referenced models from lineage
        referenced_models = extract_referenced_models(lineage)

        # Find models that need to be loaded from CSV
        missing_models = referenced_models - yaml_model_names

        if missing_models:
            # Load missing models from CSV directories
            csv_models = find_model_csvs(
                program_model_dirs or [],
                datastore_model_dirs or [],
                missing_models
            )

            # Add CSV models to the list
            models.extend(csv_models.values())

            # Warn about models that couldn't be found (likely literals)
            found_csv_models = set(csv_models.keys())
            still_missing = missing_models - found_csv_models
            if still_missing:
                print(f"Info: The following values will be treated as literals (not found as models in YAML or CSV): {', '.join(sorted(still_missing))}", file=sys.stderr)

    # Use recursive parser to handle nested models
    model_types, field_nodes_by_model, field_node_ids, model_hierarchy = parse_models_recursive(models)

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
    for model_path in model_hierarchy:
        if model_hierarchy[model_path]['parent'] is None:
            subgraph_lines = generate_subgraph(model_path, model_types, field_nodes_by_model, model_hierarchy)
            lines.extend(subgraph_lines)
            lines.append("")

    literal_nodes = {}
    def ensure_literal(label: str) -> str:
        nid = literal_nodes.get(label)
        if nid: return nid
        nid = slug(f"lit_{label}")
        lines.append(f'  {nid}["{label}"]:::literal')
        literal_nodes[label] = nid
        return nid

    def is_model_field(token: str) -> bool:
        return "." in token and token in field_node_ids

    def is_model_reference(token: str) -> bool:
        """Check if token is a model reference (can include dots for nested models)"""
        # Check if it's a known model path (including nested like Parent.Child)
        return token in model_types

    # Track which model references need style overrides
    model_ref_styles = {}

    for e in lineage:
        to_ref = e.get("to")
        if not to_ref: continue

        # Determine target: field reference or model reference
        if "." in to_ref:
            # Field reference: Model.field
            t_model, t_field = parse_field(to_ref)
            t_id = field_node_ids.get(f"{t_model}.{t_field}")
        else:
            # Model reference: use subgraph ID
            if to_ref not in model_types:
                print(f"Warning: Unknown model reference '{to_ref}' in lineage", file=sys.stderr)
                continue
            t_id = slug(to_ref.replace(".", "_"))

        srcs = e.get("from")
        if isinstance(srcs, str): srcs = [srcs]
        transform = e.get("transform", "")

        for i, src in enumerate(srcs):
            # Determine source: model reference, field reference, or literal
            # Check model reference first (before field) to handle nested models correctly
            if is_model_reference(src):
                # Model reference: use subgraph ID as node (creates implicit node)
                s_id = slug(src.replace(".", "_"))
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
            node_id = slug(model_ref.replace(".", "_"))
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

  # Mixed mode (YAML + CSV)
  python lineage_to_md.py lineage.yml output.md \\
    --program-model-dirs data/レイアウト \\
    --datastore-model-dirs data/テーブル定義
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

    args = parser.parse_args()

    main(
        args.input_yaml,
        args.output_md,
        program_model_dirs=args.program_model_dirs or [],
        datastore_model_dirs=args.datastore_model_dirs or []
    )
