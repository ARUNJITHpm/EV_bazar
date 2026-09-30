# Writing for Chargeworthy Data

Answer one question per post. Use plain language and explain every technical term on first use. Every factual claim must point to a chart or source on the page. State the reporting period and distinguish source retrieval dates from article updates. Historical references do not describe today's boundaries.

Estimates always show P10/P50/P90 with units and sample size; explain the range before interpreting it. Missing and suppressed observations are never zero. Use Indian number formatting. Keep money in integer paise until the shared formatter renders rupees; distinguish kWh, kW and kVA.

Avoid hype words, exclamation marks and promotion of any operator. Do not rank operators or expose private station records. Never make independence or ownership claims without verified evidence. Original writing and charts use CC BY 4.0; source datasets keep their own licences.

## Authoring and review

Store reviewed Markdown under `frontend/content/analytics/insights/` or `weekly/`. The filename is the route slug. Front matter between `---` delimiters is a JSON object (a YAML-compatible subset). The build validates it; it never executes MDX or HTML. Supported body blocks are paragraphs, `##` headings, `-` lists, and inline `[text](https://source)` or `/data` links. Separate blocks with a blank line. No images, raw HTML, JavaScript or arbitrary imports are allowed.

Insights require title, question, summary, vertical, authors, published_on, updated_on, datasets and changelog (date and entry). Include at least two chart blocks, for example:

```text
:::chart {"dataset":"district_reference","kind":"by-state"}
```

Weekly front matter requires a question title, published_on, vertical, dataset, chart configuration and social_caption shorter than 300 characters. Its single chart is generated from front matter; do not add chart blocks. The explanation must have at most 150 whitespace-separated words, including links. The build rejects an extra chart or unsupported dataset.

The initial chart adapter supports only the verified archived district reference, with `total` and `by-state` configurations. Counts are calculated from validated records, never entered in Markdown. Adding another dataset requires an explicit reviewed adapter, units, sources, licence, versions and null/range handling. Fixture, missing and private datasets cannot publish articles.

Review every claim and source manually before committing content. Dates must be real calendar dates; updated_on cannot precede publication, and the latest update needs a matching changelog entry. Record what changed and why, retaining earlier entries. Changing a source may change a rebuilt chart: review affected articles and update their dates and changelogs together.

## Reader checks

Check text, dates, chart tables and source attribution with JavaScript disabled. With JavaScript enabled, check chart/table switching, CSV download, URL filters and keyboard focus at mobile and desktop widths. Verify that only reviewed public content and validated datasets reach the production bundle.
