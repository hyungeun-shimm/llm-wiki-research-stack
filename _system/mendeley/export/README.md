# Mendeley Export

Place Mendeley metadata exports here, usually `library.bib` or `library.ris`.

This folder is private and ignored by git except for this README. Export from Mendeley Reference Manager, then run:

```bash
python3 scripts/audit_mendeley_export.py --bib _system/mendeley/export/library.bib --pdf-root "<MENDELEY_USERFILES_PATH>" --out _system/mendeley/review
```

Do not treat this export as the source of truth for the wiki. It is an audit input used to decide which papers should be curated into `papers/`, `sources/`, and `wiki/`.
