# Command-line Tools

ProtFlow ships four `console_scripts` entry points. They're declared in
`pyproject.toml` and installed by `pip install -e .`.

## `protflow-init-config`

Initialise `config.py` from the bundled template.

```bash
protflow-init-config                          # writes ~/.config/protflow/config.py
protflow-init-config --dest /shared/cfg.py    # custom destination
protflow-init-config --force                  # overwrite an existing file
```

Behaviour:

1. Copies `protflow/config_template.py` to the destination.
2. Refuses to overwrite an existing config unless `--force`.
3. Prints the resulting path so you know where to edit.

## `protflow-set-config`

Pin a custom config path for future runs.

```bash
protflow-set-config /shared/protflow/config.py    # remember this path
protflow-set-config --unset                        # forget; revert to search order
```

What it does: writes (or removes) the pointer file at
`$XDG_CONFIG_HOME/protflow/config.path`. That file is the *first* candidate
in `_try_load_config_module`'s search order, so a pinned path beats
`$PROTFLOW_CONFIG` beats `$XDG_CONFIG_HOME/protflow/config.py` beats the
bundled fallback.

Use cases:

- Cluster admin maintains `/shared/protflow/config.py`; every user runs
  `protflow-set-config /shared/protflow/config.py` once.
- A developer has multiple ProtFlow installs (dev / prod) sharing one
  conda env; pin the right config per-shell or per-project.

## `protflow-check-config`

Print which config.py is currently in use.

```bash
$ protflow-check-config
ProtFlow is using config file: /home/me/.config/protflow/config.py
```

If no config can be resolved, prints the same instructive message you'd get
from `MissingConfigError` at runtime, plus the search order so you can fix
it.

## `protflow-init-config --dest` vs `protflow-set-config`

| Want                                    | Use                                                       |
|-----------------------------------------|-----------------------------------------------------------|
| Create a new config file                | `protflow-init-config --dest <path>`                      |
| Point ProtFlow at an existing file      | `protflow-set-config <path>`                              |
| Verify which file is in use             | `protflow-check-config`                                   |
| Revert to defaults                      | `protflow-set-config --unset`                             |

## Programmatic equivalents

```python
import os
os.environ["PROTFLOW_CONFIG"] = "/path/to/cfg.py"   # one-shot override per process

from protflow import require_config, get_config
cfg = require_config()                              # raises if no config found
maybe_cfg = get_config()                            # returns None instead of raising
```

`require_config()` is what every runner uses internally — call it once at
the top of a script if you want a fail-fast check that all paths resolve
correctly.
