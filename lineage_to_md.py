import sys, yaml, re
from pathlib import Path

def slug(s: str) -> str:
    s = str(s).replace("::", "_")
    s = re.sub(r"[^A-Za-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "id"
    if re.match(r"^[0-9]", s):
        s = "n_" + s
    return s

def parse_field(ref: str):
    if "." not in ref:
        raise ValueError(f"Field reference must be 'Model.field': {ref}")
    model, field = ref.split(".", 1)
    return model, field

def main(input_yaml: str, output_md: str):
    data = yaml.safe_load(Path(input_yaml).read_text(encoding="utf-8"))

    models = data.get("models", [])
    lineage = data.get("lineage", [])

    model_types, field_nodes_by_model, field_node_ids = {}, {}, {}
    for m in models:
        name, mtype = m["name"], m.get("type", "datastore")
        props = m.get("props", [])
        model_types[name] = mtype
        nodes = []
        for p in props:
            nid = slug(f"{name}_{p}")
            nodes.append((nid, str(p)))
            field_node_ids[f"{name}.{p}"] = nid
        field_nodes_by_model[name] = nodes

    lines = [
        "```mermaid",
        "graph LR",
        "  classDef program_bg fill:#E3F2FD,stroke:#1565C0,stroke-width:2px;",
        "  classDef datastore_bg fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px;",
        "  classDef property fill:#F5F5F5,stroke:#9E9E9E,stroke-width:1px,color:#424242;",
        "  classDef literal fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px,color:#BF360C;",
        ""
    ]

    for model, nodes in field_nodes_by_model.items():
        mtype = model_types.get(model, 'datastore')
        lines.append(f"  subgraph {model}[{model}]")
        for nid, label in nodes:
            lines.append(f'    {nid}["{label}"]:::property')
        lines.append("  end")
        lines.append(f"  class {model} {mtype}_bg")
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
