# ADR 0013: Cursor as a third host

**Status:** accepted (2026-11-18). Amends PRD NG-05 and §18.

## Context

Cursor (the editor's Agent and the `cursor-agent` / `agent` CLI) loads Agent Skills and has its own plugin format. These facts come from the Cursor docs, checked on 2026-11-18:

- **Skills** load from:
  - project folders: `.cursor/skills/`, `.agents/skills/`;
  - user folders: `~/.cursor/skills/`, `~/.agents/skills/`;
  - Claude and Codex folders (`.claude/skills/`, `~/.claude/skills/`, `.codex/skills/`, `~/.codex/skills/`), through the "Include Third-Party Plugins, Skills, and Other Configs" setting, which is on by default.
- **Skill frontmatter.** `name` must match the folder, and `description` is required. Cursor warns above 1,024 description characters or about 5,000 body tokens. `SKILL.md` is about 790 description characters and about 2,400 body tokens.
- **Plugins.** A Cursor plugin is `.cursor-plugin/plugin.json`. With no manifest paths, Cursor discovers `skills/` and `commands/`.
  - A repository is importable from GitHub (Customize → From GitHub Repository, or `/plugin marketplace add` in the CLI) when it has `.cursor-plugin/marketplace.json`.
  - Command frontmatter supports `name` and `description`. `$ARGUMENTS` substitution is not documented.
- **Path variables.** `${CURSOR_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_ROOT}` are expanded only in MCP and hook configuration, not in `SKILL.md` text.

## Decision

- **Manifests.** Ship `.cursor-plugin/plugin.json` and `.cursor-plugin/marketplace.json` at the same plugin root.
  - The plugin manifest mirrors the Claude manifest's name, description, version, keywords and license.
  - It points `skills` at `./skills/` and `commands` at `./commands/`.
  - It reuses `.claude-plugin/icon.png` as its `logo`.
  - `scripts/verify-plugin-package.py` enforces all of the above.
- **Commands stay host-neutral.**
  - Each command says to use the text typed after the command when the host leaves `$ARGUMENTS` unfilled. The fallback sentence does not repeat the placeholder, because Claude Code substitutes it everywhere in the file.
  - Commands describe `<skill-dir>` as the folder holding the draw-design `SKILL.md`, not by a host path.
- **No Cursor rules file or MCP server.** The skill already carries the workflow, and `bin/ddraw` resolves its own location. `SKILL.md` needs no change.
- **Standalone install** for Cursor is a symlink into `~/.cursor/skills/`, the only user skills folder Cursor syncs to Cloud Agents.

## Consequences

- Cursor users can install the plugin from GitHub or symlink the skill. A user who also has the skill in `~/.claude/skills` may see it loaded twice (a Cursor behaviour); the README says to keep one copy.
- **Not verified:**
  - A live `cursor-agent` run could not authenticate from the build sandbox, so the end-to-end Cursor run is still to be done by hand. OQ-13 in the PRD tracks it.
  - Cursor's handling of a marketplace entry with `"source": "./"` (a plugin at the repository root) is inferred from the schema; the official template only shows subfolders.
