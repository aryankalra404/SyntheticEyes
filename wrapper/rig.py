"""Poses the GNM head in scene.blend from the 15 gaze-engine channels. bpy + mathutils only.

    rig = Rig()                      # finds gnm_rig / gnm_head in the open file
    rig.apply(channels)              # channels: dict with the names in wrapper.gaze.CHANNELS
    rig.key(frame)                   # keyframe everything apply() touched
    rig.pupil_px(camera)             # {"L": (x, y), "R": (x, y)}, pixels, origin top-left
    rig.eye_rotations()              # {"L": [rx, ry, rz], "R": ...}, world-frame Euler XYZ, rad

No drivers or constraints: every bone rotation and shape-key value is computed here and
written directly, so the .blend plays on the Timeline from F-curves alone.

Frames (Blender world; the armature object sits at the origin with identity transform):
    +X image-right (subject's left), +Z up, the face looks along -Y toward the camera.
    yaw > 0 turns toward image-right, pitch > 0 up, head roll > 0 tilts the top to image-right.
Everything needed at run time is read from the .blend (custom properties on gnm_rig).
"""

import math

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

NECK_SHARE = 0.35          # head rotation split: 35 % neck, 65 % head
LID_UP_FULL = 20.0         # deg of eye pitch for lid_up = 1
LID_DOWN_FULL = 25.0       # deg of eye pitch for lid_down = 1
LID_SIDE_FULL = 25.0       # deg of eye yaw toward the nose / temple for lid_in / lid_out = 1
LID_FOLLOW_MAX = 1.2
WIDEN_GAIN = 0.25
SIDES = ("L", "R")


def rot3(yaw, pitch, roll=0.0):
    """Rotation (radians) in the Blender world frame: yaw about +Z, pitch about -X, roll about +Y."""
    return (Matrix.Rotation(yaw, 3, "Z") @ Matrix.Rotation(-pitch, 3, "X")
            @ Matrix.Rotation(roll, 3, "Y"))


def pivot(R3, centre):
    """4x4 rotation R3 about the point centre."""
    return Matrix.Translation(centre) @ R3.to_4x4() @ Matrix.Translation(-centre)


def direction(yaw, pitch):
    """Unit gaze direction for image-space yaw/pitch (radians); (0, 0) looks at the camera."""
    return Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch),
                   math.sin(pitch)))


def tent(b, centre, width=1.0 / 3.0):
    return max(0.0, 1.0 - abs(b - centre) / width)


