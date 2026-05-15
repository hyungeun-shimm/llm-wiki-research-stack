# Mendeley Watch Folder

Use this folder as the future Mendeley watched folder.

Recommended Mendeley setting:

```text
<path-to-your-repo>/_system/mendeley/watch
```

Rules:

- Do not point Mendeley at its internal `userfiles` directory as a watched folder.
- Do not rename or move files inside Mendeley's internal `userfiles` directory.
- Let LLM-Wiki keep canonical PDFs in `papers/`.
- Copy selected canonical PDFs into this folder when you want Mendeley to import them.

After a paper is ingested into the wiki, run:

```bash
python3 scripts/sync_to_mendeley_watch.py --paper papers/{stem}.pdf
```
