"""Minimal stand-in for OrcaSlicer's embedded `orca` module, for tests only.

It mirrors only the parts of the API this plugin uses, as seen in OrcaSlicer's
sandboxes/orca_gcode_stamp_plugin_any.py example. It is not the real API.
"""
import enum
import types


class Step(enum.Enum):
    posSlice = 1
    psGCodePostProcess = 2


class _CapabilityBase:
    _config = "{}"

    def get_config(self):
        return self._config


class PluginResult:
    RecoverableError = "RecoverableError"
    FatalError = "FatalError"


class ExecutionResult:
    def __init__(self, ok, message):
        self.ok = ok
        self.message = message

    @staticmethod
    def success(message=""):
        return ExecutionResult(True, message)

    @staticmethod
    def failure(kind, message):
        return ExecutionResult(False, message)


slicing = types.SimpleNamespace(Step=Step, SlicingPipelineCapabilityBase=_CapabilityBase)
base = object
registered = []


def plugin(cls):
    return cls


def register_capability(cls):
    registered.append(cls)
