---
layout: home
title: COB Root Analysis
---
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
<td>{{ row.prefix }}</td>
<td>
<a href="/results/{{ row.prefix }}_results.svg">
<img src="/results/{{ row.prefix }}_results.svg" alt="Analysis of {{ row.prefix }}" />
</a>
</td>
</tr>
{% endfor %}
</tbody>
</table>
