#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "bioontologies>=0.8.3",
#     "bioregistry>=0.13.64",
#     "curies>=0.14.1",
#     "click>=8.4.2",
#     "networkx>=3.6.1",
#     "pandas>=3.0.3",
#     "pygraphviz>=2.0",
#     "pyyaml>=6.0.3",
#     "tqdm>=4.68.3",
#     "pystow>=0.8.21",
#     "curies-processing>=0.1.6",
# ]
#
# [tool.uv.sources]
# bioregistry = { path = "../bioregistry" }
# curies = { path = "../curies" }
# curies-processing = { path = "../curies-processing" }
# bioontologies = { path = "../bioontologies" }
# ///

"""Identify roots that are not annotated."""

from __future__ import annotations
import curies
from pystow.utils import write_pydantic_json
from pydantic import BaseModel
import curies_processing
from curies import Reference
from pystow.utils import read_pydantic_json
from pathlib import Path

import bioontologies
import bioregistry
from curies import vocabulary as v
import click
import networkx as nx
from pystow.utils import write_pydantic_yaml
import obographs
import pandas as pd
from tqdm import tqdm

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

edge_types: set[Reference] = {
    v.subclass_of,
    v.part_of,
    v.derives_from,
    v.contained_in,
}
COLORS: dict[Reference, str] = {
    v.subclass_of: "black",
    v.part_of: "blue",
    v.has_part: "blue",
    v.derives_from: "purple",
    v.contained_in: "purple",
}


class AnalysisLists(BaseModel):
    """Statistics from analysis."""

    parents: list[Reference]
    roots: list[Reference]
    ancestors: list[Reference]
    children: list[Reference]


class Row(BaseModel):
    prefix: str
    link: str | None
    stats: AnalysisLists
    parents: int
    roots: int
    ancestors: int
    children: int


class Results(BaseModel):
    rows: list[Row]


def analyze(
    prefix: str, *, converter: curies.Converter
) -> AnalysisLists | None:
    path_stub = RESULTS.joinpath(f"{prefix}_results")
    viz_path = path_stub.with_suffix(".svg")

    tqdm.write(click.style(prefix, fg="green", bold=True))
    json_cache_path = CACHE.joinpath(prefix).with_suffix(".json")
    graph_raw = read_pydantic_json(json_cache_path, obographs.Graph)
    try:
        graph = graph_raw.standardize(converter=converter)
    except Exception:
        tqdm.write(click.style(f"{prefix} failed to standardize", fg="red", bold=True))
        return None
    names = {node.reference: node.label for node in graph.nodes if node.label}

    prefix = converter.standardize_prefix(prefix, strict=True)


    # Get all nodes that are parents of nodes in this
    # ontology, but are not themselves in this ontology
    parents: set[Reference] = set()
    # children = set()
    hierarchy_graph: nx.DiGraph[Reference] = nx.DiGraph()  # hierarchy graph
    for edge in tqdm(
        graph.edges, unit="edge", unit_scale=True, desc="caching parents", leave=False
    ):
        if edge.predicate in edge_types:
            hierarchy_graph.add_edge(
                edge.object, edge.subject, color=COLORS.get(edge.predicate, "grey")
            )
            if edge.subject.prefix == prefix and edge.object.prefix != prefix:
                parents.add(edge.object)
                # children.add(edge.subject)
        elif inverse_predicate := v.inversions.get(edge.predicate):
            hierarchy_graph.add_edge(
                edge.subject, edge.object, color=COLORS.get(inverse_predicate, "grey")
            )
            if edge.subject.prefix != prefix and edge.object.prefix == prefix:
                parents.add(edge.subject)
                # children.add(edge.object)

    # Get root nodes that are from this ontology
    # For example, SYMP uses its own root.
    internal_roots: set[Reference] = {
        node
        for node, degree in hierarchy_graph.in_degree()
        if not degree and node.prefix == prefix
    }

    ancestors: set[Reference] = set(
        ancestor for node in parents for ancestor in nx.ancestors(hierarchy_graph, node)
    )

    tqdm.write(
        f"[{prefix}] got {len(parents)} parents, {len(ancestors)} ancestors of parents, {len(internal_roots)} roots, "
    )

    # find single children of parents
    add_children: set[Reference] = set()
    for parent in parents:
        local_children = [
            child
            for child in hierarchy_graph.successors(parent)
            if child.prefix == prefix
        ]
        if len(local_children) < 8:
            add_children.update(local_children)
        else:
            tqdm.write(
                f"[{prefix}] too many children ({len(local_children)}) of {parent.curie}"
            )
            add_children.update(local_children[:3])
        # if all(c.startswith(prefix_colon) or c in parents for c in children):
        #    add_children.update(children)

    subgraph_nodes = set(internal_roots) | set(parents) | ancestors | add_children
    # if subgraph_nodes:
    #    MODULE.join(name=f"{prefix}_all.txt").write_text("\n".join(sorted(subgraph_nodes)))

    sg = hierarchy_graph.subgraph(subgraph_nodes).copy().reverse()
    for node in sg:
        sg.nodes[node]["label"] = (
            f"{names[node]}\n{node.curie}" if node in names else node.curie
        )
        if node in parents:
            sg.nodes[node]["color"] = "blue"
        elif node in internal_roots:
            sg.nodes[node]["color"] = "red"
        elif node in add_children:
            sg.nodes[node]["color"] = "red"

    if sg.number_of_nodes() > 1:
        agraph = nx.nx_agraph.to_agraph(sg)
        agraph.draw(viz_path, prog="dot", format="svg")

    d = AnalysisLists.model_validate(
        {
            "parents": sorted(parents),
            "roots": sorted(internal_roots),
            "children": sorted(add_children),
            "ancestors": sorted(ancestors),
        }
    )

    write_pydantic_json(
        d,
        path_stub.with_suffix(".json"),
        indent=2,
        exclude_none=True,
        exclude_unset=True,
    )
    return d


@click.command()
def main() -> None:
    df = pd.read_csv(ERRORS_PATH, sep="\t")
    converter = curies_processing.wrap(bioregistry.get_preferred_converter())
    resources = [
        bioregistry.get_resource(prefix)
        for prefix in sorted(df[df.message == NO_ROOTS_MSG].prefix)
    ]
    prefixes = [
        resource.prefix for resource in resources if not resource.is_deprecated()
    ]
    it = tqdm(prefixes, desc="suggesting roots", unit="prefix")
    rows = []
    for prefix in it:
        it.set_postfix(prefix=prefix)
        row = analyze(prefix, converter=converter)
        if not row:
            continue
        rows.append(
            Row(
                prefix=prefix,
                link=bioregistry.get_repository(prefix),
                stats=row,
                parents=len(row.parents),
                roots=len(row.roots),
                ancestors=len(row.ancestors),
                children=len(row.children),
            )
        )
    write_pydantic_yaml(Results(rows=rows), DATA.joinpath("results.yml"), indent=2)


if __name__ == "__main__":
    main()
