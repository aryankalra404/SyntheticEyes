"""Numpy-only helpers for reading the GNM v3 head weights.

Mirrors the parts of the GNM package (google/GNM @ 846ab76) that the tools need,
so the export does not have to import GNM or TensorFlow:

- vertex group masks       gnm_xnp.GNM.vertex_group_mask
- UDIM tile assignment     gnm_udim.assign_tiles / offset_uvs_into_tiles
- linear blend skinning    gnm_common.linear_blend_skinning
- 68 sparse landmarks      gnm_landmarks.load_landmarks

GNM coordinates: metres, +Y up, +Z out of the face, subject's left eye at +X.
"""

from __future__ import annotations

import hashlib
import io
import os
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
GNM_SRC = REPO / "assets/third_party/gnm/gnm/shape"
MODEL_URL = "https://huggingface.co/google/gnm-v3/resolve/main/v3_0/gnm_head.npz"
NONZERO_THRESHOLD = 1e-4  # gnm_xnp._NONZERO_THRESHOLD

UDIM_TILE_REGIONS = {  # gnm_udim.UDIM_TILE_REGIONS
    1001: ("skin",),
    1002: ("left_eye", "&eye_interiors"),
    1003: ("left_eye", "&eye_exteriors"),
    1004: ("right_eye", "&eye_interiors"),
    1005: ("right_eye", "&eye_exteriors"),
    1006: ("upper_teeth_and_gums", "lower_teeth_and_gums"),
    1007: ("tongue",),
}

# Expression index ranges, read from expression_names in the v3.0 weights.
EXPR_LEFT_EYE = slice(0, 100)
EXPR_RIGHT_EYE = slice(100, 200)
EXPR_LOWER_FACE = slice(200, 350)
EXPR_TONGUE = slice(350, 382)  # tongue_mean (350) + tongue_000..030
EXPR_PUPIL = 382


def default_model_path() -> Path:
    if env := os.getenv("GNM_CACHE_DIR"):
        base = Path(env)
    elif xdg := os.getenv("XDG_CACHE_HOME"):
        base = Path(xdg) / "gnm" / "models"
    else:
        base = Path.home() / ".cache/gnm/models"
    return base / "v3_0" / "gnm_head.npz"


def fetch_model(path: Path) -> Path:
    """Downloads the weights to the same cache path GNM.from_remote uses."""
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".npz.part")
    req = urllib.request.Request(MODEL_URL, headers={"User-Agent": "gnm-client-python"})
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.replace(path)
    return path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def load_model(path: Path | None = None) -> dict[str, np.ndarray]:
    path = fetch_model(path or default_model_path())
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


class Groups:
    """Vertex group lookup with GNM's '[op][~]name' mask syntax."""

    def __init__(self, model: dict[str, np.ndarray]):
        self.names = [str(n) for n in model["vertex_group_names"]]
        self.values = model["vertex_groups"]

    def __call__(self, name: str) -> np.ndarray:
        return self.values[self.names.index(name)]

    def mask(self, *names: str) -> np.ndarray:
        out = np.zeros(self.values.shape[1], dtype=bool)
        for name in names:
            op, inv = "|", False
            if name[0] in "|&-":
                op, name = name[0], name[1:]
            if name[0] == "~":
                inv, name = True, name[1:]
            m = self(name) > NONZERO_THRESHOLD
            if inv:
                m = ~m
            if op == "|":
                out |= m
            elif op == "&":
                out &= m
            else:
                out &= ~m
        return out


def udim_tiles(model: dict[str, np.ndarray], faces: np.ndarray) -> np.ndarray:
    groups = Groups(model)
    tiles = np.zeros(len(faces), dtype=np.int32)
    for tile, names in UDIM_TILE_REGIONS.items():
        idx = np.where(groups.mask(*names)[faces].all(axis=-1))[0]
        if tiles[idx].any():
            raise ValueError(f"UDIM tile {tile} overlaps another tile")
        tiles[idx] = tile
    if (tiles == 0).any():
        raise ValueError(f"{int((tiles == 0).sum())} faces have no UDIM tile")
    return tiles


