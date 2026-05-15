# Push Checklist — Before You Push to Public Repo

This template directory (`_public_template/`) contains the **clean, generalized core files** safe for a public repo. But your system also has `scripts/`, `subagents/`, and `_system/docs/` that you'll want to include — those need a quick scrub.

## What this folder already gives you (push as-is)

- `CLAUDE.md` — generalized
- `AGENTS.md` — generalized
- `CLAUDE.local.md.example` — template for personal overrides
- `README.md`
- `SETUP.md`
- `.gitignore` — comprehensive

## What you still need to copy from your live repo (after scrubbing)

| Source | Action |
|---|---|
| `scripts/` | Review each `.py` file for hardcoded domain-specific terms, personal identifiers, and absolute paths. Replace with placeholders or read from `CLAUDE.local.md`. |
| `subagents/` | Same scrub. Especially `subagents/11-scout-brief.md` flagged. |
| `_system/docs/` | Scrub `WIKI_VIEWING.md`, `OPERATIONS.md`, `README.md`. |
| `_system/dashboard/` | Check for hardcoded paths and personal info. |
| `projects/_template/` | Should already be generic — verify. |
| `explorations/_template/` | Should already be generic — verify. |
| `requirements.txt` | Make sure it exists; if not, create from your current Python env. |

## Files flagged earlier with personal references (must scrub)

```
subagents/11-scout-brief.md
scripts/build_dashboard.py
scripts/audit_mendeley_export.py
scripts/mendeley_apply_collections.py
scripts/pre_drafter.py
scripts/ingest_{author}_batch.py            # rename or delete (lab-specific)
scripts/refine_{author}_wiki_links.py       # rename or delete (lab-specific)
scripts/resolve_citations.py
_system/docs/WIKI_VIEWING.md
_system/docs/README.md
_system/docs/OPERATIONS.md
```

Quick scrub command (review output before deleting):

```bash
grep -rn -i -E "your-domain-term|your-identifier|/Users/your-username" \
  scripts/ subagents/ _system/docs/ projects/_template/ explorations/_template/ \
  2>/dev/null
```

## NEVER push these (already in .gitignore, but double-check)

- `papers/*.pdf` — copyright
- `sources/*.md` — paper summaries (gray-area copyright)
- `wiki/*/*.md` — your accumulated knowledge
- `index.md` — reveals your reading list
- `explorations/active/` — exploration content
- `projects/{slug}/` — confidential project work
- `_system/mendeley/export/library.bib` — personal metadata
- `CLAUDE.local.md` — personal overrides
- `homework/`, `working/` — scratch
- `SYSTEM_OVERVIEW.svg` — check if it has personal info in labels

## Git history cleanup

If your existing public repo already has commits referencing your specific research, do one of:

**Option A: Fresh repo (simplest, recommended)**
```bash
# 1. Create new GitHub repo (e.g., llm-wiki-template-clean)
# 2. Init clean local copy:
mkdir ~/llm-wiki-public && cd ~/llm-wiki-public
git init
# 3. Copy template files + scrubbed scripts/subagents/_system/docs
cp -r /path/to/your-repo/_public_template/. .
# 4. Add scrubbed scripts/, subagents/, _system/docs/, projects/_template/, explorations/_template/
# 5. git add . && git commit -m "Initial public template"
# 6. git remote add origin <new-repo-url>
# 7. git push -u origin main
# 8. Delete or archive the old public repo
```

**Option B: Rewrite history (riskier)**
```bash
# In existing repo:
git filter-repo --replace-text expressions.txt   # see git-filter-repo docs
git push --force
# Then delete cached old commits from GitHub: Settings → Danger Zone → ... 
# Note: forks and clones may still have the old history
```

Option A is safer because forks of the old repo can't expose old commits.

## Final verification before push

```bash
cd <new-clean-repo>
grep -rn -i -E "your-domain-term|your-identifier|/Users/your-username" .
# Should return nothing
ls papers/ sources/ wiki/*/ 2>/dev/null
# Should be empty (only .gitkeep files)
git status
git log --oneline
# Single clean initial commit
```
