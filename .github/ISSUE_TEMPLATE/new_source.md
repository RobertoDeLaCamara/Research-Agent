---
name: New Research Source
about: Propose or contribute a new information source
title: '[SOURCE] '
labels: enhancement, good first issue
assignees: ''
---

**Source name and URL**
E.g., PubMed — https://pubmed.ncbi.nlm.nih.gov/

**What type of content does it provide?**
E.g., biomedical research papers, news articles, academic preprints...

**Is there a Python library or public API?**
E.g., `biopython`, REST API with no auth required...

**Which personas would benefit most?**
- [ ] Product Manager
- [ ] Software Architect
- [ ] Market Analyst
- [ ] Scientific Reviewer
- [ ] Generalist

**Implementation notes**
The pattern to follow is in `src/tools/research_tools.py`. Each source is a function that takes an `AgentState` and returns a dict with a `<source>_results` key. Adding a new one is ~50 lines including error handling.
