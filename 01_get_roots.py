"""Get roots that are annotated with IAO_0000700."""

import json
from pathlib import Path

import bioontologies
import bioregistry
import click
import pandas as pd
from more_click import verbose_option
from tqdm import tqdm

HERE = Path(__file__).parent.resolve()
RESULTS_TSV_PATH = HERE.joinpath("results.tsv")
RESULTS_JSON_PATH = HERE.joinpath("results.json")
ERRORS_PATH = HERE.joinpath("errors.tsv")

CANONICAL = {
    "cheminf": "http://semanticchemistry.github.io/semanticchemistry/ontology/cheminf.owl",
    "dideo": "http://purl.obolibrary.org/obo/dideo/release/2022-06-14/dideo.owl",
    "micro": "http://purl.obolibrary.org/obo/MicrO.owl",
    "ogsf": "http://purl.obolibrary.org/obo/ogsf-merged.owl",
    "mfomd": "http://purl.obolibrary.org/obo/MF.owl",
    "one": "http://purl.obolibrary.org/obo/ONE",
    "ons": "https://raw.githubusercontent.com/enpadasi/Ontology-for-Nutritional-Studies/master/ons.owl",
}
SKIP = {
    "ncbitaxon",
}
NO_ROOTS_MSG = "no roots annotated with IAO_0000700"


@click.command()
@verbose_option
def main():
    errors = pd.read_csv(ERRORS_PATH, sep="\t")
    error_prefixes = set(errors[errors["message"] == NO_ROOTS_MSG].prefix)

    roots = json.loads(RESULTS_JSON_PATH.read_text())
    prefixes = [
        (resource.prefix, resource.get_obofoundry_prefix())
        for resource in bioregistry.resources()
        if (
            resource.get_obofoundry_prefix()
            and not resource.is_deprecated()
            and resource.prefix not in roots
            and resource.prefix not in SKIP
        )
    ]
    missing = []
    it = tqdm(prefixes, unit="ontology")
    for prefix, obo_prefix in it:
        it.set_postfix(prefix=obo_prefix)

        if prefix in error_prefixes:
            missing.append((prefix, NO_ROOTS_MSG))
            continue

        try:
            parse_results = bioontologies.get_obograph_by_prefix(prefix)
        except TypeError:
            tqdm.write(f"[{prefix}] malformed data")
            missing.append((prefix, "malformed data"))
            continue

        if not parse_results.graph_document:
            tqdm.write(f"[{prefix}] no graph document")
            missing.append((prefix, "no document"))
            continue

        graphs = parse_results.graph_document.graphs
        if 1 == len(graphs):
            graph = graphs[0]
        else:
            id_to_graph = {graph.id: graph for graph in graphs}
            standard_id = f"http://purl.obolibrary.org/obo/{obo_prefix.lower()}.owl"
            if standard_id in id_to_graph:
                graph = id_to_graph[standard_id]
            elif prefix in CANONICAL and CANONICAL[prefix] in id_to_graph:
                graph = id_to_graph[CANONICAL[prefix]]
            else:
                tqdm.write(f"[{prefix}] has multiple graphs:")
                for i, graph in enumerate(graphs):
                    tqdm.write(f"  - [{i}] {graph.id}")
                missing.append((prefix, "multiple graphs"))
                continue

        if not graph.roots:
            missing.append((prefix, NO_ROOTS_MSG))
            continue

        labels = {
            node.id: node.lbl
            for node in tqdm(
                graph.nodes,
                desc=f"caching {prefix} labels",
                unit="term",
                unit_scale=True,
            )
            if node.lbl
        }
        roots[prefix] = {root: labels.get(root) for root in graph.roots}

    # make outputs on all rows
    errors_df = pd.DataFrame(missing, columns=["prefix", "message"])
    errors_df.to_csv(ERRORS_PATH, sep="\t", index=False)

    roots_rows = [
        (
            prefix,
            root.removeprefix("http://purl.obolibrary.org/obo/").replace("_", ":"),
            root_label,
        )
        for prefix, data in sorted(roots.items())
        for root, root_label in sorted(data.items())
    ]
    results_df = pd.DataFrame(roots_rows, columns=["prefix", "root", "label"])
    results_df.to_csv(RESULTS_TSV_PATH, sep="\t", index=False)

    RESULTS_JSON_PATH.write_text(json.dumps(roots, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
