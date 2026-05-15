---
project_slug: short-kebab-case-name
project_type: library_ingest
title: "What batch of papers are we adding?"
deadline: YYYY-MM-DD
lead: "Your name"
confidential_tier: external-ok
status: active
---

This is a library-ingest project: its only purpose is to add a batch of public papers to the wiki. Cloud agents read this file. Do not put unpublished hypotheses here.

## Goal

One sentence: what corpus segment is being added and why.

## Must-include keywords

(papers must mention at least one)

## Must-exclude keywords

(auto-reject)

## Year range

## Preferred sources

(arxiv, biorxiv, pubmed, semantic_scholar, gscholar — empty = all)

## Triage criteria

What makes a candidate IN-SCOPE for this ingest batch.

## Notes

- Scout outputs land in `candidates/`. Triage reports land in `triage-reports/`.
- Once all approved PDFs are ingested into the wiki, change `status: closed` in the frontmatter.
