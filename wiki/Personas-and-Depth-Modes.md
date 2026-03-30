# Personas and Depth Modes

## How Personas Work

The persona is passed as a system prompt modifier to the Ollama LLM during the `consolidate_research` node. The same raw research data produces different outputs depending on which persona is active. The persona also affects source selection (e.g., `tech` and `pm` get GitHub README content and Stack Overflow full body; `news_editor` gets Reddit results filtered to last 24 hours).

## Persona Reference

### Generalista (`general`)
**Role:** Senior research analyst
**Style:** Professional, balanced, objective. Synthesizes across sources without bias toward any domain.
**Source behavior:** No special-case source handling.

### Analista de Mercado (`business`)
**Role:** Business strategist
**Style:** ROI-focused, commercial viability, strategic impact. Emphasizes market positioning, competitive landscape, and business model implications.
**Source behavior:** No special-case source handling.

### Arquitecto de Software (`tech`)
**Role:** Senior software architect (CTO perspective)
**Style:** Highly technical, implementation-focused. Includes architecture patterns, code examples, dependency analysis, and performance tradeoffs.
**Source behavior:**
- GitHub: fetches README content for top repositories
- Stack Overflow: full body text (not just title)

### Revisor Científico (`academic`)
**Role:** Scientific peer reviewer
**Style:** Rigorous, evidence-based. Prioritizes peer-reviewed sources (arXiv, Semantic Scholar). Explicit about methodology, limitations, and confidence levels.
**Source behavior:** No special-case source handling; arXiv/Scholar weighted higher in synthesis.

### Product Manager (`pm`)
**Role:** Product Manager
**Style:** User needs, viability, feature prioritization. Structures findings around "what does this enable for users" and "what is the build vs. buy tradeoff."
**Source behavior:**
- GitHub: fetches README content
- Stack Overflow: full body text

### Editor de Noticias (`news_editor`)
**Role:** Breaking news editor
**Style:** Immediacy, impact, clarity. Output is structured as Daily Digest + TL;DR. Recency is prioritized over depth.
**Source behavior:**
- Reddit: time range forced to "d" (last 24 hours)
- **Evaluation loop skipped entirely** — no quality re-plan step

## Research Depths

### Rápido (`quick`)
- Word count: 800–1500
- Structure: main points only
- Use case: quick orientation on an unfamiliar topic

### Estándar (`standard`)
- Word count: 2000–3500
- Structure: 3–5 key points, 2–4 paragraphs each, evidence from multiple sources
- Use case: decision-support research

### Profundo (`deep`)
- Word count: 3500–6000
- Structure: 3–5 key points, 3–5 paragraphs each, cross-source comparison, mandatory critical analysis section
- Use case: technical due diligence, literature review preparation

## Output Format Requirements (All Depths)

The LLM synthesis prompt enforces these regardless of persona or depth:

- Hierarchical structure: `##` sections, `###` subsections
- No numbered section titles (`1.`, `2.` prohibited for headings)
- Bullet points with `*` and indentation for detail
- Mandatory citation links: `[Title](URL)` format
- Mandatory "## Verificación de Datos" section: 3 most critical claims with source attribution

## LLM Output Processing

Raw LLM output is cleaned before storage:

```python
# Remove reasoning blocks (DeepSeek/Qwen3 chain-of-thought)
re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

# Extract content between report tags
re.search(r'<report>(.*?)</report>', text, re.DOTALL)

# Fallback: find Markdown anchors (## heading or "Resumen:")
# Final fallback: strip first 10 lines if they match preamble patterns

# Remove filler openings
r'^okay,?\s.*'
r'^entendido,?\s.*'
r'^analizando,?\s.*'
```

## Quality Evaluation

After synthesis, `evaluate_research_node()` runs a second LLM call that returns:

```json
{
  "sufficient": true,
  "gaps": [],
  "shallow_topics": ["implementation details"],
  "fact_check_queries": ["verify claim X"],
  "reasoning": "Coverage is adequate for standard depth"
}
```

If `sufficient == false` and `iteration_count < 2`: the system re-runs `plan_research_node()` with the evaluation report injected as context, then repeats parallel search and synthesis. The LLM can select different sources in the re-plan to fill identified gaps.

`news_editor` skips this node entirely.
