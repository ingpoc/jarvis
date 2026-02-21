# GitHub Account Isolation

Two-account setup: `ingpoc` (personal, default) and `openclaw-gurusharan` (Jarvis-only).

## Critical: Stale env override problem

**Symptom**: `gh` uses wrong account even with `GH_CONFIG_DIR` set — creates repos under `ingpoc` instead of `openclaw-gurusharan`.

**Root cause**: Process-level `GH_TOKEN` or `GITHUB_TOKEN` (inherited from shell at launch time) overrides `GH_CONFIG_DIR`. direnv only auto-loads on `cd` in an interactive shell. Any long-lived process (OpenCode, Claude Code daemon) inherits the env from when it was launched — which may have stale tokens.

**Fix**: Always extract the token explicitly, clearing stale overrides:

```bash
# ALWAYS use this pattern for gh operations in Jarvis context
GH_TOKEN=$(GH_CONFIG_DIR=~/.jarvis/gh-config GH_TOKEN= GITHUB_TOKEN= gh auth token --hostname github.com) \
GH_CONFIG_DIR=~/.jarvis/gh-config \
GH_TOKEN= GITHUB_TOKEN= \
gh <command>
```

**Why**: `GH_TOKEN=` (empty assignment before the subshell) clears the stale env for the token extraction call, ensuring the token comes from `GH_CONFIG_DIR`, not the inherited env.

**Practical example** — create a repo under the correct account:

```bash
_GH_TOKEN=$(GH_CONFIG_DIR=~/.jarvis/gh-config GH_TOKEN= GITHUB_TOKEN= gh auth token --hostname github.com)
GH_CONFIG_DIR=~/.jarvis/gh-config GH_TOKEN="$_GH_TOKEN" gh repo create openclaw-gurusharan/my-repo --private
```

**If a repo was created under the wrong account** (ingpoc instead of openclaw-gurusharan):

```bash
# Delete the wrongly created repo
gh repo delete ingpoc/<repo-name> --yes
# Then re-create under correct account using the pattern above
```

---

## Architecture

| Context | `GH_CONFIG_DIR` | Active account | Protocol |
|---------|-----------------|----------------|----------|
| Personal shell / Claude Code | `~/.config/gh` | `ingpoc` (default) | SSH |
| Jarvis workspace | `~/.jarvis/gh-config` | `openclaw-gurusharan` (locked) | HTTPS |

## How isolation works

- Jarvis's `.envrc` sets `GH_CONFIG_DIR=~/.jarvis/gh-config` — a separate gh config dir with only `openclaw-gurusharan`.
- `GH_TOKEN` is dynamically pulled from that isolated config (not hardcoded, never stale).
- `gh auth switch --user ingpoc` fails inside Jarvis context: "no accounts matched".
- `ingpoc` exists only in `~/.config/gh/` — Jarvis cannot see or reach it.

## Key files

| File | Purpose |
|------|---------|
| `~/.jarvis/workspaces/.envrc` | Sets `GH_CONFIG_DIR` + `GH_TOKEN` for Jarvis |
| `~/.jarvis/gh-config/hosts.yml` | Only `openclaw-gurusharan` — never add `ingpoc` here |
| `~/.config/gh/hosts.yml` | Both accounts, `ingpoc` active |
| `~/.zshrc` | direnv hook only — no `GH_TOKEN` / `GITHUB_TOKEN` exports |

## Maintenance rules

- **Never add `ingpoc` to `~/.jarvis/gh-config/`** — breaks isolation.
- **Never export `GH_TOKEN` in `~/.zshrc`** — pollutes personal shell.
- If `openclaw-gurusharan` OAuth token expires: `gh auth refresh` inside Jarvis context (`GH_CONFIG_DIR=~/.jarvis/gh-config gh auth refresh`), then `direnv reload`.
- If adding new scopes to `openclaw-gurusharan`: same as above — always use `GH_CONFIG_DIR` prefix.

## Verification

```bash
# Personal context — should show ingpoc active, openclaw-gurusharan inactive
gh auth status

# Jarvis context — should show only openclaw-gurusharan
GH_CONFIG_DIR=~/.jarvis/gh-config gh auth status

# Jarvis cannot reach ingpoc
GH_CONFIG_DIR=~/.jarvis/gh-config gh auth switch --user ingpoc
# → "no accounts matched that criteria"
```

## Setup (one-time, already done)

1. `brew install direnv` + add `eval "$(direnv hook zsh)"` to `~/.zshrc`
2. `cp ~/.config/gh/{config,hosts}.yml ~/.jarvis/gh-config/` (before ingpoc was added)
3. Created `~/.jarvis/workspaces/.envrc` with `GH_CONFIG_DIR` + dynamic `GH_TOKEN`
4. `direnv allow ~/.jarvis/workspaces`
5. `.envrc` added to global gitignore
6. `gh auth login --web` as `ingpoc` → added to `~/.config/gh/` only