class Rig:
    def __init__(self, arm=None, mesh=None):
        self.arm = arm or bpy.data.objects["gnm_rig"]
        self.mesh = mesh or bpy.data.objects["gnm_head"]
        a = self.arm
        self.eye_rest = {s: Vector(a[f"eye_rest_{s}"]) for s in SIDES}
        self.eye_mid = Vector(a["eye_mid"])
        self.rest_pupil = float(a["rest_pupil"])
        self.rest_lid_open = float(a.get("rest_lid_open", 0.0))
        self.tent_blink = a.get("blink_keys", "single") == "tent"
        self.bones = {n: a.pose.bones[n] for n in ("neck", "head", "eye.L", "eye.R")}
        self.rest = {n: a.data.bones[n].matrix_local.copy() for n in self.bones}
        self.keys = self.mesh.data.shape_keys.key_blocks
        self.pupil_idx = {s: [v.index for v in self.mesh.data.vertices
                              if any(g.group == self.mesh.vertex_groups[f"pupil_{s}"].index
                                     for g in v.groups)] for s in SIDES}
        self.state = {}
        self.touched_keys = []

    # ---- posing -------------------------------------------------------------------------

    def _set_local(self, name, L):
        """Pose a bone by its rest-space rigid delta L (G_parent^-1 @ G_bone)."""
        M = self.rest[name]
        basis = M.inverted() @ L @ M
        self.bones[name].rotation_quaternion = basis.to_quaternion()
        self.bones[name].location = (0.0, 0.0, 0.0)

    def apply(self, ch):
        r = math.radians
        hy, hp, hl = r(ch.get("head_yaw", 0.0)), r(ch.get("head_pitch", 0.0)), r(ch.get("head_roll", 0.0))
        neck_c = self.rest["neck"].translation
        head_c = self.rest["head"].translation
        Ln = pivot(rot3(NECK_SHARE * hy, NECK_SHARE * hp, NECK_SHARE * hl), neck_c)
        Lh = pivot(rot3((1 - NECK_SHARE) * hy, (1 - NECK_SHARE) * hp, (1 - NECK_SHARE) * hl), head_c)
        G_head = Ln @ Lh
        R_head = G_head.to_3x3()
        self._set_local("neck", Ln)
        self._set_local("head", Lh)

        # Fixation point in the world frame; each eye aims at it (vergence), no torsion.
        target = G_head @ self.eye_mid + ch.get("gaze_dist", 0.6) * direction(
            r(ch.get("gaze_yaw", 0.0)), r(ch.get("gaze_pitch", 0.0)))
        eye_pitch, eye_yaw, eye_world = {}, {}, {}
        R_head_inv = R_head.inverted()
        for s in SIDES:
            e_rest = self.eye_rest[s]
            t = (R_head_inv @ (target - G_head @ e_rest)).normalized()   # in the head's rest frame
            yaw = math.atan2(t.x, -t.y)
            pitch = math.atan2(t.z, math.hypot(t.x, t.y))
            Re = rot3(yaw, pitch)
            self._set_local(f"eye.{s}", pivot(Re, e_rest))
            eye_pitch[s] = math.degrees(pitch)
            eye_yaw[s] = math.degrees(yaw)
            eye_world[s] = R_head @ Re

        # Shape keys.
        vals = {}
        for s in SIDES:
            b = min(max(ch.get(f"blink_{s}", 0.0), 0.0), 1.0)
            p = eye_pitch[s]
            up = min(max(p / LID_UP_FULL, 0.0), LID_FOLLOW_MAX)
            down = min(max(-p / LID_DOWN_FULL, 0.0), LID_FOLLOW_MAX)
            vals[f"lid_up.{s}"] = (up + WIDEN_GAIN * ch.get("widen", 0.0)) * (1.0 - b)
            vals[f"lid_down.{s}"] = down * (1.0 - b)
            # the lid apex follows the cornea sideways; nasal is -X for L, +X for R
            nasal = -eye_yaw[s] if s == "L" else eye_yaw[s]
            vals[f"lid_in.{s}"] = min(max(nasal / LID_SIDE_FULL, 0.0), LID_FOLLOW_MAX) * (1.0 - b)
            vals[f"lid_out.{s}"] = min(max(-nasal / LID_SIDE_FULL, 0.0), LID_FOLLOW_MAX) * (1.0 - b)
            vals[f"lid_open.{s}"] = self.rest_lid_open * (1.0 - b)
            if self.tent_blink:
                vals[f"blink_33.{s}"] = tent(b, 1 / 3)
                vals[f"blink_66.{s}"] = tent(b, 2 / 3)
                vals[f"blink.{s}"] = max(0.0, 1.0 - abs(b - 1.0) / (1 / 3))
            else:
                vals[f"blink.{s}"] = b
            vals[f"brow_up.{s}"] = ch.get(f"brow_{s}", 0.0)
            # squint lowers the upper margin too; left on through a blink it pushes the closed
            # upper lid 1.4 mm past the lower one at squint 0.3, so it fades with the blink
            vals[f"squint.{s}"] = ch.get("squint", 0.0) * (1.0 - b)
        vals["pupil"] = self.rest_pupil + ch.get("pupil", 0.0)
        self.touched_keys = []
        for k, v in vals.items():
            kb = self.keys.get(k)
            if kb is not None:
                kb.value = v
                self.touched_keys.append(kb)

        self.state = dict(eye_pitch=eye_pitch, eye_yaw=eye_yaw, eye_world=eye_world, target=target, shape=vals)
        bpy.context.view_layer.update()
        return self.state

    def key(self, frame):
        for pb in self.bones.values():
            pb.keyframe_insert("rotation_quaternion", frame=frame)
        for kb in self.touched_keys:
            kb.keyframe_insert("value", frame=frame)

    def clear_animation(self):
        for ob in (self.arm, self.mesh.data.shape_keys):
            if ob.animation_data:
                ob.animation_data_clear()

    def bake(self, track, fps=30, frame_start=1):
        """Keyframe a wrapper.gaze Track onto the Timeline; returns the number of frames."""
        prefs = bpy.context.preferences.edit
        old = prefs.keyframe_new_interpolation_type
        prefs.keyframe_new_interpolation_type = "LINEAR"   # no Bezier overshoot between frames
        try:
            self.clear_animation()
            rows = track.frames(fps)
            for row in rows:
                f = frame_start + row["frame"] - 1
                self.apply(row)
                self.key(f)
        finally:
            prefs.keyframe_new_interpolation_type = old
        scene = bpy.context.scene
        scene.render.fps = fps
        scene.frame_start = frame_start
        scene.frame_end = frame_start + len(rows) - 1
        return len(rows)

    # ---- measuring ----------------------------------------------------------------------

    def pupil_world(self):
        dg = bpy.context.evaluated_depsgraph_get()
        ev = self.mesh.evaluated_get(dg)
        me = ev.to_mesh()
        mw = self.mesh.matrix_world
        out = {}
        for s in SIDES:
            acc = Vector((0.0, 0.0, 0.0))
            for i in self.pupil_idx[s]:
                acc += me.vertices[i].co
            out[s] = mw @ (acc / len(self.pupil_idx[s]))
        ev.to_mesh_clear()
        return out

    def pupil_px(self, camera=None):
        scene = bpy.context.scene
        cam = camera or scene.camera
        w = scene.render.resolution_x * scene.render.resolution_percentage / 100.0
        h = scene.render.resolution_y * scene.render.resolution_percentage / 100.0
        out = {}
        for s, p in self.pupil_world().items():
            v = world_to_camera_view(scene, cam, p)
            out[s] = (v.x * w, (1.0 - v.y) * h)   # origin top-left
        return out

    def eye_rotations(self):
        """World-frame rotation of each eye relative to its rest pose, as Euler XYZ radians."""
        return {s: list(self.state["eye_world"][s].to_euler("XYZ")) for s in SIDES}
