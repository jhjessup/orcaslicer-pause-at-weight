# Pause at Weight for OrcaSlicer

An OrcaSlicer plugin that inserts a filament-change pause before your spool runs out.

Weigh your spool, enter how many grams are left, and the plugin adds a pause at the start of the
layer where the print would use more than that (minus a safety margin). Swap spools, resume, done.

> **Status: 0.2.0, early.** OrcaSlicer's plugin system is new and its API may change. The plugin
> has been tested against a stand-in for OrcaSlicer's plugin API, not yet against a real
> OrcaSlicer install. Please check the exported G-code before relying on it, and
> [report problems](https://github.com/jhjessup/orcaslicer-pause-at-weight/issues).

## Requirements

- **As a plugin:** OrcaSlicer 2.5 or later.
- **As a post-processing script** (older OrcaSlicer, or if you prefer): Python 3.12 or later.

## Install as a plugin (OrcaSlicer 2.5+)

1. Download `pause_at_weight.py` from the [latest release](https://github.com/jhjessup/orcaslicer-pause-at-weight/releases/latest).
2. Add it in OrcaSlicer's **Plugins** window, or copy it into the `orca_plugins` folder in
   OrcaSlicer's data folder (on Windows, `%APPDATA%\OrcaSlicer`).
3. In **Process** settings (Advanced mode), pick **Pause at Weight** under
   **Slicing Pipeline Plugin**.
4. Set your spool weight with the **Capabilities** button (see Settings below).

## Settings

Settings are JSON, edited through the **Capabilities** dialog. They can be set globally or per
print, printer, or filament preset.

```json
{"remaining_g": 1000, "reserve_g": 20, "pause_command": "M600", "density_g_cm3": 0, "diameter_mm": 0}
```

| Setting | Meaning | Default |
|---|---|---|
| `remaining_g` | Grams left on the spool: scale reading minus empty spool weight | `1000` (fresh 1 kg spool) |
| `reserve_g` | Safety margin in grams, because slicer estimates aren't exact | `20` |
| `pause_command` | G-code for the pause. Separate several lines with `\n` | `M600` |
| `density_g_cm3` | Filament density. `0` uses your filament preset | `0` |
| `diameter_mm` | Filament diameter. `0` uses your filament preset | `0` |

Pause command by firmware:

| Firmware | `pause_command` |
|---|---|
| Marlin | `M600` (filament change) |
| Klipper | `PAUSE` |
| Bambu Lab | `M400 U1` |

**Remember to update `remaining_g` for a partly used spool.** With the default, the plugin
assumes a full 1 kg spool.

## Use as a post-processing script

In **Process → Others → Post-processing Scripts**, add a line like this:

```
"C:\Path\To\python.exe" "C:\Path\To\pause_at_weight.py" --remaining 312 --reserve 20 --pause-cmd M600;
```

OrcaSlicer adds the G-code file path automatically. Options: `--remaining`, `--reserve`,
`--pause-cmd`, `--density`, `--diameter` (same meanings and defaults as the settings above).

## Checking the result

The G-code preview does **not** show the pause; it is added to the exported file only. Open the
exported G-code and search for `pause_at_weight`.

- The second line of the file is always a summary, so you can tell the plugin ran, for example
  `; pause_at_weight: print needs 738.2 g, spool has 1000.0 g (reserve 20 g); no pause needed.`
- If a pause was inserted, a second match marks where, with the grams used before it. The
  `;Z:` line just below it is the height where the printer will pause.
- No match at all means the plugin did not run: check that it is selected under
  **Slicing Pipeline Plugin**. (Bambu `.gcode.3mf` files are zip archives; search the
  `.gcode` file inside.)

## Limitations

- Inserts one pause only. The replacement spool must hold the rest of the print; the plugin's
  message says how much that is.
- Multi-material prints: usage of all filaments is added together, and a warning is shown.

## Development

Run the tests (no OrcaSlicer needed) from the repository root:

```bash
python3 -m unittest discover -s tests
```

Lint and format with [ruff](https://docs.astral.sh/ruff/) (settings in `pyproject.toml`):

```bash
ruff check . && ruff format --check .
```

GitHub Actions runs both on every pull request.

## License

[MIT](LICENSE)
