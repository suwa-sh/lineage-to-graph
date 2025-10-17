import sys
import yaml
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

def slug(s: str) -> str:
    s = str(s).replace("::", "_")
    s = re.sub(r"[^A-Za-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "id"
    if re.match(r"^[0-9]", s):
        s = "n_" + s
    return s

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

def main(input_yaml: str, output_md: str) -> None:
    """Convert YAML lineage definition to Mermaid Markdown diagram.

    Args:
        input_yaml: Path to input YAML file
        output_md: Path to output Markdown file
    """
    data = yaml.safe_load(Path(input_yaml).read_text(encoding="utf-8"))

    models = data.get("models", [])
    lineage = data.get("lineage", [])

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

    for e in lineage:
        to_ref = e.get("to")
        if not to_ref: continue
        t_model, t_field = parse_field(to_ref)
        t_id = field_node_ids.get(f"{t_model}.{t_field}")
        srcs = e.get("from")
        if isinstance(srcs, str): srcs = [srcs]
        transform = e.get("transform", "")
        for i, src in enumerate(srcs):
            s_id = field_node_ids[src] if is_model_field(src) else ensure_literal(src)
            label = transform if i == 0 and transform else ""
            if label:
                lines.append(f'  {s_id} -->|"{label}"| {t_id}')
            else:
                lines.append(f'  {s_id} --> {t_id}')

    lines.append("```")
    Path(output_md).write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python lineage_to_mermaid_v3.py <input.yaml> <output.md>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
