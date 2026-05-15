# LLM Wiki + Project Research System

This repository is a local markdown research system built on top of [joonan30's LLM-Wiki gist](https://gist.github.com/joonan30/cbce305684d079dbe9a3fbaefe4e3959).

Start with:

- [README.md](README.md)
- [SYSTEM_OVERVIEW.svg](SYSTEM_OVERVIEW.svg)
- [Research_System_Training.pptx](_system/docs/Research_System_Training.pptx)
- [WIKI_VIEWING.md](_system/docs/WIKI_VIEWING.md)
- [OPERATIONS.md](_system/docs/OPERATIONS.md)
- [CLAUDE.md](CLAUDE.md)
- [AGENTS.md](AGENTS.md)
- [projects/_template/Project_Brief_TEMPLATE.md](projects/_template/Project_Brief_TEMPLATE.md)

The system now has three connected spaces:

- `Library`: durable memory in `papers/`, `sources/`, and `wiki/`
- `Exploration`: idea incubation in `explorations/`
- `Project`: deliverable workspaces in `projects/`

The wiki is the source of truth. Explorations and project folders can read from it, but they write back only through explicit promotion gates.
