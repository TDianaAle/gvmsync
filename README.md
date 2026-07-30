# gvmsync

**Automated permission synchronization for Greenbone Vulnerability Management (GVM) using project tags.**

gvmsync solves the lack of native multi-tenancy in Greenbone Community Edition.
It uses `project:*` tags on GVM resources (tasks, scanners, reports) to
automatically synchronize group-based permissions, enabling clean multi-client
isolation without manual permission management.

## How It Works

1. **Tag resources** in the GVM web UI with `project:<ClientName>` (e.g., `project:Acme`, `project:GlobalCorp`).
2. **Run gvmsync** — it discovers all tagged resources, ensures a GVM group
   exists for each project, and grants the minimum required permissions.
3. **Garbage collection** (optional) — revokes orphaned permissions when tags
   are removed or resources are deleted.

### Permission Model

| Resource Type | Permissions Granted          |
|---------------|------------------------------|
| Scanner       | `get_scanners`               |
| Task          | `get_tasks`, `start_task`, `stop_task` |
| Report        | `get_reports`                |

## Installation

### From PyPI (when published)

```bash
pip install gvmsync
```

### From source

```bash
git clone https://github.com/TDianaAle/gvmsync.git
cd gvmsync
pip install .
```

### Development setup

```bash
pip install uv
uv sync
uv run autohooks activate --force
```

## Requirements

- Python >= 3.10
- Greenbone Community Edition >= 24.10
- [python-gvm](https://github.com/greenbone/python-gvm) >= 24.0.0
- Access to the `gvmd` Unix socket

## Usage

### Standalone CLI

```bash
# Basic sync
gvmsync --admin admin --admin-pass secret

# Dry-run (simulate without changes)
gvmsync --admin admin --admin-pass secret --dry-run

# Sync with garbage collection
gvmsync --admin admin --admin-pass secret --enable-cleanup

# Show inventory of all resources and their tags
gvmsync --admin admin --admin-pass secret --all

# Using environment variables
export GVM_ADMIN_USER=admin
export GVM_ADMIN_PASS=secret
gvmsync
```

### As a gvm-tools script

Copy `scripts/sync-permissions-by-tags.gmp.py` to your system and run it
with [gvm-tools](https://github.com/greenbone/gvm-tools):

```bash
gvm-script --gmp-username admin --gmp-password secret \
    ssh --hostname gvm-host \
    sync-permissions-by-tags.gmp.py

# With options
gvm-script ... sync-permissions-by-tags.gmp.py --dry-run
gvm-script ... sync-permissions-by-tags.gmp.py --cleanup
gvm-script ... sync-permissions-by-tags.gmp.py --all
```

### Running inside a Docker container

```bash
# Copy the script into the gvmd container
docker cp scripts/sync-permissions-by-tags.gmp.py \
    greenbone-community-edition-gvmd-1:/scripts/

# Execute inside the container
docker exec -it greenbone-community-edition-gvmd-1 bash
pip install python-gvm lxml
python3 /scripts/sync-permissions-by-tags.gmp.py \
    --admin admin --admin-pass secret
```

## CLI Options

| Option               | Description                                      |
|----------------------|--------------------------------------------------|
| `--admin USERNAME`   | GVM admin username (or `GVM_ADMIN_USER` env var) |
| `--admin-pass PASS`  | GVM admin password (or `GVM_ADMIN_PASS` env var) |
| `--socket PATH`      | Unix socket path (default: `/run/gvmd/gvmd.sock`)|
| `--timeout SECONDS`  | Connection timeout (default: 60)                 |
| `--dry-run`          | Simulate changes without applying them           |
| `--enable-cleanup`   | Remove orphaned permissions (garbage collection) |
| `--all`              | Show inventory of all resources with their tags  |
| `-v, --verbose`      | Enable debug logging                             |
| `--version`          | Show version and exit                            |

## Architecture

```
gvmsync/
    _cli.py          # CLI entry point, argparse, logging
    _sync.py         # Orchestrator: sequences phases 1-4
    _resources.py    # Phase 1: extract tagged resources
    _groups.py       # Phase 2: ensure groups exist
    _permissions.py  # Phase 3: grant permissions + Phase 4: cleanup
    _inventory.py    # --all mode: full resource listing
    _xml.py          # XML parsing + retry utilities
    _errors.py       # Custom exception hierarchy
```

### Sync Phases

1. **Resource Extraction** — Queries GVM for all scanners, tasks, and reports.
   Filters for resources carrying `project:*` tags and groups them by project name.

2. **Group Verification** — For each discovered project, checks whether a GVM
   group with that name exists. Creates it if missing.

3. **Permission Configuration** — For each project group, grants the required
   permissions on each tagged resource. Skips permissions that already exist
   (idempotent).

4. **Garbage Collection** *(optional)* — Iterates all permissions of each group.
   If the underlying resource has been deleted or its `project:*` tag removed,
   the permission is revoked.

## Extending Permission Types

The `PERMISSION_CONFIG` dictionary in `_resources.py` defines which permissions
are granted per resource type. To add support for new resource types (e.g.,
targets), extend this dictionary:

```python
PERMISSION_CONFIG = {
    "scanner": ["get_scanners"],
    "task": ["get_tasks", "start_task", "stop_task"],
    "report": ["get_reports"],
    "target": ["get_targets"],  # new
}
```

You also need to add the resource type to `RESOURCE_TYPES` and provide the
corresponding `gmp.get_*` method mapping.

## Running Tests

```bash
pytest tests/ -v
```

## License

Copyright 2025-2026 Diana Tichy

Licensed under the GNU General Public License v3.0 or later.
See [LICENSE](LICENSE) for the full text.
