# Blender with its window open: play the Timeline of scene.blend in three looks (Cycles
# viewport, face wireframe, eye wireframe) and screenshot the window each frame, for the demo.
#   Blender scene.blend --window-geometry 0 0 1920 1080 -P tools/capture_blender_ui.py -- OUTDIR [xray=0.4]
# Everything is changed in memory only; the .blend is never saved. Feeds tools/make_demo.py.
import bpy, sys, os, json

ARGS = sys.argv[sys.argv.index("--") + 1:]
OUT = ARGS[0]
QUICK = "quick" in ARGS
XRAY = float(([a.split("=")[1] for a in ARGS if a.startswith("xray=")] or ["0.5"])[0])
WIREONLY = "wireonly" in ARGS
os.makedirs(OUT, exist_ok=True)
S = bpy.context.scene

# (name, frames, look, camera, wait seconds after frame change)
PHASES = [
    ("render", range(1, 101), "RENDERED", "cam_face", 5.0),
    ("wire_face", range(100, 190), "WIREFRAME", "cam_face", 0.05),
    ("wire_eye", range(190, 250), "WIREFRAME", "cam_move_eye", 0.05),
]
if QUICK:
    PHASES = [(n, list(f)[::40], l, c, w) for n, f, l, c, w in PHASES]

if WIREONLY:
    PHASES = [p for p in PHASES if p[2] == "WIREFRAME"]
SHOTS = [(n, f, l, c, w) for n, fr, l, c, w in PHASES for f in fr]
state = {"i": 0, "stage": "setup", "look": None}
HIDE_WIRE = {"vellus"}


def win_scr():
    win = bpy.context.window_manager.windows[0]
    return win, win.screen


def area_of(scr, t):
    return [a for a in scr.areas if a.type == t]


def region(area):
    return [r for r in area.regions if r.type == "WINDOW"][0]


def setup():
    win, scr = win_scr()
    ws = bpy.data.workspaces.get("Layout")
    if win.workspace != ws:
        win.workspace = ws
        return False
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
        if o.hide_render:
            o.hide_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects["gnm_head"]
    S.cycles.preview_samples = 8
    S.cycles.use_preview_denoising = True
    for area in area_of(scr, "VIEW_3D"):
        sp = area.spaces.active
        ov = sp.overlay
        ov.show_extras = False
        ov.show_outline_selected = False
        ov.show_relationship_lines = False
        ov.show_floor = False
        ov.show_axis_x = ov.show_axis_y = False
        ov.show_bones = False
        ov.wireframe_threshold = 1.0
        ov.wireframe_opacity = 1.0
        sp.show_gizmo = False
        sp.shading.xray_alpha_wireframe = XRAY
        sp.shading.show_xray_wireframe = True
    for area in area_of(scr, "PROPERTIES"):
        area.spaces.active.context = "DATA"
    for area in area_of(scr, "DOPESHEET_EDITOR"):
        area.spaces.active.mode = "TIMELINE"
        with bpy.context.temp_override(window=win, area=area, region=region(area)):
            try:
                bpy.ops.action.view_all()
            except Exception:
                pass
    for area in area_of(scr, "VIEW_3D"):
        with bpy.context.temp_override(window=win, screen=scr):
            try:
                bpy.ops.screen.area_move(x=area.x + area.width, y=area.y + area.height // 2, delta=-260)
            except Exception as e:
                print("area_move failed", e)
    return True


def set_look(look, cam):
    win, scr = win_scr()
    S.camera = bpy.data.objects[cam]
    for name in HIDE_WIRE:
        o = bpy.data.objects.get(name)
        if o:
            o.hide_set(look == "WIREFRAME")
    for area in area_of(scr, "VIEW_3D"):
        sp = area.spaces.active
        sp.shading.type = look
        sp.region_3d.view_perspective = "CAMERA"
        with bpy.context.temp_override(window=win, area=area, region=region(area)):
            bpy.ops.view3d.view_center_camera()


def shoot(idx):
    win, scr = win_scr()
    for a in scr.areas:
        a.tag_redraw()
    with bpy.context.temp_override(window=win):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
        bpy.ops.screen.screenshot(filepath=os.path.join(OUT, f"{idx:04d}.png"))


def tick():
    if state["stage"] == "setup":
        if setup():
            state["stage"] = "frame"
        return 0.5
    i = state["i"]
    if i >= len(SHOTS):
        json.dump([(n, f) for n, f, *_ in SHOTS], open(os.path.join(OUT, "shots.json"), "w"))
        bpy.ops.wm.quit_blender()
        return None
    name, f, look, cam, wait = SHOTS[i]
    if state["stage"] == "frame":
        if state["look"] != (look, cam):
            set_look(look, cam)
            state["look"] = (look, cam)
            S.frame_set(f)
            return 4.0
        S.frame_set(f)
        state["stage"] = "shoot"
        return wait
    shoot(i)
    state["i"] += 1
    state["stage"] = "frame"
    return 0.01


bpy.app.timers.register(tick, first_interval=2.0)
