# Pause at Weight for OrcaSlicer

An OrcaSlicer plugin that inserts a filament-change pause before your spool runs out.

Weigh your spool, enter how many grams are left, and the plugin adds a pause at the start of the
layer where the print would use more than that (minus a safety margin). Swap spools, resume, done.

> **Status: 0.2.0, early.** Tested with OrcaSlicer 2.5 on Linux (Flatpak). OrcaSlicer's plugin
> system is new and its API may change. Please check the exported G-code before relying on it,
> and [report problems](https://github.com/jhjessup/orcaslicer-pause-at-weight/issues).

## Requirements

- **As a plugin:** OrcaSlicer 2.5 or later.
- **As a post-processing script** (older OrcaSlicer, or if you prefer): Python 3.12 or later.

## Install as a plugin (OrcaSlicer 2.5+)

1. Download `pause_at_weight.py` from the [latest release](https://github.com/jhjessup/orcaslicer-pause-at-weight/releases/latest).
2. Add it in OrcaSlicer's **Plugins** window, or copy it into the `orca_plugins` folder in
   OrcaSlicer's data folder (on Windows, `%APPDATA%\OrcaSlicer`).
3. Restart OrcaSlicer so it loads the plugin.
4. **Enable it:** in **Process** settings, switch on **Advanced** mode, open the **Others**
   page, and select **Pause at Weight** under **Slicing Pipeline Plugin**. Then **save the
   Process preset**. Installing alone does nothing: until it is selected here, the plugin
   never runs.
5. Set your spool weight with the **Capabilities** button (see Settings below).

If you have more than one OrcaSlicer installed (for example a Flatpak and a regular install
on Linux), each keeps its own plugins and presets. Install and enable the plugin in the one
you actually use.

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
| Older Marlin without `M600`, e.g. stock Creality Ender 5 | see the sequence below |
| Klipper | `PAUSE` |
| Bambu Lab | `M400 U1` |

### Older Marlin without `M600` (e.g. Creality Ender 5)

Many older or stock Creality firmwares don't support `M600`. This sequence builds the pause
from basic commands: it retracts, lifts, parks in a corner, waits for you to press the knob,
purges the new filament, and lowers back to print height. The next layer's own G-code moves
the head back over the print.

```
M84 S0            ; keep motors on while waiting (S0 matters: plain M84 turns them off)
M83               ; relative extrusion
G91
G1 E-2 F1800      ; retract
G1 Z10 F600       ; lift 10 mm
G90
G1 X0 Y0 F6000    ; park in the corner
M0 Change filament
G1 E25 F150       ; purge new filament (still parked; wipe the blob off)
G1 E-1 F1800      ; small retract so it doesn't drip on the way back
G91
G1 Z-10 F600      ; back down to print height
G90
M84 S120          ; restore Marlin's default 2-minute motor timeout
```

As the plugin setting (one line in the JSON, with `\n` between commands):

```json
"pause_command": "M84 S0\nM83\nG91\nG1 E-2 F1800\nG1 Z10 F600\nG90\nG1 X0 Y0 F6000\nM0 Change filament\nG1 E25 F150\nG1 E-1 F1800\nG91\nG1 Z-10 F600\nG90\nM84 S120"
```

Before relying on it:

- **`M0` must work on your printer.** Print a G-code file containing only `M0 test`: the
  screen should show "test" and wait for a knob press. If not, try `M25` (SD card pause).
- **Your G-code must use relative extrusion** (OrcaSlicer's default). `grep -m1 -E "^M8[23]"`
  on the exported file should print `M83`.
- **Printing from OctoPrint?** `M0` can conflict with how it sends commands; printing from
  the SD card is the safe choice.
- **Do a dry run:** set `remaining_g` so the pause happens a few layers in, then swap
  filament and check that it purges and resumes cleanly.

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
