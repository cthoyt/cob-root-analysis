"""Identify roots that are not annotated"""
import json
import pickle
from pathlib import Path

import bioontologies
import bioregistry
import click
import networkx as nx
import pandas as pd
import pystow
from tqdm import tqdm
from tqdm.auto import tqdm
import yaml

HERE = Path(__file__).parent.resolve()
DOCS = HERE.joinpath("docs")
DATA = DOCS.joinpath("_data")
DATA.mkdir(exist_ok=True, parents=True)
CACHE = DOCS.joinpath("cache")
CACHE.mkdir(exist_ok=True, parents=True)
RESULTS = DOCS.joinpath("results")
RESULTS.mkdir(exist_ok=True, parents=True)
ERRORS_PATH = HERE.joinpath("errors.tsv")
NO_ROOTS_MSG = "no roots annotated with IAO_0000700"
MODULE = pystow.module("bioregistry", "analysis", "roots")

edge_types = {
    "rdfs:subClassOf",
    "bfo:0000050",
    "ro:0002202",  # derives from/develops from
}
edge_backwards = {
    "bfo:0000051",
}
COLORS = {
    "rdfs:subClassOf": "black",
    "bfo:0000050": "blue",
    "bfo:0000051": "blue",
    "ro:0002202": "purple",
}
DOMAINS = {
    "anatomy and development",
    "phenotype",
}


def analyze(prefix: str):
    path_stub = RESULTS.joinpath(f"{prefix}_results")
    viz_path = path_stub.with_suffix(".svg")

    owl_iri = bioregistry.get_owl_download(prefix)
    if not owl_iri:
        tqdm.write(f"[{prefix}] no owl IRI")
        return

    cache_path = CACHE.joinpath(prefix).with_suffix(".pkl")
    if cache_path.is_file():
        graph = pickle.loads(cache_path.read_bytes())
    else:
        parse_results = bioontologies.convert_to_obograph(owl_iri, input_is_iri=True)
        try:
            graph = parse_results.guess(prefix).standardize()
        except ValueError as e:
            tqdm.write(f"[{prefix} could not guess: {e}")
            return
        cache_path.write_bytes(pickle.dumps(graph))

    names = graph.get_curie_to_name()

    prefix_colon = f"{prefix}:"

    # Get all nodes that are parents of nodes in this
    # ontology, but are not themselves in this ontology
    parents = set()
    children = set()
    hierarchy_graph = nx.DiGraph()  # hierarchy graph
    for edge in tqdm(
        graph.edges, unit="edge", unit_scale=True, desc="caching parents", leave=False
    ):
        if edge.pred in edge_types:
            hierarchy_graph.add_edge(edge.obj, edge.sub, color=COLORS[edge.pred])
            if edge.sub.startswith(prefix_colon) and not edge.obj.startswith(
                prefix_colon
            ):
                parents.add(edge.obj)
                children.add(edge.sub)
        elif edge.pred in edge_backwards:
            hierarchy_graph.add_edge(edge.sub, edge.obj, color=COLORS[edge.pred])
            if not edge.sub.startswith(prefix_colon) and edge.obj.startswith(
                prefix_colon
            ):
                parents.add(edge.sub)
                children.add(edge.obj)

    # Get root nodes that are from this ontology
    # For example, SYMP uses its own root.
    internal_roots = {
        node
        for node, degree in hierarchy_graph.in_degree()
        if not degree and node.startswith(prefix_colon)
    }

    ancestors = set(
        ancestor for node in parents for ancestor in nx.ancestors(hierarchy_graph, node)
    )

    tqdm.write(
        f"[{prefix}] got {len(parents)} parents, {len(ancestors)} ancestors of parents, {len(internal_roots)} roots, "
    )

    # find single children of parents
    add_children = set()
    for parent in parents:
        children = [
            child
            for child in hierarchy_graph.successors(parent)
            if child.startswith(prefix_colon)
        ]
        if len(children) < 8:
            add_children.update(children)
        else:
            tqdm.write(f"[{prefix}] too many children ({len(children)}) of {parent}")
            add_children.update(children[:3])
        # if all(c.startswith(prefix_colon) or c in parents for c in children):
        #    add_children.update(children)

    subgraph_nodes = set(internal_roots) | set(parents) | ancestors | add_children
    # if subgraph_nodes:
    #    MODULE.join(name=f"{prefix}_all.txt").write_text("\n".join(sorted(subgraph_nodes)))

    sg = hierarchy_graph.subgraph(subgraph_nodes).copy().reverse()
    for node in sg:
        sg.nodes[node]["label"] = f"{names[node]}\n{node}" if node in names else node
        if node in parents:
            sg.nodes[node]["color"] = "blue"
        elif node in internal_roots:
            sg.nodes[node]["color"] = "red"
        elif node in add_children:
            sg.nodes[node]["color"] = "orange"

    agraph = nx.nx_agraph.to_agraph(sg)
    agraph.draw(viz_path, prog="dot", format="svg")

    d = {
        "parents": sorted(parents),
        "roots": sorted(internal_roots),
        "children": sorted(add_children),
        "ancestors": sorted(ancestors),
    }

    path_stub.with_suffix(".json").write_text(
        json.dumps(
            d,
            indent=2,
            sort_keys=True,
        )
    )
    return d


@click.command()
def main():
    df = pd.read_csv(ERRORS_PATH, sep="\t")
    prefixes = sorted(df[df.message == NO_ROOTS_MSG].prefix)
    prefixes = [
        prefix
        for prefix in prefixes
        if bioregistry.get_resource(prefix).obofoundry["domain"]
           in {"anatomy and development", "phenotype"}
    ]
    it = tqdm(prefixes, desc="suggesting roots", unit="prefix")
    rows = []
    for prefix in it:
        it.set_postfix(prefix=prefix)
        row = analyze(prefix)
        rows.append({
            "prefix": prefix,
            "parents": len(row["parents"]),
            "roots": len(row["roots"]),
            "ancestors": len(row["ancestors"]),
            "children": len(row["children"]),
        })
    DATA.joinpath("results.yml").write_text(yaml.safe_dump(rows, indent=2))


if __name__ == "__main__":
    main()
