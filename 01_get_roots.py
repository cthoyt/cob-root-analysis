#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "bioontologies>=0.8.3",
#     "bioregistry>=0.13.64",
#     "click>=8.4.2",
#     "curies",
#     "curies-processing",
#     "more-click>=0.1.3",
#     "pandas>=3.0.3",
#     "robot-obo-tool>=0.0.1",
#     "tqdm>=4.68.3",
#     "pystow>=0.8.21",
# ]
#
# [tool.uv.sources]
# bioregistry = { path = "../bioregistry" }
# curies = { path = "../curies" }
# curies-processing = { path = "../curies-processing" }
# bioontologies = { path = "../bioontologies" }
# ///

"""Get roots that are annotated with IAO:0000700."""

import json
from pathlib import Path
import obographs
import bioontologies
import bioregistry
import click
from robot_obo_tool import ROBOTError
from tqdm.contrib.logging import logging_redirect_tqdm
import pandas as pd
from more_click import verbose_option, force_option
from tqdm import tqdm
from pystow.utils import write_pydantic_json

HERE = Path(__file__).parent.resolve()
RESULTS_TSV_PATH = HERE.joinpath("results.tsv")
RESULTS_JSON_PATH = HERE.joinpath("results.json")
ERRORS_PATH = HERE.joinpath("errors.tsv")

CACHE_DIR = HERE.joinpath("docs", "cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

#: manual overrides for when the graph's IRI is not clearly inferrable by the prefix
CANONICAL_GRAPH_IRI = {
    "cheminf": "http://semanticchemistry.github.io/semanticchemistry/ontology/cheminf.owl",
    "dideo": "http://purl.obolibrary.org/obo/dideo/release/2022-06-14/dideo.owl",
    "micro": "http://purl.obolibrary.org/obo/MicrO.owl",
    "ogsf": "http://purl.obolibrary.org/obo/ogsf-merged.owl",
    "mfomd": "http://purl.obolibrary.org/obo/MF.owl",
    "one": "http://purl.obolibrary.org/obo/ONE",
    "ons": "https://raw.githubusercontent.com/enpadasi/Ontology-for-Nutritional-Studies/master/ons.owl",
    "geogeo": "http://purl.obolibrary.org/obo/geo.owl",
}
SKIP = {
    "ncbitaxon",# big
    "ncit", #big
    "chebi", # big
    "gaz", # big
    "epio", # garb
    "interpro", # irrelevant
}
NO_ROOTS_MSG = "no roots annotated with IAO_0000700"
DOMAINS = {
    "anatomy and development",
    "phenotype",
}


@click.command()
@force_option
@verbose_option
def main(force: bool) -> None:
    if ERRORS_PATH.is_file() and not force:
        errors = pd.read_csv(ERRORS_PATH, sep="\t")
        error_prefixes = set(errors[errors["message"] == NO_ROOTS_MSG].prefix)
    else:
        error_prefixes = set()

    if RESULTS_JSON_PATH.is_file() and not force:
        prefix_to_roots = json.loads(RESULTS_JSON_PATH.read_text())
    else:
        prefix_to_roots = {}

    prefixes: list[tuple[str, str]] = [
        (resource.prefix, resource, obo_prefix)
        for resource in bioregistry.resources()
        if (
            (obo_prefix := resource.get_obofoundry_prefix())
            and not resource.is_deprecated()
            and resource.prefix not in prefix_to_roots
            and resource.prefix not in SKIP
            # and resource.obofoundry["domain"] in DOMAINS
        )
    ]
    missing = []
    it = tqdm(prefixes, unit="ontology", desc="Extracting roots")
    for prefix, resource, obo_prefix in it:
        it.set_postfix(prefix=obo_prefix)

        if prefix in error_prefixes:
            missing.append((prefix, obo_prefix,
                    resource.get_name(),
                    resource.get_repository(),NO_ROOTS_MSG))
            continue

        try:
            with logging_redirect_tqdm():
                parse_results = bioontologies.get_obograph_by_prefix(
                    prefix, check=False
                )
        except (TypeError, ROBOTError):
            tqdm.write(f"[{prefix}] malformed data")
            missing.append((prefix, obo_prefix,
                    resource.get_name(),
                    resource.get_repository(),"malformed data"))
            continue

        if not parse_results.graph_document:
            tqdm.write(f"[{prefix}] no graph document")
            missing.append((prefix,obo_prefix,
                    resource.get_name(),
                    resource.get_repository(), "no document"))
            continue

        graphs: list[obographs.Graph] = parse_results.graph_document.graphs
        if 1 == len(graphs):
            graph = graphs[0]
        else:
            id_to_graph = {graph.id: graph for graph in graphs}
            standard_id = f"http://purl.obolibrary.org/obo/{obo_prefix.lower()}.owl"
            if standard_id in id_to_graph:
                graph = id_to_graph[standard_id]
            elif (
                prefix in CANONICAL_GRAPH_IRI
                and CANONICAL_GRAPH_IRI[prefix] in id_to_graph
            ):
                graph = id_to_graph[CANONICAL_GRAPH_IRI[prefix]]
            else:
                tqdm.write(f"[{prefix}] has multiple graphs:")
                for i, graph in enumerate(graphs):
                    tqdm.write(f"  - [{i}] {graph.id}")
                missing.append((prefix, "multiple graphs"))
                continue

        write_pydantic_json(graph, CACHE_DIR.joinpath(prefix).with_suffix(".json"), indent=2, exclude_unset=True, exclude_none=True, exclude_defaults=True)

        if not graph.roots:
            missing.append(
                (
                    prefix,
                    obo_prefix,
                    resource.get_name(),
                    resource.get_repository(),
                    NO_ROOTS_MSG,
                )
            )
            continue

        node_uri_to_label = {node.id: node.lbl for node in graph.nodes if node.lbl}
        prefix_to_roots[prefix] = {
            root: node_uri_to_label.get(root) for root in graph.roots
        }

    # make outputs on all rows
    errors_df = pd.DataFrame(
        missing, columns=["prefix", "obo", "name", "repository", "message"]
    )
    errors_df.to_csv(ERRORS_PATH, sep="\t", index=False)

    roots_rows = [
        (
            prefix,
            root.removeprefix("http://purl.obolibrary.org/obo/").replace("_", ":"),
            root_label,
        )
        for prefix, roots in sorted(prefix_to_roots.items())
        for root, root_label in sorted(roots.items())
    ]
    results_df = pd.DataFrame(roots_rows, columns=["prefix", "root", "label"])
    results_df.to_csv(RESULTS_TSV_PATH, sep="\t", index=False)

    RESULTS_JSON_PATH.write_text(json.dumps(prefix_to_roots, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
