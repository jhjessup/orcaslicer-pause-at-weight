"""Tests for pause_at_weight.py. Run from the repository root:

python3 -m unittest discover -s tests
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "pause_at_weight.py")


def load_module(with_orca):
    """Load pause_at_weight.py, optionally with the fake orca module installed."""
    sys.modules.pop("orca", None)
    if with_orca:
        sys.path.insert(0, HERE)
        import fake_orca

        sys.path.pop(0)
        fake_orca.registered.clear()
        sys.modules["orca"] = fake_orca
    spec = importlib.util.spec_from_file_location("pause_at_weight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules.pop("orca", None)
    return module


def make_gcode(layers=10, moves=10, e_per_move=100.0, absolute=False):
    """Synthetic G-code. 1.75 mm PLA is ~2.98 g/m, so the defaults use ~29.8 g."""
    out = ["; start\n", "G90\n", "M82\n" if absolute else "M83\n", "G92 E0\n"]
    e = 0.0
    for layer in range(layers):
        out += [
            ";LAYER_CHANGE\n",
            f";Z:{0.2 * (layer + 1):.1f}\n",
            f"G1 Z{0.2 * (layer + 1):.1f}\n",
        ]
        for m in range(moves):
            if absolute:
                out += [f"G1 E{e - 0.8:.4f} ; retract\n", "G1 X10 Y10\n", f"G1 E{e:.4f}\n"]
                e += e_per_move
                out += [f"G1 X{m} Y5 E{e:.4f}\n"]
            else:
                out += [
                    "G1 E-0.8 ; retract\n",
                    "G1 X10 Y10\n",
                    "G1 E0.8\n",
                    f"G1 X{m} Y5 E{e_per_move}\n",
                ]
    out += ["; filament_diameter = 1.75,1.75\n", "; filament_density = 1.24,1.24\n"]
    return "".join(out)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module(with_orca=False)
        fd, self.path = tempfile.mkstemp(suffix=".gcode")
        os.close(fd)

    def tearDown(self):
        os.remove(self.path)

    def write(self, text):
        with open(self.path, "w", newline="") as f:
            f.write(text)

    def read(self):
        with open(self.path, newline="") as f:
            return f.read()

    def test_pause_inserted_before_layer_that_crosses_limit(self):
        self.write(make_gcode())
        msg = self.mod.process_file(self.path, 25, 5, "M600")
        self.assertIn("pause inserted", msg)
        lines = self.read().splitlines()
        i = lines.index("M600")
        # Limit is 20 g; each layer is ~2.98 g, so the pause goes before layer 7.
        self.assertEqual(lines[i + 2], ";LAYER_CHANGE")
        self.assertEqual(lines[i + 3], ";Z:1.4")

    def test_absolute_extrusion_gives_same_result(self):
        self.write(make_gcode(absolute=True))
        self.mod.process_file(self.path, 25, 5, "M600")
        lines = self.read().splitlines()
        self.assertEqual(lines[lines.index("M600") + 3], ";Z:1.4")

    def test_no_pause_when_spool_is_big_enough(self):
        original = make_gcode()
        self.write(original)
        msg = self.mod.process_file(self.path, 1000, 20, "M600")
        self.assertIn("no pause needed", msg)
        self.assertEqual(self.read(), original)

    def test_multi_line_pause_command(self):
        self.write(make_gcode())
        self.mod.process_file(self.path, 25, 5, "M117 Swap spool\\nM600")
        text = self.read()
        self.assertIn("M117 Swap spool\nM600\n", text)

    def test_windows_line_endings_preserved(self):
        self.write(make_gcode().replace("\n", "\r\n"))
        self.mod.process_file(self.path, 25, 5, "M600")
        self.assertIn("M600\r\n", self.read())
        self.assertNotIn("\r\r", self.read())

    def test_zero_remaining_is_an_error(self):
        self.write(make_gcode())
        with self.assertRaises(ValueError):
            self.mod.process_file(self.path, 0, 5, "M600")

    def test_missing_density_is_an_error_unless_given(self):
        self.write(make_gcode().replace("; filament_density = 1.24,1.24\n", ""))
        with self.assertRaises(ValueError):
            self.mod.process_file(self.path, 25, 5, "M600")
        self.assertIn(
            "pause inserted", self.mod.process_file(self.path, 25, 5, "M600", density=1.24)
        )

    def test_command_line_mode(self):
        self.write(make_gcode())
        r = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                "--remaining",
                "25",
                "--reserve",
                "5",
                "--pause-cmd",
                "PAUSE",
                self.path,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("\nPAUSE\n", self.read())


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module(with_orca=True)
        self.orca = self.mod.orca
        self.mod.PauseAtWeightPackage().register_capabilities()
        self.cap = self.orca.registered[0]()
        fd, self.path = tempfile.mkstemp(suffix=".gcode")
        os.close(fd)
        with open(self.path, "w") as f:
            f.write(make_gcode())

    def tearDown(self):
        os.remove(self.path)

    def run_step(self, step, config):
        self.cap._config = json.dumps(config)
        return self.cap.execute(types.SimpleNamespace(step=step, gcode_path=self.path))

    def test_geometry_steps_are_ignored(self):
        r = self.run_step(self.orca.slicing.Step.posSlice, {"remaining_g": 25, "reserve_g": 5})
        self.assertTrue(r.ok)
        with open(self.path) as f:
            self.assertNotIn("M600", f.read())

    def test_post_process_inserts_pause(self):
        r = self.run_step(
            self.orca.slicing.Step.psGCodePostProcess,
            {"remaining_g": 25, "reserve_g": 5, "pause_command": "PAUSE"},
        )
        self.assertTrue(r.ok, r.message)
        with open(self.path) as f:
            self.assertIn("\nPAUSE\n", f.read())

    def test_defaults_are_a_fresh_1kg_spool(self):
        self.assertEqual(self.cap.get_default_config()["remaining_g"], 1000)
        self.assertEqual(self.cap.get_default_config()["reserve_g"], 20)
        r = self.run_step(self.orca.slicing.Step.psGCodePostProcess, {})
        self.assertTrue(r.ok)
        self.assertIn("no pause needed", r.message)

    def test_bad_config_reports_failure(self):
        r = self.run_step(self.orca.slicing.Step.psGCodePostProcess, {"remaining_g": 0})
        self.assertFalse(r.ok)
        self.assertIn("remaining_g", r.message)


if __name__ == "__main__":
    unittest.main()
