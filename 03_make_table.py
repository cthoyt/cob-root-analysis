#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "bioregistry>=0.13.64",
#     "pandas>=3.0.3",
#     "tabulate>=0.10.0",
# ]
# ///

import bioregistry
import pandas
import click
from tabulate import tabulate


@click.command()
def main() -> None:
    df = pandas.read_csv("errors.tsv", sep="\t")
    df = df[df["message"] == "no roots annotated with IAO_0000700"]
    rows = []
    for prefix in df.prefix:
        resource = bioregistry.get_resource(prefix, strict=True)
        if resource.obofoundry is None:
            raise
        domain = resource.obofoundry["domain"]
        if domain in {"phenotype", "anatomy and development"}:
            rows.append(
                (
                    domain,
                    f"[{prefix}](https://obofoundry.org/ontology/{prefix})",
                    resource.get_repository(),
                    f"![](https://cthoyt.com/cob-root-analysis/results/{prefix}_results.svg)",
                )
            )
    rows = sorted(rows)
    click.echo(
        tabulate(
            rows, headers=["domain", "prefix", "repository", "image"], tablefmt="github"
        )
    )


if __name__ == "__main__":
    main()