def udim_uvs(uvs: np.ndarray, tiles: np.ndarray) -> np.ndarray:
    t = tiles - 1001
    offset = np.stack([t % 10, t // 10], axis=-1).astype(uvs.dtype)
    return uvs + offset[:, None, :]


def load_landmarks() -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(GNM_SRC / "data/landmarks/head_sparse_68.txt")
    return data[:, ::2].astype(np.int32), data[:, 1::2].astype(np.float32)


def axis_angle_to_matrix(aa: np.ndarray) -> np.ndarray:
    aa = np.asarray(aa, dtype=np.float64)
    out = np.tile(np.eye(3), (*aa.shape[:-1], 1, 1))
    theta = np.linalg.norm(aa, axis=-1)
    nz = theta > 1e-12
    k = aa[nz] / theta[nz, None]
    K = np.zeros((len(k), 3, 3))
    K[:, 0, 1], K[:, 0, 2] = -k[:, 2], k[:, 1]
    K[:, 1, 0], K[:, 1, 2] = k[:, 2], -k[:, 0]
    K[:, 2, 0], K[:, 2, 1] = -k[:, 1], k[:, 0]
    s, c = np.sin(theta[nz])[:, None, None], np.cos(theta[nz])[:, None, None]
    out[nz] = np.eye(3) + s * K + (1 - c) * K @ K
    return out


def lbs(vertices, joints, rotations, parents, weights, translation=None):
    """Linear blend skinning exactly as gnm_common.linear_blend_skinning."""
    R = axis_angle_to_matrix(rotations)
    J = len(parents)
    local_t = joints.astype(np.float64).copy()
    local_t[1:] -= joints[parents[1:]]
    if translation is not None:
        local_t[0] += translation
    world = []
    for j in range(J):
        T = np.eye(4)
        T[:3, :3], T[:3, 3] = R[j], local_t[j]
        world.append(T if j == 0 else world[parents[j]] @ T)
    world = np.stack(world)
    r, t = world[:, :3, :3], world[:, :3, 3]
    t_bind = t - np.einsum("jmn,jn->jm", r, joints)
    vr = np.einsum("jv,jmn->vmn", weights, r)
    vt = np.einsum("jv,jm->vm", weights, t_bind)
    return np.einsum("vmn,vn->vm", vr, vertices) + vt


def lid_margins(model: dict[str, np.ndarray], side: str, column_mm: float = 2.0,
                depth_mm: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Upper and lower lid-margin vertex indices in the column through the pupil.

    The margin is the front rim of the `eye_sockets` group: socket vertices within
    `column_mm` of the pupil's x, and within `depth_mm` of the most forward socket
    vertex on that half (above or below the pupil centre).
    """
    groups = Groups(model)
    V = model["template_vertex_positions"]
    sign = 1.0 if side == "L" else -1.0
    eye = groups.mask("left_eye" if side == "L" else "right_eye")
    pupil = V[eye & groups.mask("pupils")].mean(axis=0)
    sock = groups.mask("eye_sockets") & (np.sign(V[:, 0]) == sign)
    col = sock & (np.abs(V[:, 0] - pupil[0]) < column_mm / 1000)
    out = []
    for half in (V[:, 1] > pupil[1], V[:, 1] < pupil[1]):
        idx = np.where(col & half)[0]
        zmax = V[idx, 2].max()
        out.append(idx[V[idx, 2] > zmax - depth_mm / 1000])
    return out[0], out[1]


def lid_gap_mm(vertices: np.ndarray, upper: np.ndarray, lower: np.ndarray) -> float:
    """Vertical gap between upper and lower margin; <= 0 means the lids meet."""
    return float((vertices[upper, 1].min() - vertices[lower, 1].max()) * 1000)


def save_npz_deterministic(path: Path, arrays: dict[str, np.ndarray]) -> None:
    """np.savez_compressed with fixed zip timestamps so the bytes are reproducible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".npz.part")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for key in sorted(arrays):
            buf = io.BytesIO()
            np.lib.format.write_array(buf, np.ascontiguousarray(arrays[key]),
                                      allow_pickle=False)
            info = zipfile.ZipInfo(key + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, buf.getvalue())
    tmp.replace(path)
