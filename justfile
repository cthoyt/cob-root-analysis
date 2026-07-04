build:
    # rm -rf docs/cache
    # rm -rf docs/results
    # rm errors.tsv results.json results.tsv
    uv run 01_get_roots.py
    uv run 02_annotate_roots.py
    uv run 03_make_table.py

serve:
    # Note that the 4.2.0 tag is important - 4.2.2 (latest, released ~2022) does not work.
    cd docs && docker run --rm --volume="$PWD:/srv/jekyll" -p 4000:4000 -it jekyll/jekyll:4.2.0 jekyll serve
