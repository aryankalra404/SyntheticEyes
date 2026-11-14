"""Pick the Cycles render device. No bpy import, so tests/test_device.py runs without Blender."""

# Tried in this order; the first backend with a device on this machine wins.
GPU_BACKENDS = ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL")


def pick_gpu(prefs, backends=GPU_BACKENDS):
    """Turn on the first GPU backend that has a device here; return its name, or None for CPU.

    prefs is bpy.context.preferences.addons["cycles"].preferences. Blender raises TypeError when
    a backend is not in this build (METAL outside macOS, OPTIX on a Mac), and lists no device of
    that type when the build has the backend but the machine has no such GPU.
    """
    for backend in backends:
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
        except (TypeError, ValueError, RuntimeError):
            continue
        if any(d.type == backend for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == backend
            return backend
    return None
