# Contributing

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
