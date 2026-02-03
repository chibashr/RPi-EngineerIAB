# Module Manager

Manages module discovery, enable/disable, install, and registration.

## Repo-based modules and updates

- **Available modules**: The same Git repo and branch used for app updates (`RPI_ENGINEER_UPDATE_REPO`, `RPI_ENGINEER_UPDATE_BRANCH`) is used as the catalog. When the app runs from a git clone, modules under `modules/` are read from the local repo; otherwise the GitHub API is used to list `modules/` and each `module.json`.
- **Install from repo**: A module can be installed by copying it from the repo into the configured modules directory (`RPI_ENGINEER_MODULES_DIR`). From a clone, files are copied from the repo path; otherwise a branch archive is downloaded from GitHub and the selected module is extracted.
- **Module updates**: Version is taken from each module’s `module.json` (`version`). The manager compares installed versions to repo versions (semver-like). Installed modules with a higher repo version are reported as having an update; applying the update overwrites the module directory and preserves enabled/disabled state.

## API

- `GET /api/v1/modules/list` – installed modules
- `GET /api/v1/modules/available` – modules in the repo (with installed/update flags)
- `POST /api/v1/modules/install-from-repo` – body `{ "module_id": "..." }`
- `GET /api/v1/modules/updates` – list of installed modules that have an update available
- `POST /api/v1/modules/update/<module_id>` – update one module from the repo
