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


@click.command()
@verbose_option
def main():
    prefixes = [
        resource.prefix
        for resource in bioregistry.resources()
        if resource.get_obofoundry_prefix() and not resource.is_deprecated()
    ]
    roots_rows = []
    roots_dict = {}
    missing = []
    it = tqdm(prefixes, unit="ontology")
    for prefix in it:
        it.set_postfix(prefix=prefix)
        parse_results = bioontologies.get_obograph_by_prefix(prefix)
        if not parse_results.graph_document:
            tqdm.write(f"[{prefix}] no graph document")
            missing.append((prefix, "no document"))
            continue
        graphs = parse_results.graph_document.graphs
        if 1 != len(graphs):
            tqdm.write(f"[{prefix}] has multiple graphs:")
            for i, graph in enumerate(graphs):
                tqdm.write(f"  - [{i}] {graph.id}")
            missing.append((prefix, "multiple graphs"))
            continue
        graph = graphs[0]
        if not graph.roots:
            missing.append((prefix, "no roots"))
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

        roots_dict[prefix] = {root: labels.get(root) for root in graph.roots}
        for root in graph.roots:
            roots_rows.append((prefix, root, labels.get(root)))

        # make outputs on all rows
        errors_df = pd.DataFrame(missing, columns=["prefix", "message"])
        errors_df.to_csv(ERRORS_PATH, sep="\t", index=False)

        results_df = pd.DataFrame(roots_rows, columns=["prefix", "root", "label"])
        results_df.to_csv(RESULTS_TSV_PATH, sep="\t", index=False)

        RESULTS_JSON_PATH.write_text(json.dumps(roots_dict, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
