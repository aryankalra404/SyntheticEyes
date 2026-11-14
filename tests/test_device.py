"""Render device choice, against a stand-in for Blender's Cycles preferences.

    python -m unittest discover tests
"""

import unittest

from wrapper.device import pick_gpu


class Device:
    def __init__(self, kind):
        self.type = kind
        self.use = kind == "CPU"


class Prefs:
    """Behaves like the Cycles add-on preferences: a backend that is not in the build cannot be
    selected (TypeError), and get_devices lists the CPU plus this machine's devices of that type."""

    def __init__(self, build, machine):
        self.build, self.machine = set(build), set(machine)
        self.devices = [Device("CPU")]
        self._kind = "NONE"

    @property
    def compute_device_type(self):
        return self._kind

    @compute_device_type.setter
    def compute_device_type(self, kind):
        if kind not in self.build:
            raise TypeError(f'enum "{kind}" not found')
        self._kind = kind

    def get_devices(self):
        if self._kind in self.machine and all(d.type != self._kind for d in self.devices):
            self.devices.append(Device(self._kind))


PC_BUILD = ("OPTIX", "CUDA", "HIP", "ONEAPI")       # Windows and Linux builds of Blender


class PickGpu(unittest.TestCase):
    def used(self, prefs):
        return sorted(d.type for d in prefs.devices if d.use)

    def test_mac_uses_metal(self):
        prefs = Prefs(("METAL",), ("METAL",))
        self.assertEqual(pick_gpu(prefs), "METAL")
        self.assertEqual(self.used(prefs), ["METAL"])

    def test_nvidia_prefers_optix(self):
        prefs = Prefs(PC_BUILD, ("OPTIX", "CUDA"))
        self.assertEqual(pick_gpu(prefs), "OPTIX")
        self.assertEqual(self.used(prefs), ["OPTIX"])

    def test_nvidia_without_optix_uses_cuda(self):
        self.assertEqual(pick_gpu(Prefs(PC_BUILD, ("CUDA",))), "CUDA")

    def test_amd_and_intel(self):
        self.assertEqual(pick_gpu(Prefs(PC_BUILD, ("HIP",))), "HIP")
        self.assertEqual(pick_gpu(Prefs(PC_BUILD, ("ONEAPI",))), "ONEAPI")

    def test_no_gpu_stays_on_cpu(self):
        prefs = Prefs(PC_BUILD, ())                 # the Docker image, or a laptop without a GPU
        self.assertIsNone(pick_gpu(prefs))
        self.assertEqual(self.used(prefs), ["CPU"])


if __name__ == "__main__":
    unittest.main()
