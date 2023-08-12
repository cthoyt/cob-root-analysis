import bioregistry
import pandas
from tabulate import tabulate

if __name__ == "__main__":
    df = pandas.read_csv("errors.tsv", sep="\t")
    df = df[df["message"] == "no roots annotated with IAO_0000700"]
    rows = []
    for prefix in df.prefix:
        resource = bioregistry.get_resource(prefix)
        domain = resource.obofoundry["domain"]
        if domain in {"phenotype", "anatomy and development"}:
            rows.append(
                (
                    domain,
                    f"[{prefix}](https://obofoundry.org/ontology/{prefix})",
                    resource.get_repository(),
                    f"![](https://cthoyt.com/cob-root-analysis/results/{prefix}_results.svg)"
                )
            )
    rows = sorted(rows)
    print(tabulate(rows, headers=["domain", "prefix", "repository", "image"], tablefmt="github"))
