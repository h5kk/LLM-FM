# Image Incorporation Plan

## Constraint: GitHub Gists vs Repos

GitHub gists don't support image uploads or relative image paths. Two options:

1. **Commit images to the repo and use raw GitHub URLs** — images in `images/` are accessible via `https://raw.githubusercontent.com/h5kk/LLM-FM/main/images/...`. Gists can reference these URLs. This is the simplest and keeps images version-controlled.
2. **Upload to GitHub Issues** — drag an image into a dummy issue comment, grab the `user-images.githubusercontent.com` URL. Works but images are orphaned if the issue is deleted.

**Recommendation:** Option 1. Commit `images/` to the repo, reference via raw URLs in both README and gists.

### URL Pattern

```
https://raw.githubusercontent.com/h5kk/LLM-FM/main/images/{filename}
```

Note: filenames with spaces need URL encoding (`%20`).

---

## README Incorporation

The README is the landing page. It should use 3-4 images max — enough to convey the value prop and architecture without overwhelming.

### Placement

| Section | Image | Why |
|---------|-------|-----|
| **Top (after "The Problem")** | `value.png` | Hero image. Immediately answers "why should I care?" with the 20min vs 40sec comparison. |
| **Architecture** | `Three-Layer Architecture.png` | Replaces the bullet-point architecture list with a visual mental model. |
| **How It Works** | `Hook lifecycle.png` | Replaces the hooks table with a richer visual showing the cost tiers. |
| **Test Results** | `feature page anatomy.png` | Shows what FM actually produces — makes the abstract concrete. |

### Implementation

```markdown
## The Problem
...existing text...

![20 minutes of manual investigation vs 40 seconds with Feature Memory](images/value.png)

## How It Works
...directory structure...

![Five-stage hook lifecycle from File Edit to Nightly](images/Hook%20lifecycle.png)

## Architecture
![Three-layer architecture: source code, compiled docs, consumers](images/Three-Layer%20Architecture.png)

## What a Feature Page Looks Like
![Annotated Feature Memory page showing metadata, summaries, source map](images/feature%20page%20anatomy.png)
```

---

## Gist Incorporation

### `feature-memory-gist-minimal.md` (2-minute overview)

This gist is short and punchy. Add **2 images**:

| After section | Image | Purpose |
|---------------|-------|---------|
| "The problem" | `value.png` | Hook the reader immediately |
| "Structure" | `project structure example.png` | Show where FM lives in a real project |

### `feature-memory-gist.md` (full concept)

This gist is the detailed walkthrough. Add **5-6 images** at key explanation points:

| After section | Image | Purpose |
|---------------|-------|---------|
| "The core idea" | `value.png` | Hero / hook |
| "The shape of it" | `Three-Layer Architecture.png` | Replace or supplement the ASCII art layers diagram |
| "What a feature page looks like" | `feature page anatomy.png` | Visual companion to the markdown code block |
| "Hooks are the maintenance engine" | `Hook lifecycle.png` | Supplement the hook timeline text |
| After mermaid data flow diagram | `data pipeline.png` | Show FM vs prior art positioning |
| After changelog section | `ChangelogRaw vs Synthesized.png` | Before/after changelog quality |

### `feature-memory-gist-ar.md` (architecture review)

This is the technical deep-dive. Add **4 images**:

| After section | Image | Purpose |
|---------------|-------|---------|
| Architecture overview | `Three-Layer Architecture.png` | Visual anchor for the three-layer model |
| Hooks discussion | `Hook lifecycle.png` | Cost-tier visual |
| Quality/lint section | `Lint  Review Pipeline.png` | Two-phase QA pipeline |
| Cross-references | `Cross-Reference Propagation.png` | Shared dependency propagation |

---

## Filename Cleanup (Optional)

Current filenames have spaces which require URL encoding. Consider renaming for cleaner URLs:

| Current | Proposed |
|---------|----------|
| `ChangelogRaw vs Synthesized.png` | `changelog-raw-vs-synthesized.png` |
| `Cross-Reference Propagation.png` | `cross-reference-propagation.png` |
| `Hook lifecycle.png` | `hook-lifecycle.png` |
| `Lint  Review Pipeline.png` | `lint-review-pipeline.png` |
| `Three-Layer Architecture.png` | `three-layer-architecture.png` |
| `data pipeline.png` | `data-pipeline.png` |
| `feature page anatomy.png` | `feature-page-anatomy.png` |
| `project structure example.png` | `project-structure-example.png` |
| `value.png` | `value.png` (already clean) |

This is optional but makes markdown references cleaner and less error-prone.

---

## Execution Steps

1. **Rename images** (optional but recommended) — `git mv` each file to kebab-case
2. **Commit images** to the repo — `git add images/ && git commit`
3. **Update README.md** — insert image references at the 4 placement points above
4. **Update gists** — add image references using raw GitHub URLs
5. **Push** — `git push` to make raw URLs resolve
6. **Verify** — check that images render in the README and gists on GitHub
