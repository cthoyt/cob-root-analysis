---
layout: home
title: COB Root Analysis
---
The following diagrams show the hierarchy in OBO Foundry ontologies that
live above the ontology-specific terms. The point of making these diagrams
was to figure out what are the *logical* root terms in each ontology, and
which upper-level parts aren't actually useful in browsers like the OLS.

How to read the following diagrams:

- blue nodes represent the parents of ontology-specific terms
- red nodes represent ontology terms. Some are children of blue nodes, and some
  are themselves roots of the ontology - these appear to not be aligned with an
  upper structure like BFO!
- black nodes represent hierarchical parents (like BFO)

<table>
<thead>
<tr>
<th>Prefix</th>
<th>Image</th>
</tr>
</thead>
<tbody>
{% for row in site.data.results %}
<tr>
<td><a href="{{ row.link }}">{{ row.prefix }}</a></td>
<td>
<a href="/results/{{ row.prefix }}_results.svg">
<img src="/results/{{ row.prefix }}_results.svg" alt="Analysis of {{ row.prefix }}" />
</a>
</td>
</tr>
{% endfor %}
</tbody>
</table>
