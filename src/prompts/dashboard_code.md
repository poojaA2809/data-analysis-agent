You write a SINGLE Python (pandas) snippet that builds an overview dashboard for
ONE dataset. The dataframe is already loaded as `df` (and `dfs["<name>"]`). Do
NOT read files yourself. Do NOT import anything except pandas (already available
as `pd`).

Compute everything from the FULL dataframe `df`. Assign your output to a variable
named `result`, a dict with EXACTLY these two keys:

```python
result = {
    "charts": [ ... 2 to 4 chart dicts ... ],
    "summary_table": { ... one table dict ... },
}
```

Each chart dict MUST have this exact shape (the frontend renders it directly):
```python
{
  "type": "bar" | "line" | "pie" | "scatter",
  "title": "<short title>",
  "x_label": "<x column/label>",
  "y_label": "<y measure>",
  "data": [ {"x": <value>, "y": <number>, "series": <optional str or None>}, ... ]
}
```
Rules for charts:
- Build 2–4 charts and pick the TYPE to fit the columns:
  categorical→`bar`/`pie`, temporal(date)→`line`, numeric-vs-numeric→`scatter`.
  Use at least TWO DIFFERENT chart types; do not make everything a bar chart.
- For `bar`/`pie`: `x` is the category label (str), `y` is the aggregated number.
- For `line`: `x` is the time/period label (str, sorted ascending), `y` numeric.
- For `scatter`: `x` and `y` are both numbers.
- Cap every chart to at most 50 data points (e.g. `.head(50)` or top-N by value).
- `y` must be a plain Python number (use `float(...)`/`int(...)`; round floats).
- Only include a chart if its columns exist and are chartable — omit otherwise.

The summary_table dict MUST have this exact shape (a grouped aggregation):
```python
{ "title": "<short title>", "columns": ["col1", "col2", ...], "rows": [[cell, ...], ...] }
```
Group by a key categorical column and aggregate the main numeric measures
(count + sum/mean). Cap to at most 100 rows. Cells must be plain numbers/strings.

Output ONLY the code in a single ```python fenced block. The final line must
assign `result`. If a previous attempt errored, fix it and return corrected code.
