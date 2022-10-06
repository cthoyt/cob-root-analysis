"""Identify roots that are not annotated"""

from pathlib import Path

import bioontologies
import click
import networkx as nx
import pandas as pd
import pystow
from tqdm import tqdm
from tqdm.auto import tqdm

HERE = Path(__file__).parent.resolve()
ERRORS_PATH = HERE.joinpath("errors.tsv")
NO_ROOTS_MSG = "no roots annotated with IAO_0000700"
MODULE = pystow.module("bioregistry", "analysis", "roots")

edge_types = {
    "rdfs:subClassOf",
    "bfo:0000050",
}
edge_backwards = {
    "bfo:0000051",
}


def analyze(prefix: str):
    viz_path = MODULE.join(name=f"{prefix}.pdf")
    if viz_path.is_file():
        return

    parse_results = bioontologies.get_obograph_by_prefix(prefix)
    try:
        graph = parse_results.guess(prefix).standardize()
    except ValueError as e:
        tqdm.write(f"[{prefix} could not guess: {e}")
        return
    names = graph.get_curie_to_name()

    prefix_colon = f"{prefix}:"

    # Get all nodes that are parents of nodes in this
    # ontology, but are not themselves in this ontology
    parents = set()
    hierarchy_graph = nx.DiGraph()  # hierarchy graph
    for edge in tqdm(graph.edges, unit="edge", unit_scale=True, desc="caching parents"):
        if edge.pred in edge_types:
            hierarchy_graph.add_edge(edge.obj, edge.sub)
            if edge.sub.startswith(prefix_colon) and not edge.obj.startswith(prefix_colon):
                parents.add(edge.obj)
        elif edge.pred in edge_backwards:
            hierarchy_graph.add_edge(edge.sub, edge.obj)
            if not edge.sub.startswith(prefix_colon) and edge.obj.startswith(prefix_colon):
                parents.add(edge.sub)
    tqdm.write(f"[{prefix}] got {len(parents)} parents")
    if parents:
        MODULE.join(name=f"{prefix}_parents.txt").write_text("\n".join(sorted(parents)))

    # Get root nodes that are from this ontology
    # For example, SYMP uses its own root.
    roots = {
        node for node, degree in hierarchy_graph.in_degree() if not degree and node.startswith(prefix_colon)
    }
    tqdm.write(f"[{prefix}] got {len(roots)} roots")
    if roots:
        MODULE.join(name=f"{prefix}_roots.txt").write_text("\n".join(sorted(roots)))

    ancestors = set(
        ancestor for parent in parents for ancestor in nx.ancestors(hierarchy_graph, parent)
    )
    tqdm.write(f"[{prefix}] got {len(ancestors)} ancestors of parents")
    if ancestors:
        MODULE.join(name=f"{prefix}_ancestors.txt").write_text("\n".join(sorted(ancestors)))

    subgraph_nodes = set(roots) | set(parents) | ancestors
    if subgraph_nodes:
        MODULE.join(name=f"{prefix}_all.txt").write_text("\n".join(sorted(subgraph_nodes)))

    sg = hierarchy_graph.subgraph(subgraph_nodes).copy().reverse()
    for node in sg:
        sg.nodes[node]["label"] = f"{names[node]}\n{node}" if node in names else node
        if node in parents:
            sg.nodes[node]["color"] = "blue"
        elif node in roots:
            sg.nodes[node]["color"] = "red"

    agraph = nx.nx_agraph.to_agraph(sg)
    agraph.draw(viz_path, prog="dot")


@click.command()
def main():
    df = pd.read_csv(ERRORS_PATH, sep="\t")
    prefixes = sorted(df[df.message == NO_ROOTS_MSG].prefix)
    for prefix in tqdm(prefixes, desc="suggesting roots", unit="prefix"):
        analyze(prefix)


if __name__ == "__main__":
    main()
