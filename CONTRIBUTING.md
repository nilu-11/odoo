# Contributing

## How to Fix a Bug in a Shared Module

This repo is used as a git submodule by multiple client repos. When you fix a bug here, you must also update the submodule pointer in each client repo.

### If the bug affects ALL school clients (fix in this repo):

1. Create a branch:
   ```bash
   git checkout -b fix/describe-the-bug
   ```
2. Fix the bug, commit, push, open PR → merge to `main`
3. In each client repo, update the submodule pointer:
   ```bash
   cd lincoln-college        # repeat for iims-college, etc.
   git submodule update --remote education
   git add education
   git commit -m "chore: update education submodule (fix describe-the-bug)"
   git push
   ```
4. Odoo.sh rebuilds automatically for each updated client repo.

### If the bug is client-specific (e.g. only affects Lincoln):

Fix it in the client repo's own `lincoln_specific/` folder — do NOT touch this repo.

### Branching strategy:

| Branch | Purpose |
|--------|---------|
| `main` | Stable — all client submodule pointers target this |
| `feat/emis` | Active EMIS feature development |
| `staging` | Pre-merge integration testing |

**Rule:** Client repos always point their submodule at a specific commit on `main`. Never point at a feature branch.

---

## Repository hygiene

Before committing, make sure generated/local artifacts are not tracked by git.

- Do not commit Python cache files (`__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd`).
- Do not commit virtual environments (`.venv/`, `venv/`, `env/`).
- Do not commit local environment files (`.env`, `.env.*`).
- Do not commit IDE metadata (`.vscode/`, `.idea/`).
- Do not commit local Claude workspace internals (`.claude/worktrees/`, `.claude/settings.local.json`).
- Do not commit runtime artifacts (`*.log`, `*.pid`, `*.sock`).

## Commit expectations

- Keep commits focused and module-specific when possible.
- Use clear, conventional commit messages (for example: `fix:`, `feat:`, `chore:`).
- Review `git status` before every commit to avoid accidental files.

## Odoo module changes

- Update manifest metadata when introducing new data, views, or dependencies.
- Include access/security updates when adding new models.
- Validate module installation/update flow locally before opening a PR.
