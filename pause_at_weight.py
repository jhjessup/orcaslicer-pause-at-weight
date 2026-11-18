# /// script
# requires-python = ">=3.12"
#
# [tool.orcaslicer.plugin]
# name = "Pause at Weight"
# description = "Pauses for a filament change before the spool runs out, based on its weight."
# author = "jhjessup"
# version = "0.2.0"
# type = "slicing-pipeline"
# ///
"""Pause at Weight - an OrcaSlicer 2.5+ slicing-pipeline plugin.
https://github.com/jhjessup/orcaslicer-pause-at-weight

Weigh your spool, enter the grams left, and the plugin inserts a pause at the start of the
layer where the print would use more than (remaining_g - reserve_g).

Settings (JSON, edited in OrcaSlicer's plugin Capabilities dialog):
  remaining_g        grams left on the spool: scale reading minus empty spool weight
                     (default 1000, a fresh 1 kg spool)
  reserve_g          safety margin in grams (default 20)
  pause_command      G-code for the pause. Marlin: "M600", Klipper: "PAUSE", Bambu: "M400 U1".
                     Separate several lines with "\\n".
  density_g_cm3      0 = use the value from the filament preset
  diameter_mm        0 = use the value from the filament preset

The same file can also run as a classic post-processing script (for OrcaSlicer before 2.5):
  python3 pause_at_weight.py [--remaining 1000] [--reserve 20] [--pause-cmd M600] file.gcode
"""

import json
import math
import re
import sys

try:
    import orca
except ImportError:  # Running outside OrcaSlicer (command-line mode).
    orca = None

DEFAULTS = {
    "remaining_g": 1000,
    "reserve_g": 20,
    "pause_command": "M600",
    "density_g_cm3": 0,
    "diameter_mm": 0,
}

_WORD_RE = re.compile(r"([A-Z])\s*([-+]?(?:\d+\.?\d*|\.\d+))")
_LAYER_MARKER = ";LAYER_CHANGE"


# ----------------------------------------------------------------- core logic (no orca needed)


def _read_setting(lines, key):
    """First value of an OrcaSlicer '; key = value' setting (written at file end), or None."""
    pattern = re.compile(r"^;\s*" + re.escape(key) + r"\s*=\s*(.+)$")
    for line in reversed(lines):
        m = pattern.match(line.strip())
        if m:
            try:
                return float(m.group(1).split(",")[0].strip())
            except ValueError:
                return None
    return None


def _cumulative_extrusion(lines):
    """Total filament length (mm) extruded after each line, plus whether T1+ appears."""
    relative = False
    last_e = total = 0.0
    totals = []
    extra_tools = False
    for line in lines:
        code = line.split(";", 1)[0].strip().upper()
        if code:
            cmd = code.split()[0]
            if cmd in ("M82", "G90"):
                relative = False
            elif cmd in ("M83", "G91"):
                relative = True
            elif re.fullmatch(r"T[1-9]\d*", cmd):
                extra_tools = True
            else:
                words = dict(_WORD_RE.findall(code[len(cmd) :]))
                if "E" in words:
                    e = float(words["E"])
                    if cmd == "G92":
                        last_e = e
                    elif cmd in ("G0", "G1", "G2", "G3"):
                        if relative:
                            total += e
                        else:
                            total += e - last_e
                            last_e = e
        totals.append(total)
    return totals, extra_tools


def process_file(path, remaining_g, reserve_g, pause_command, density=0, diameter=0):
    """Insert the pause into the G-code file in place. Returns a message; raises ValueError."""
    if remaining_g <= 0:
        raise ValueError("set remaining_g (grams left on the spool) to a number above 0")

    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        lines = f.readlines()
    if not lines:
        raise ValueError("the G-code file is empty")

    density = density or _read_setting(lines, "filament_density")
    diameter = diameter or _read_setting(lines, "filament_diameter")
    if not density or not diameter:
        raise ValueError("filament density/diameter not found in G-code; set them in the config")

    grams_per_mm = math.pi * (diameter / 2) ** 2 / 1000.0 * density
    totals, extra_tools = _cumulative_extrusion(lines)
    total_g = totals[-1] * grams_per_mm
    note = " WARNING: several tools used; weights are combined." if extra_tools else ""

    limit_mm = (remaining_g - reserve_g) / grams_per_mm
    hit = next((i for i, t in enumerate(totals) if t > limit_mm), None)
    eol = "\r\n" if lines[0].endswith("\r\n") else "\n"

    if hit is None:
        message = (
            f"print needs {total_g:.1f} g, spool has {remaining_g:.1f} g "
            f"(reserve {reserve_g:g} g); no pause needed.{note}"
        )
    else:
        # Pause at the start of the layer where the limit is crossed.
        insert_at = next((i for i in range(hit, -1, -1) if lines[i].startswith(_LAYER_MARKER)), hit)
        used_g = (totals[insert_at - 1] if insert_at > 0 else 0.0) * grams_per_mm
        commands = [c.strip() for c in pause_command.replace("\\n", "\n").split("\n") if c.strip()]
        block = [f"; --- pause_at_weight: ~{used_g:.1f} g used of {remaining_g:.1f} g ---{eol}"]
        block += [c + eol for c in commands]
        block.append(f"; --- end pause_at_weight ---{eol}")
        lines[insert_at:insert_at] = block
        message = (
            f"pause inserted after ~{used_g:.1f} g (print total {total_g:.1f} g); "
            f"new spool needs at least {total_g - used_g:.1f} g.{note}"
        )

    # Always leave a summary near the top, so the file shows the plugin ran. It goes after
    # the first line, which some printers expect to stay first.
    lines.insert(1, f"; pause_at_weight: {message}{eol}")

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.writelines(lines)
    return message


# ----------------------------------------------------------------- OrcaSlicer plugin

if orca is not None:

    class PauseAtWeight(orca.slicing.SlicingPipelineCapabilityBase):
        def get_name(self):
            return "Pause at Weight"

        def get_default_config(self):
            return DEFAULTS

        def _settings(self):
            cfg = dict(DEFAULTS)
            try:
                cfg.update(json.loads(self.get_config()))
            except (AttributeError, TypeError, ValueError):
                pass
            return cfg

        def execute(self, ctx):
            # Only act on the exported G-code; every geometry step is a no-op.
            if ctx.step != orca.slicing.Step.psGCodePostProcess or not ctx.gcode_path:
                return orca.ExecutionResult.success()
            try:
                c = self._settings()
                msg = process_file(
                    ctx.gcode_path,
                    float(c["remaining_g"]),
                    float(c["reserve_g"]),
                    str(c["pause_command"]),
                    float(c["density_g_cm3"]),
                    float(c["diameter_mm"]),
                )
            except (ValueError, OSError) as e:
                return orca.ExecutionResult.failure(
                    orca.PluginResult.RecoverableError, "Pause at Weight: " + str(e)
                )
            return orca.ExecutionResult.success("Pause at Weight: " + msg)

    @orca.plugin
    class PauseAtWeightPackage(orca.base):
        def register_capabilities(self):
            orca.register_capability(PauseAtWeight)


# ----------------------------------------------------------------- command-line mode


def _main():
    import argparse

    p = argparse.ArgumentParser(description="Insert a pause before the spool runs out.")
    p.add_argument("gcode", help="G-code file (OrcaSlicer supplies this)")
    p.add_argument(
        "--remaining",
        type=float,
        default=DEFAULTS["remaining_g"],
        help="grams left on spool (default 1000)",
    )
    p.add_argument("--reserve", type=float, default=DEFAULTS["reserve_g"])
    p.add_argument("--pause-cmd", default=DEFAULTS["pause_command"])
    p.add_argument("--density", type=float, default=0)
    p.add_argument("--diameter", type=float, default=0)
    a = p.parse_args()
    try:
        print(
            "pause_at_weight: "
            + process_file(a.gcode, a.remaining, a.reserve, a.pause_cmd, a.density, a.diameter)
        )
    except (ValueError, OSError) as e:
        sys.exit("pause_at_weight: " + str(e))


if __name__ == "__main__" and orca is None:
    _main()
