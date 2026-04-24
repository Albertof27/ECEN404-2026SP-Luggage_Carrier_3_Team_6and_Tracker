import os
import cv2
import time
import math
import atexit
import signal
import socket
import json
import serial
import threading
import numpy as np
import onnxruntime as ort

# =========================
# OPTIONAL: Picamera2
# =========================
USE_PICAMERA2 = True
SOURCE = 0

try:
    from picamera2 import Picamera2
except Exception:
    Picamera2 = None
    if USE_PICAMERA2:
        print("[WARN] Picamera2 not available, falling back to cv2.VideoCapture")
        USE_PICAMERA2 = False

# =========================
# OPTIONAL: Raspberry Pi GPIO
# =========================
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except Exception:
    GPIO = None
    GPIO_AVAILABLE = False
    print("[WARN] RPi.GPIO not available; ultrasonic obstacle sensing disabled")

# =========================
# DETECTION SETTINGS
# =========================
MODEL_PATH = "yolov8n.onnx"
OUTPUT_DIR = "runs_onnx"
SAVE_VIDEO = True

CONF_THRES = 0.35
IOU_THRES = 0.45
INPUT_SIZE = 640
CAM_W = 640
CAM_H = 480

CLASS_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse",
    "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie",
    "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut",
    "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book",
    "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

# =========================
# TRACKING + DISTANCE
# =========================
PERSON_H_M = 1.70
FOCAL_LEN_PX = 700.0
MAX_TRACK_MISSES = 12
MAX_MATCH_DIST = 120.0
TRACK_DISTANCE_ALPHA = 0.55
TRACK_MEMORY_SEC = 1.0
TRACK_PRUNE_SEC = 3.0
BOX_EDGE_MARGIN_PX = 6
BOTTOM_EDGE_MARGIN_PX = 8
MIN_PERSON_BOX_H_PX = 45
MIN_PERSON_ASPECT = 1.10

# =========================
# APPEARANCE RE-ID
# =========================
HIST_ENABLED = False
HIST_MATCH_THRESHOLD = 0.65
HIST_SAVE_MIN_STABLE_FRAMES = 8
HIST_REID_CONFIRM_FRAMES = 3
HIST_REID_MAX_X_SHIFT_FRAC = 0.20
HIST_REID_MAX_H_ERR_FRAC = 0.35
HIST_MIN_BOX_H_PX = 70
HIST_MIN_SCORE = 0.45
HIST_H_BINS = 24
HIST_S_BINS = 24
HIST_UPPER_Y1 = 0.10
HIST_UPPER_Y2 = 0.60

# =========================
# SERIAL / MOTOR + UWB
# =========================
UWB_SERIAL_PORT = "/dev/ttyACM0" #needs to be checked
MOTOR_SERIAL_PORT = "/dev/ttyACM1"
SERIAL_BAUD = 115200
PWM_MAX = 1023
motor_ser = None
uwb_ser = None

UWB_MIN_DIST_M = 0.10
UWB_MAX_DIST_M = 12.0
UWB_DISTANCE_ALPHA = 0.25
UWB_ANGLE_ALPHA = 0.24
UWB_MAX_ANGLE_JUMP_DEG = 75.0
UWB_MIN_ABS_Y_CM_FOR_ANGLE = 10.0
UWB_ANGLE_SIGN = 1.0  # set to -1.0 if left/right turns are reversed
UWB_STALE_S = 0.45
UWB_ANGLE_DEADBAND_DEG = 5.0
UWB_TURN_FULL_SCALE_DEG = 34
UWB_MAX_JUMP_M = 2.0
READY_STABLE_S = 0.0
READY_CENTER_TOL = 0.18
READY_MAX_UWB_DIST_M = 3.0
READY_MIN_UWB_DIST_M = 0.35
READY_LOST_RESET_S = 1.00
READY_MAX_ANGLE_DEG = 85.0

# =========================
# MANUAL OVERRIDE
# =========================
manual_command = "S"
manual_timeout = 0.0
manual_mode_enabled = False
manual_lock = threading.Lock()
MANUAL_HOLD_S = 1.0
UDP_PORT = 5006

# =========================
# CONTROL SETTINGS
# =========================
DESIRED_DIST_M = .95
HOLD_BAND_M = 0.04
MAX_FOLLOW_DIST_M = 10.0
MIN_VALID_FOLLOW_DIST_M = 0.45
MAX_DIST_JUMP_M = 1.00

FWD_MAX_PWM = 300 # indoor max forward speed
TURN_MAX_PWM = 640 # softened for slippery indoor floor
SEARCH_TURN_PWM = 100 # indoor search turn strength
COAST_TURN_GAIN = 0.45

K_FWD = 220.0 ##how far you are from desired distance/acceration
K_TURN = 515.0 # softened for slippery indoor floor
X_GATE = 1.40 # allows more forward motion while still correcting angle

ACCEL_STEP_PWM = 105 # indoor accel step
DECEL_STEP_PWM = 200 # indoor decel step
TURN_STEP_PWM = 255 # softened for slippery indoor floor
MIN_MOVE_PWM = 170
MIN_TURN_PWM = 345
TURN_ACTIVE_EPS = 50.0
TURN_SIGN_HYST_DEG = 8.0
TURN_SIGN_CONFIRM_FRAMES = 3
FOLLOW_STOP_MARGIN_M = 0.1
FOLLOW_CRUISE_PWM = 175.0
FOLLOW_MIN_HEADING_SCALE = 0.45

TARGET_LOST_COAST_S = 0.35
TARGET_LOST_SEARCH_S = 1.20

STATE_SEARCH = "SEARCH"
STATE_FOLLOW = "FOLLOW"
STATE_COAST = "COAST"
STATE_BLOCKED = "BLOCKED"
STATE_MANUAL = "MANUAL"
STATE_WAIT = "WAIT"
STATE_REVERSE = "REVERSE"
STATE_AVOID_LEFT = "AVOID_LEFT"
STATE_AVOID_RIGHT = "AVOID_RIGHT"

# =========================
# ULTRASONIC SETTINGS
# =========================
USE_ULTRASONICS = True

# Update these GPIO values to match your wiring.
# The old center/front + side + back sensors share TRIG 24 in this example.
# The two added front sensors use their own trigger pins.
# =========================
# ULTRASONIC SETTINGS
# =========================
USE_ULTRASONICS = True

US_SENSORS = {
  #  "front_left": {"trig": 27, "echo": 23},
    "front": {"trig": 27, "echo": 24},
    "left": {"trig": 27, "echo": 25},
    "back": {"trig": 27, "echo": 22},
}

FRONT_SENSOR_NAMES = ("front",)
US_POLL_SEQUENCE = ["front", "left", "back"]

US_MIN_M = 0.02
US_MAX_M = 4.00
US_INTER_SENSOR_DELAY_S = 0.05
US_LOOP_DELAY_S = 0.02
US_TIMEOUT_S = 0.025
US_FILTER_ALPHA = 0.45
US_FRONT_FILTER_ALPHA = 0.70
US_STALE_S = 0.35
AUTO_HARD_STOP_FRONT_M = 0.76
AVOID_BIAS_DIST_M = 0.90 # kept aligned with closer indoor spacing
AVOID_TURN_PWM = 550 # indoor pivot turn strength
AVOID_BIAS_GAIN = 95.0 #how strong the extra stear is during avoid mode
AVOID_FWD_PWM = 320 #forward arc speed during avoid turn
AVOID_ARC_OUTER_MIN_PWM = 650 #outer wheel threshold to break friction in avoid arcs
MIN_AVOID_HOLD_S = 0.50
REVERSE_PWM = 220
REVERSE_HOLD_S = 0.55
TURN_CLEAR_FRONT_M = 0.95
MAX_AVOID_TURN_S = 1.10
STOP_ESCAPE_DELAY_S = 0.0  # disabled in final: hard stop only
ESCAPE_REVERSE_S = 0.0   # disabled in final: hard stop only
ESCAPE_PIVOT_S = 0.0     # disabled in final: hard stop only
PERSON_CENTER_THRESHOLD = 0.35
TARGET_FRONT_DIST_TOL_M = 0.55
TARGET_FRONT_DIST_REL_TOL = 0.40
AVOID_SIDE_CLEAR_M = 1.00
AVOID_SIDE_MARGIN_M = 0.12

ultra = {name: float("nan") for name in US_SENSORS}
ultra_lock = threading.Lock()
ultra_last_update_s = 0.0
ultra_thread_started = False
ultra_thread = None
ultra_stop_event = threading.Event()

uwb_lock = threading.Lock()
uwb_stop_event = threading.Event()
uwb_thread_started = False
uwb_thread = None


class UWBState:
    def __init__(self):
        self.tag_id = ""
        self.distance_m = None
        self.angle_deg = None
        self.raw_distance_m = None
        self.raw_angle_deg = None
        self.x_cm = None
        self.y_cm = None
        self.last_update_s = 0.0
        self.raw_line = ""


uwb_state = UWBState()


def wrap_angle_deg(angle_deg):
    return ((angle_deg + 180.0) % 360.0) - 180.0


def smooth_angle_deg(prev_deg, new_deg, alpha):
    if prev_deg is None:
        return wrap_angle_deg(new_deg)
    delta = wrap_angle_deg(new_deg - prev_deg)
    return wrap_angle_deg(prev_deg + (alpha * delta))


def parse_uwb_line(line):
    line = line.strip()
    if not line or '{' not in line:
        return None

    try:
        payload = json.loads(line[line.index('{'):])
    except Exception:
        return None

    twr = payload.get('TWR')
    if not isinstance(twr, dict):
        return None

    d_cm = twr.get('D')
    x_cm = twr.get('Xcm')
    y_cm = twr.get('Ycm')
    tag_id = str(twr.get('a16', ''))

    if d_cm is None:
        return None

    try:
        dist_m = float(d_cm) / 100.0
    except Exception:
        return None

    x_val = None if x_cm is None else float(x_cm)
    y_val = None if y_cm is None else float(y_cm)

    if x_val is None or y_val is None:
        angle_deg = 0.0
    elif abs(y_val) < UWB_MIN_ABS_Y_CM_FOR_ANGLE:
        angle_deg = 0.0
    else:
        try:
            angle_deg = UWB_ANGLE_SIGN * math.degrees(math.atan2(x_val, y_val))
        except Exception:
            angle_deg = 0.0

    return {
        'tag_id': tag_id,
        'distance_m': dist_m,
        'angle_deg': float(angle_deg),
        'x_cm': x_val,
        'y_cm': y_val,
        'raw': line,
    }


def update_uwb_state(parsed):
    global uwb_state
    if parsed is None:
        return

    dist_m = parsed['distance_m']
    angle_deg = parsed['angle_deg']
    if not (UWB_MIN_DIST_M <= dist_m <= UWB_MAX_DIST_M):
        return

    with uwb_lock:
        prev_raw = uwb_state.raw_distance_m
        if prev_raw is not None and abs(dist_m - prev_raw) > UWB_MAX_JUMP_M:
            return

        prev_angle = uwb_state.raw_angle_deg
        if prev_angle is not None:
            angle_delta = abs(wrap_angle_deg(angle_deg - prev_angle))
            if angle_delta > UWB_MAX_ANGLE_JUMP_DEG:
                return

        uwb_state.raw_distance_m = dist_m
        uwb_state.raw_angle_deg = angle_deg
        uwb_state.distance_m = dist_m if uwb_state.distance_m is None else ((UWB_DISTANCE_ALPHA * dist_m) + ((1.0 - UWB_DISTANCE_ALPHA) * uwb_state.distance_m))
        uwb_state.angle_deg = smooth_angle_deg(uwb_state.angle_deg, angle_deg, UWB_ANGLE_ALPHA)
        uwb_state.tag_id = parsed['tag_id']
        uwb_state.x_cm = parsed['x_cm']
        uwb_state.y_cm = parsed['y_cm']
        uwb_state.last_update_s = time.time()
        uwb_state.raw_line = parsed['raw']


def get_uwb_snapshot():
    with uwb_lock:
        dist_m = uwb_state.distance_m
        angle_deg = uwb_state.angle_deg
        raw_dist_m = uwb_state.raw_distance_m
        raw_angle_deg = uwb_state.raw_angle_deg
        x_cm = uwb_state.x_cm
        y_cm = uwb_state.y_cm
        tag_id = uwb_state.tag_id
        last_update_s = uwb_state.last_update_s
        raw_line = uwb_state.raw_line

    age_s = time.time() - last_update_s if last_update_s > 0.0 else float('inf')
    valid = (dist_m is not None) and (angle_deg is not None) and (age_s <= UWB_STALE_S)
    return {
        'valid': valid,
        'distance_m': None if not valid else float(dist_m),
        'angle_deg': None if not valid else float(angle_deg),
        'raw_distance_m': raw_dist_m,
        'raw_angle_deg': raw_angle_deg,
        'x_cm': x_cm,
        'y_cm': y_cm,
        'tag_id': tag_id,
        'age_s': age_s,
        'raw_line': raw_line,
    }


def uwb_reader_loop():
    global uwb_ser
    while not uwb_stop_event.is_set():
        if uwb_ser is None:
            time.sleep(0.05)
            continue

        try:
            line = uwb_ser.readline().decode(errors='ignore').strip()
        except Exception as e:
            if not uwb_stop_event.is_set():
                print(f"[UWB] Read error: {e}")
            time.sleep(0.05)
            continue

        if not line:
            continue

        parsed = parse_uwb_line(line)
        if parsed is not None:
            update_uwb_state(parsed)


class StartupGate:
    def __init__(self):
        self.latched = False
        self.ever_started = False
        self.stable_start_s = 0.0
        self.last_good_s = 0.0

    def reset(self):
        self.latched = False
        self.ever_started = False
        self.stable_start_s = 0.0
        self.last_good_s = 0.0

    def update(self, uwb, target):
        now = time.time()
        uwb_valid = bool(uwb.get('valid'))
        target_visible = target is not None

        if uwb_valid:
            self.last_good_s = now

        # After the first startup, UWB alone is enough to keep/re-arm tracking.
        if self.ever_started:
            if self.latched:
                if (not uwb_valid) and ((now - self.last_good_s) > READY_LOST_RESET_S):
                    self.latched = False
                return self.latched

            if uwb_valid:
                self.latched = True
                return True

            return False

        # Before first startup, require person in front + valid UWB.
        ready_ok = uwb_valid and target_visible

        if ready_ok:
            if self.stable_start_s <= 0.0:
                self.stable_start_s = now
            self.latched = True
            self.ever_started = True
            return True

        self.stable_start_s = 0.0
        return False

    def stable_time_s(self):
        if self.latched:
            return READY_STABLE_S
        if self.stable_start_s <= 0.0:
            return 0.0
        return max(0.0, time.time() - self.stable_start_s)


def person_center_error(box, frame_w):
    x1, _, x2, _ = box
    cx = 0.5 * (x1 + x2)
    return float((cx - (frame_w * 0.5)) / (frame_w * 0.5))


def pick_camera_target(tracked, frame_w, frame_h, preferred_track_id=None):
    people = []
    for det in tracked:
        if det.get('label') != 'person':
            continue
        e_x = person_center_error(det['box'], frame_w)
        det['center_err'] = e_x
        det['startup_ok'] = person_box_startup_ok(det['box'], frame_w, frame_h)
        det['startup_centered'] = det['startup_ok'] and (abs(e_x) <= READY_CENTER_TOL)
        people.append(det)

    if not people:
        return None

    if preferred_track_id is not None:
        for det in people:
            if det.get('track_id') == preferred_track_id:
                det['target_pick_reason'] = 'TRACK_ID'
                return det

    people.sort(key=lambda d: (0 if d.get('startup_centered') else 1, abs(d.get('center_err', 999.0)), -float(d.get('score', 0.0))))
    people[0]['target_pick_reason'] = 'CENTER'
    return people[0]


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def rate_limit(current, target, up_step, down_step):
    delta = target - current
    if delta > 0:
        return current + min(delta, up_step)
    return current + max(delta, -down_step)


def mix_differential(drive_pwm, turn_pwm, enforce_min_move=False, enforce_min_turn=False, allow_pivot=True):
    if allow_pivot and abs(turn_pwm) >= TURN_ACTIVE_EPS and abs(drive_pwm) < MIN_MOVE_PWM:
        left = turn_pwm
        right = -turn_pwm
    else:
        left = drive_pwm + turn_pwm
        right = drive_pwm - turn_pwm

    if enforce_min_move and abs(drive_pwm) >= TURN_ACTIVE_EPS:
        if left > 0.0:
            left = max(left, MIN_MOVE_PWM)
        elif left < 0.0:
            left = min(left, -MIN_MOVE_PWM)
        if right > 0.0:
            right = max(right, MIN_MOVE_PWM)
        elif right < 0.0:
            right = min(right, -MIN_MOVE_PWM)

    if enforce_min_turn and abs(turn_pwm) >= TURN_ACTIVE_EPS:
        turn_sign = 1.0 if turn_pwm > 0.0 else -1.0
        left = abs(left) if turn_sign > 0.0 else -abs(left)
        right = -abs(right) if turn_sign > 0.0 else abs(right)

        if abs(left) < MIN_TURN_PWM:
            left = turn_sign * MIN_TURN_PWM
        if abs(right) < MIN_TURN_PWM:
            right = -turn_sign * MIN_TURN_PWM

    return int(clamp(left, -PWM_MAX, PWM_MAX)), int(clamp(right, -PWM_MAX, PWM_MAX))


def mix_forward_arc(drive_pwm, turn_pwm, outer_min_pwm=0.0):
    left = max(0.0, drive_pwm + turn_pwm)
    right = max(0.0, drive_pwm - turn_pwm)

    if abs(turn_pwm) >= TURN_ACTIVE_EPS:
        if turn_pwm > 0.0:
            left = max(left, outer_min_pwm)
        else:
            right = max(right, outer_min_pwm)

    return int(clamp(left, 0, PWM_MAX)), int(clamp(right, 0, PWM_MAX))


def make_output_path(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    i = 1
    while os.path.exists(os.path.join(output_dir, f"{i}.mp4")):
        i += 1
    return os.path.join(output_dir, f"{i}.mp4")


def estimate_person_distance_m(box):
    x1, y1, x2, y2 = box
    h = max(1.0, y2 - y1)
    return (PERSON_H_M * FOCAL_LEN_PX) / h


def person_box_reliable(box, frame_w, frame_h):
    x1, y1, x2, y2 = box
    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)
    aspect = h / w

    if y2 >= frame_h - BOTTOM_EDGE_MARGIN_PX:
        return False
    if y1 <= BOX_EDGE_MARGIN_PX:
        return False
   # if x1 <= BOX_EDGE_MARGIN_PX or x2 >= frame_w - BOX_EDGE_MARGIN_PX:
    #    return False
    if h < MIN_PERSON_BOX_H_PX:
        return False
    if aspect < MIN_PERSON_ASPECT:
        return False
    return True


def person_box_startup_ok(box, frame_w, frame_h):
    x1, y1, x2, y2 = box
    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)
    aspect = h / w

    if y1 <= BOX_EDGE_MARGIN_PX:
        return False
    if x1 <= BOX_EDGE_MARGIN_PX or x2 >= frame_w - BOX_EDGE_MARGIN_PX:
        return False
    if h < MIN_PERSON_BOX_H_PX:
        return False
    if aspect < MIN_PERSON_ASPECT:
        return False
    return True


def iou_xyxy(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    iw = max(0.0, inter_x2 - inter_x1)
    ih = max(0.0, inter_y2 - inter_y1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter + 1e-9
    return inter / union


def nms_xyxy(dets, iou_thres=0.45):
    if not dets:
        return []
    dets = sorted(dets, key=lambda d: d["score"], reverse=True)
    keep = []
    while dets:
        best = dets.pop(0)
        keep.append(best)
        remaining = []
        for d in dets:
            if d["cls_id"] != best["cls_id"] or iou_xyxy(d["box"], best["box"]) < iou_thres:
                remaining.append(d)
        dets = remaining
    return keep


class SimpleTracker:
    def __init__(self, max_misses=10, max_match_dist=100.0):
        self.max_misses = max_misses
        self.max_match_dist = max_match_dist
        self.next_id = 1
        self.tracks = {}

    @staticmethod
    def center(box):
        x1, y1, x2, y2 = box
        return np.array([(x1 + x2) * 0.5, (y1 + y2) * 0.5], dtype=np.float32)

    def update(self, detections):
        assigned_track_ids = set()
        assigned_det_idx = set()

        for tid in list(self.tracks.keys()):
            tr = self.tracks[tid]
            tr_center = self.center(tr["box"])
            tr_cls = tr["cls_id"]
            best_idx = -1
            best_dist = float("inf")

            for i, det in enumerate(detections):
                if i in assigned_det_idx or det["cls_id"] != tr_cls:
                    continue
                det_center = self.center(det["box"])
                dist = float(np.linalg.norm(det_center - tr_center))
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i

            if best_idx >= 0 and best_dist <= self.max_match_dist:
                det = detections[best_idx]
                self.tracks[tid] = {
                    "box": det["box"],
                    "cls_id": det["cls_id"],
                    "label": det["label"],
                    "score": det["score"],
                    "misses": 0,
                }
                detections[best_idx]["track_id"] = tid
                assigned_track_ids.add(tid)
                assigned_det_idx.add(best_idx)

        for i, det in enumerate(detections):
            if i in assigned_det_idx:
                continue
            tid = self.next_id
            self.next_id += 1
            self.tracks[tid] = {
                "box": det["box"],
                "cls_id": det["cls_id"],
                "label": det["label"],
                "score": det["score"],
                "misses": 0,
            }
            det["track_id"] = tid
            assigned_track_ids.add(tid)

        dead = []
        for tid, tr in self.tracks.items():
            if tid not in assigned_track_ids:
                tr["misses"] += 1
                if tr["misses"] > self.max_misses:
                    dead.append(tid)
        for tid in dead:
            del self.tracks[tid]

        return detections


class TargetAppearance:
    def __init__(self):
        self.saved_hist = None
        self.reference_track_id = -1
        self.saved_from_box = None
        self.stable_track_id = -1
        self.stable_count = 0
        self.last_similarity = 0.0
        self.last_match_track_id = -1
        self.last_target_box = None
        self.reid_candidate_track_id = -1
        self.reid_candidate_count = 0

    def clear(self):
        self.saved_hist = None
        self.reference_track_id = -1
        self.saved_from_box = None
        self.stable_track_id = -1
        self.stable_count = 0
        self.last_similarity = 0.0
        self.last_match_track_id = -1
        self.last_target_box = None
        self.reid_candidate_track_id = -1
        self.reid_candidate_count = 0

    def has_reference(self):
        return self.saved_hist is not None

    def _compute_hist(self, frame, box):
        x1, y1, x2, y2 = map(int, box)
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(frame.shape[1], x2)
        y2 = min(frame.shape[0], y2)
        if x2 <= x1 or y2 <= y1:
            return None

        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return None

        h = roi.shape[0]
        if h < HIST_MIN_BOX_H_PX:
            return None

        y_top = int(h * HIST_UPPER_Y1)
        y_bot = int(h * HIST_UPPER_Y2)
        if y_bot <= y_top:
            return None

        upper = roi[y_top:y_bot, :]
        if upper.size == 0:
            return None

        if USE_PICAMERA2:
            hsv = cv2.cvtColor(upper, cv2.COLOR_RGB2HSV)
        else:
            hsv = cv2.cvtColor(upper, cv2.COLOR_BGR2HSV)

        mask = cv2.inRange(hsv, np.array([0, 30, 20]), np.array([180, 255, 255]))
        hist = cv2.calcHist([hsv], [0, 1], mask, [HIST_H_BINS, HIST_S_BINS], [0, 180, 0, 256])
        if hist is None:
            return None
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return hist

    def compare(self, frame, box):
        if self.saved_hist is None:
            return 0.0
        hist = self._compute_hist(frame, box)
        if hist is None:
            return 0.0
        sim = float(cv2.compareHist(self.saved_hist, hist, cv2.HISTCMP_CORREL))
        return sim

    def spatial_gate(self, box, frame_w):
        if self.last_target_box is None:
            return True

        px1, py1, px2, py2 = self.last_target_box
        bx1, by1, bx2, by2 = box

        prev_cx = 0.5 * (px1 + px2)
        curr_cx = 0.5 * (bx1 + bx2)
        prev_h = max(1.0, py2 - py1)
        curr_h = max(1.0, by2 - by1)

        x_ok = abs(curr_cx - prev_cx) <= (HIST_REID_MAX_X_SHIFT_FRAC * frame_w)
        h_ratio = curr_h / prev_h
        h_ok = (1.0 - HIST_REID_MAX_H_ERR_FRAC) <= h_ratio <= (1.0 + HIST_REID_MAX_H_ERR_FRAC)
        return x_ok and h_ok

    def update_reid_candidate(self, det):
        tid = det.get("track_id", -1) if det is not None else -1
        if tid < 0:
            self.reid_candidate_track_id = -1
            self.reid_candidate_count = 0
            return 0

        if self.reid_candidate_track_id == tid:
            self.reid_candidate_count += 1
        else:
            self.reid_candidate_track_id = tid
            self.reid_candidate_count = 1
        return self.reid_candidate_count

    def observe_target(self, frame, target):
        if not HIST_ENABLED or target is None:
            self.stable_track_id = -1
            self.stable_count = 0
            return

        if target.get("label") != "person":
            self.stable_track_id = -1
            self.stable_count = 0
            return

        tid = target.get("track_id", -1)
        if tid < 0:
            self.stable_track_id = -1
            self.stable_count = 0
            return

        self.last_target_box = list(target["box"])
        self.last_match_track_id = tid
        self.last_similarity = float(target.get("hist_similarity", 0.0))
        self.reid_candidate_track_id = tid
        self.reid_candidate_count = max(self.reid_candidate_count, HIST_REID_CONFIRM_FRAMES)

        score = float(target.get("score", 0.0))
        if score < HIST_MIN_SCORE:
            self.stable_track_id = -1
            self.stable_count = 0
            return

        if target.get("distance_source") not in ("YOLO", "YOLO_INIT", "MEM"):
            self.stable_track_id = -1
            self.stable_count = 0
            return

        if self.stable_track_id == tid:
            self.stable_count += 1
        else:
            self.stable_track_id = tid
            self.stable_count = 1

        if self.saved_hist is None and self.stable_count >= HIST_SAVE_MIN_STABLE_FRAMES:
            hist = self._compute_hist(frame, target["box"])
            if hist is not None:
                self.saved_hist = hist
                self.reference_track_id = tid
                self.saved_from_box = list(target["box"])
                print(f"[HIST] Saved reference for track {tid}")


class TrackMemory:
    def __init__(self):
        self.mem = {}

    def ensure(self, track_id):
        if track_id not in self.mem:
            self.mem[track_id] = {
                "dist_m": None,
                "last_good_ts": 0.0,
                "last_seen_ts": 0.0,
                "last_box": None,
            }
        return self.mem[track_id]

    def update(self, tracked, frame_w, frame_h):
        now = time.time()
        active_ids = set()
        for det in tracked:
            tid = det.get("track_id", -1)
            if tid < 0:
                continue
            active_ids.add(tid)
            info = self.ensure(tid)
            info["last_seen_ts"] = now
            info["last_box"] = list(det["box"])

            if det["label"] != "person":
                continue

            raw_dist = estimate_person_distance_m(det["box"])
            reliable = person_box_reliable(det["box"], frame_w, frame_h)
            det["raw_dist_m"] = raw_dist
            det["distance_reliable"] = reliable

            if reliable and MIN_VALID_FOLLOW_DIST_M <= raw_dist <= MAX_FOLLOW_DIST_M:
                prev = info["dist_m"]
                smooth_dist = raw_dist if prev is None else (TRACK_DISTANCE_ALPHA * raw_dist + (1.0 - TRACK_DISTANCE_ALPHA) * prev)
                info["dist_m"] = smooth_dist
                info["last_good_ts"] = now
                det["follow_dist_m"] = smooth_dist
                det["distance_source"] = "YOLO"
            else:
                fallback = self.get_recent_distance(tid)
                if fallback is not None:
                    det["follow_dist_m"] = fallback
                    det["distance_source"] = "MEM"
                elif person_box_startup_ok(det["box"], frame_w, frame_h) and MIN_VALID_FOLLOW_DIST_M <= raw_dist <= MAX_FOLLOW_DIST_M:
                    info["dist_m"] = raw_dist
                    info["last_good_ts"] = now
                    det["follow_dist_m"] = raw_dist
                    det["distance_source"] = "YOLO_INIT"
                else:
                    det["follow_dist_m"] = None
                    det["distance_source"] = "NONE"

        dead = []
        for tid, info in self.mem.items():
            if tid not in active_ids and (now - info["last_seen_ts"]) > TRACK_PRUNE_SEC:
                dead.append(tid)
        for tid in dead:
            del self.mem[tid]

    def get_recent_distance(self, track_id):
        info = self.mem.get(track_id)
        if info is None or info["dist_m"] is None:
            return None
        if (time.time() - info["last_good_ts"]) > TRACK_MEMORY_SEC:
            return None
        return float(info["dist_m"])


def pick_target(tracked, frame, appearance, preferred_track_id=None):
    people = [det for det in tracked if det["label"] == "person"]
    if not people:
        if appearance is not None:
            appearance.last_similarity = 0.0
            appearance.last_match_track_id = -1
        return None

    if preferred_track_id is not None:
        for det in people:
            if det.get("track_id") == preferred_track_id:
                det["target_pick_reason"] = "TRACK_ID"
                return det

    if HIST_ENABLED and appearance is not None and appearance.has_reference():
        best_match = None
        best_similarity = HIST_MATCH_THRESHOLD
        frame_w = frame.shape[1]

        for det in people:
            gate_ok = appearance.spatial_gate(det["box"], frame_w)
            det["hist_gate_ok"] = gate_ok
            if not gate_ok:
                det["hist_similarity"] = 0.0
                continue

            score = appearance.compare(frame, det["box"])
            det["hist_similarity"] = score
            if score > best_similarity:
                best_similarity = score
                best_match = det

        appearance.last_similarity = best_similarity if best_match is not None else 0.0
        appearance.last_match_track_id = best_match.get("track_id", -1) if best_match is not None else -1

        if best_match is not None:
            confirm_count = appearance.update_reid_candidate(best_match)
            best_match["hist_confirm_count"] = confirm_count
            if confirm_count >= HIST_REID_CONFIRM_FRAMES:
                best_match["target_pick_reason"] = "HIST"
                return best_match
            return None

        appearance.update_reid_candidate(None)
        return None

    source_priority = {"YOLO": 0, "YOLO_INIT": 0, "MEM": 1, "NONE": 2}
    ranked = sorted(
        people,
        key=lambda d: (
            source_priority.get(d.get("distance_source"), 3),
            d.get("follow_dist_m") if d.get("follow_dist_m") is not None else 999.0,
        ),
    )
    ranked[0]["target_pick_reason"] = "DIST"
    return ranked[0]




class FollowController:
    def __init__(self):
        self.state = STATE_SEARCH
        self.drive_pwm = 0.0
        self.turn_pwm = 0.0
        self.last_target_ts = 0.0
        self.last_turn_sign = 1.0
        self.sign_flip_count = 0
        self.last_target_id = -1
        self.last_follow_dist = None

    def reset_motion(self):
        self.drive_pwm = 0.0
        self.turn_pwm = 0.0

    def compute(self, target, frame_w, uwb=None, ready_to_follow=False, tracked=None, front_m=None, left_m=None, right_m=None,
                front_bias_m=0.0, hard_blocked=False):
        now = time.time()
        uwb = uwb or {}
        uwb_valid = bool(uwb.get("valid"))
        uwb_dist_m = uwb.get("distance_m") if uwb_valid else None
        uwb_angle_deg = uwb.get("angle_deg") if uwb_valid else None

        if uwb_angle_deg is not None:
            if uwb_angle_deg > TURN_SIGN_HYST_DEG:
                new_sign = 1.0
            elif uwb_angle_deg < -TURN_SIGN_HYST_DEG:
                new_sign = -1.0
            else:
                new_sign = self.last_turn_sign

            if new_sign != self.last_turn_sign:
                self.sign_flip_count += 1
                if self.sign_flip_count >= TURN_SIGN_CONFIRM_FRAMES:
                    self.last_turn_sign = new_sign
                    self.sign_flip_count = 0
            else:
                self.sign_flip_count = 0

        obstacle_blocked = (front_m is not None) and (front_m < AUTO_HARD_STOP_FRONT_M)

        # Final indoor behavior: hard stop bubble always overrides everything; stop and wait only, no pivots.
        if obstacle_blocked:
            self.state = STATE_WAIT
            self.drive_pwm = 0.0
            self.turn_pwm = 0.0
            return 0, 0, self.state, 0.0, 0.0

        e_x = 0.0
        e_d = 0.0
        target_ok = uwb_valid and ready_to_follow

        if target_ok:
            target_id = target.get("track_id", -1) if target is not None else -1
            angle_for_control = float(uwb_angle_deg)
            if abs(angle_for_control) < UWB_ANGLE_DEADBAND_DEG:
                angle_for_control = 0.0
            e_x = float(clamp(angle_for_control / max(1.0, UWB_TURN_FULL_SCALE_DEG), -1.0, 1.0))
            e_d = float(uwb_dist_m - DESIRED_DIST_M)
            self.last_target_ts = now
            self.last_target_id = target_id
            self.last_follow_dist = uwb_dist_m
            if target is not None:
                target["control_follow_dist_m"] = uwb_dist_m
                target["uwb_angle_deg"] = uwb_angle_deg

            self.state = STATE_FOLLOW
            if e_d <= -FOLLOW_STOP_MARGIN_M:
                forward_des = 0.0
            else:
                if e_d < 0.0:
                    near_scale = clamp((e_d + FOLLOW_STOP_MARGIN_M) / FOLLOW_STOP_MARGIN_M, 0.0, 1.0)
                    base_forward = FOLLOW_CRUISE_PWM * near_scale
                    extra_forward = 0.0
                else:
                    base_forward = FOLLOW_CRUISE_PWM
                    extra_forward = K_FWD * e_d

                heading_scale = clamp(1.0 - (abs(e_x) / max(0.05, X_GATE)), FOLLOW_MIN_HEADING_SCALE, 1.0)
                forward_des = base_forward + (extra_forward * heading_scale)
                forward_des = clamp(forward_des, 0.0, FWD_MAX_PWM)

            turn_des = clamp(K_TURN * e_x, -TURN_MAX_PWM, TURN_MAX_PWM)

            self.drive_pwm = rate_limit(self.drive_pwm, forward_des, ACCEL_STEP_PWM, DECEL_STEP_PWM)
            self.turn_pwm = rate_limit(self.turn_pwm, turn_des, TURN_STEP_PWM, TURN_STEP_PWM)
        else:
            if not ready_to_follow:
                self.state = STATE_WAIT if uwb_valid else STATE_SEARCH
                self.last_target_ts = 0.0
                self.last_target_id = -1
                self.last_follow_dist = None
                self.drive_pwm = rate_limit(self.drive_pwm, 0.0, ACCEL_STEP_PWM, DECEL_STEP_PWM)
                self.turn_pwm = rate_limit(self.turn_pwm, 0.0, TURN_STEP_PWM, TURN_STEP_PWM)
            elif self.last_target_ts <= 0.0:
                self.state = STATE_SEARCH
                self.drive_pwm = rate_limit(self.drive_pwm, 0.0, ACCEL_STEP_PWM, DECEL_STEP_PWM)
                self.turn_pwm = rate_limit(self.turn_pwm, 0.0, TURN_STEP_PWM, TURN_STEP_PWM)
            else:
                lost_age = now - self.last_target_ts
                if lost_age <= TARGET_LOST_COAST_S:
                    self.state = STATE_COAST
                    self.drive_pwm = rate_limit(self.drive_pwm, 0.0, ACCEL_STEP_PWM, DECEL_STEP_PWM)
                    coast_turn = self.turn_pwm * COAST_TURN_GAIN
                    self.turn_pwm = rate_limit(self.turn_pwm, coast_turn, TURN_STEP_PWM, TURN_STEP_PWM)
                else:
                    self.state = STATE_SEARCH
                    self.drive_pwm = rate_limit(self.drive_pwm, 0.0, ACCEL_STEP_PWM, DECEL_STEP_PWM)
                    if lost_age > TARGET_LOST_SEARCH_S:
                        self.last_follow_dist = None
                        self.last_target_id = -1
                    self.turn_pwm = rate_limit(self.turn_pwm, 0.0, TURN_STEP_PWM, TURN_STEP_PWM)

        enforce_min_move = self.state == STATE_FOLLOW and abs(self.drive_pwm) >= MIN_MOVE_PWM
        left, right = mix_differential(
            self.drive_pwm,
            self.turn_pwm,
            enforce_min_move=enforce_min_move,
            enforce_min_turn=False,
            allow_pivot=True,
        )
        return left, right, self.state, e_x, e_d


class YOLOv8ONNX:
    def __init__(self, model_path):
        providers = ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        input_shape = self.session.get_inputs()[0].shape
        if len(input_shape) >= 4 and isinstance(input_shape[2], int) and isinstance(input_shape[3], int):
            self.input_h = input_shape[2]
            self.input_w = input_shape[3]
        else:
            self.input_h = INPUT_SIZE
            self.input_w = INPUT_SIZE
        print(f"[INFO] ONNX input: {self.input_w}x{self.input_h}")
        print(f"[INFO] ONNX outputs: {self.output_names}")

    def letterbox(self, image, new_shape=(640, 640), color=(114, 114, 114)):
        h, w = image.shape[:2]
        new_w, new_h = new_shape
        r = min(new_w / w, new_h / h)
        resized_w = int(round(w * r))
        resized_h = int(round(h * r))
        resized = cv2.resize(image, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
        dw = (new_w - resized_w) / 2.0
        dh = (new_h - resized_h) / 2.0
        top = int(round(dh - 0.1))
        bottom = int(round(dh + 0.1))
        left = int(round(dw - 0.1))
        right = int(round(dw + 0.1))
        padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
        return padded, r, left, top

    def preprocess(self, image):
        if not USE_PICAMERA2:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        blob, ratio, pad_x, pad_y = self.letterbox(image, (self.input_w, self.input_h))
        blob = blob.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0)
        return blob, ratio, pad_x, pad_y

    def infer(self, image):
        blob, ratio, pad_x, pad_y = self.preprocess(image)
        outputs = self.session.run(self.output_names, {self.input_name: blob})
        return outputs, ratio, pad_x, pad_y

    def postprocess(self, outputs, orig_w, orig_h, ratio, pad_x, pad_y, conf_thres=0.35, iou_thres=0.45):
        pred = outputs[0]
        if pred.ndim == 3:
            pred = pred[0]
        if pred.shape[0] < pred.shape[1] and pred.shape[0] in (84, 85):
            pred = pred.T

        detections = []
        num_classes = len(CLASS_NAMES)
        for row in pred:
            if len(row) < 4 + num_classes:
                continue
            x, y, w, h = row[:4]
            class_scores = row[4:4 + num_classes]
            cls_id = int(np.argmax(class_scores))
            score = float(class_scores[cls_id])
            if score < conf_thres:
                continue

            x1 = (x - w / 2.0 - pad_x) / ratio
            y1 = (y - h / 2.0 - pad_y) / ratio
            x2 = (x + w / 2.0 - pad_x) / ratio
            y2 = (y + h / 2.0 - pad_y) / ratio

            x1 = clamp(x1, 0, orig_w - 1)
            y1 = clamp(y1, 0, orig_h - 1)
            x2 = clamp(x2, 0, orig_w - 1)
            y2 = clamp(y2, 0, orig_h - 1)
            if x2 <= x1 or y2 <= y1:
                continue

            label = CLASS_NAMES[cls_id] if cls_id < len(CLASS_NAMES) else f"class_{cls_id}"
            detections.append({
                "box": [float(x1), float(y1), float(x2), float(y2)],
                "score": score,
                "cls_id": cls_id,
                "label": label,
            })

        return nms_xyxy(detections, iou_thres=iou_thres)


# =========================
# SERIAL HELPERS
# =========================
def init_serial():
    global motor_ser
    print(f"[INFO] Opening motor serial: {MOTOR_SERIAL_PORT}")
    try:
        motor_ser = serial.Serial(MOTOR_SERIAL_PORT, SERIAL_BAUD, timeout=1, write_timeout=1, rtscts=False, dsrdtr=False, xonxoff=False)
        try:
            motor_ser.setDTR(False)
            motor_ser.setRTS(False)
        except Exception:
            pass
        time.sleep(2)
        print("[INFO] Motor serial connected")
    except Exception as e:
        motor_ser = None
        print(f"[WARN] Motor serial unavailable on {MOTOR_SERIAL_PORT}: {e}")


def init_uwb_serial():
    global uwb_ser, uwb_thread_started, uwb_thread
    print(f"[INFO] Opening UWB serial: {UWB_SERIAL_PORT}")
    try:
        uwb_ser = serial.Serial(UWB_SERIAL_PORT, SERIAL_BAUD, timeout=0.1)
        try:
            uwb_ser.reset_input_buffer()
        except Exception:
            pass
        print("[INFO] UWB serial connected")
    except Exception as e:
        uwb_ser = None
        print(f"[WARN] UWB serial unavailable on {UWB_SERIAL_PORT}: {e}")
        return

    if not uwb_thread_started:
        uwb_stop_event.clear()
        uwb_thread_started = True
        uwb_thread = threading.Thread(target=uwb_reader_loop, daemon=True)
        uwb_thread.start()


def send_motor_pwm(m1, m2):
    global motor_ser
    if motor_ser is None:
        return
    try:
        m1 = int(clamp(m1, -PWM_MAX, PWM_MAX))
        m2 = int(clamp(m2, -PWM_MAX, PWM_MAX))
        msg = f"{m1},{m2}\n"
        print(f"[SERIAL OUT] {msg.strip()}")
        motor_ser.write(msg.encode("utf-8"))
        motor_ser.flush()
    except serial.SerialException as e:
        print(f"[MOTOR] Write error: {e}")
        try:
            motor_ser.close()
        except Exception:
            pass
        motor_ser = None


def stop_motors():
    try:
        send_motor_pwm(0, 0)
    except Exception:
        pass


def close_serial():
    global motor_ser
    try:
        stop_motors()
    except Exception:
        pass
    if motor_ser is not None:
        try:
            motor_ser.close()
        except Exception:
            pass
        motor_ser = None


def close_uwb_serial():
    global uwb_ser, uwb_thread_started, uwb_thread
    uwb_stop_event.set()
    if uwb_thread is not None and uwb_thread.is_alive():
        uwb_thread.join(timeout=0.3)
    uwb_thread_started = False
    uwb_thread = None
    if uwb_ser is not None:
        try:
            uwb_ser.close()
        except Exception:
            pass
        uwb_ser = None


# =========================
# ULTRASONIC HELPERS
# =========================
def us_value_is_valid(v):
    return v is not None and np.isfinite(v)


def init_ultrasonics():
    global ultra_thread_started, ultra_thread
    if not USE_ULTRASONICS:
        print("[INFO] Ultrasonics disabled in settings")
        return
    if not GPIO_AVAILABLE:
        print("[WARN] Ultrasonics requested but GPIO not available")
        return
    if ultra_thread_started:
        return

    ultra_stop_event.clear()
    GPIO.setmode(GPIO.BCM)

    trig_pins = sorted({cfg["trig"] for cfg in US_SENSORS.values()})
    for trig_pin in trig_pins:
        GPIO.setup(trig_pin, GPIO.OUT)
        GPIO.output(trig_pin, False)

    for cfg in US_SENSORS.values():
        GPIO.setup(cfg["echo"], GPIO.IN)

    time.sleep(0.25)
    ultra_thread_started = True
    ultra_thread = threading.Thread(target=ultrasonic_thread, daemon=True)
    ultra_thread.start()
    print(f"[INFO] Ultrasonic thread started: {US_SENSORS}")


def close_ultrasonics():
    global ultra_thread_started, ultra_thread
    if not ultra_thread_started:
        return

    ultra_stop_event.set()
    if ultra_thread is not None and ultra_thread.is_alive():
        ultra_thread.join(timeout=0.3)

    if GPIO_AVAILABLE:
        try:
            GPIO.cleanup()
        except Exception:
            pass

    ultra_thread_started = False
    ultra_thread = None


def trigger_pulse(trig_pin):
    if ultra_stop_event.is_set():
        return
    GPIO.output(trig_pin, True)
    time.sleep(0.00001)
    GPIO.output(trig_pin, False)


def read_echo_distance_m(echo_pin):
    deadline = time.time() + US_TIMEOUT_S
    while GPIO.input(echo_pin) == 0:
        if time.time() > deadline:
            return None
    pulse_start = time.time()
    deadline = pulse_start + US_TIMEOUT_S
    while GPIO.input(echo_pin) == 1:
        if time.time() > deadline:
            return None
    pulse_end = time.time()
    dist_m = (pulse_end - pulse_start) * 343.0 / 2.0
    if not (US_MIN_M <= dist_m <= US_MAX_M):
        return None
    return dist_m


def low_pass_filter(new_value, old_value, alpha):
    if old_value is None or not np.isfinite(old_value):
        return new_value
    return alpha * new_value + (1.0 - alpha) * old_value


def ultrasonic_thread():
    global ultra_last_update_s
    while not ultra_stop_event.is_set():
        cycle_values = {}
        for name in US_POLL_SEQUENCE:
            if ultra_stop_event.is_set():
                break

            sensor_cfg = US_SENSORS[name]
            trig_pin = sensor_cfg["trig"]
            echo_pin = sensor_cfg["echo"]

            try:
                trigger_pulse(trig_pin)
                if ultra_stop_event.is_set():
                    break
                dist_m = read_echo_distance_m(echo_pin)
                if dist_m is not None:
                    cycle_values[name] = dist_m
            except Exception as e:
                if not ultra_stop_event.is_set():
                    print(f"[US] Read error on {name}: {e}")

            time.sleep(US_INTER_SENSOR_DELAY_S)

        if cycle_values and not ultra_stop_event.is_set():
            with ultra_lock:
                for name, dist_m in cycle_values.items():
                    alpha = US_FRONT_FILTER_ALPHA if name in FRONT_SENSOR_NAMES else US_FILTER_ALPHA
                    ultra[name] = low_pass_filter(dist_m, ultra.get(name, float("nan")), alpha)
                ultra_last_update_s = time.time()

        time.sleep(US_LOOP_DELAY_S)


def get_ultra_snapshot():
    with ultra_lock:
        snap = dict(ultra)
        ts = ultra_last_update_s
    return snap, ts


def get_front_ultra_m():
    snap, ts = get_ultra_snapshot()
    if (time.time() - ts) > US_STALE_S:
        return None

    front_vals = []
    for name in FRONT_SENSOR_NAMES:
        v = snap.get(name, float("nan"))
        if np.isfinite(v):
            front_vals.append(float(v))

    if not front_vals:
        return None

    return min(front_vals)


def get_front_bias_m():
    snap, ts = get_ultra_snapshot()
    if (time.time() - ts) > US_STALE_S:
        return 0.0

    fl = snap.get("front_left", float("nan"))
    fr = snap.get("front_right", float("nan"))

    if not np.isfinite(fl) or not np.isfinite(fr):
        return 0.0

    return float(fr - fl)


# =========================
# MANUAL MODE HELPERS
# =========================
def manual_command_to_pwm(cmd):
    if cmd == "F":
        return max(FWD_MAX_PWM, MIN_MOVE_PWM), max(FWD_MAX_PWM, MIN_MOVE_PWM), "MANUAL-F"
    if cmd == "B":
        return -max(FWD_MAX_PWM, MIN_MOVE_PWM), -max(FWD_MAX_PWM, MIN_MOVE_PWM), "MANUAL-B"
    if cmd == "R":
        return -max(TURN_MAX_PWM, MIN_TURN_PWM), max(TURN_MAX_PWM, MIN_TURN_PWM), "MANUAL-R"
    if cmd == "L":
        return max(TURN_MAX_PWM, MIN_TURN_PWM), -max(TURN_MAX_PWM, MIN_TURN_PWM), "MANUAL-L"
    return 0, 0, "MANUAL-S"


def set_manual_mode(enabled, stop_now=False):
    global manual_mode_enabled, manual_command, manual_timeout
    with manual_lock:
        manual_mode_enabled = enabled
        manual_timeout = 0.0
        if stop_now:
            manual_command = "S"


def get_manual_state():
    with manual_lock:
        return manual_mode_enabled, manual_command, manual_timeout


def udp_motor_listener():
    global manual_command, manual_timeout
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", UDP_PORT))
    sock.settimeout(0.5)
    print(f"[UDP] Listening on port {UDP_PORT}")

    while True:
        try:
            data, addr = sock.recvfrom(1024)
            cmd = data.decode("utf-8").strip().upper()

            if cmd in ["MANUAL", "M", "MAN", "JOY", "T:1"]:
                set_manual_mode(True, stop_now=True)
                print(f"[UDP] From {addr}: manual mode enabled")
                continue
            if cmd in ["AUTO", "A", "TRACK", "YOLO", "T:0"]:
                set_manual_mode(False, stop_now=True)
                stop_motors()
                print(f"[UDP] From {addr}: auto mode enabled")
                continue
            if cmd in ["F", "B", "L", "R", "S"]:
                with manual_lock:
                    manual_command = cmd
                    manual_timeout = time.time() + MANUAL_HOLD_S
                print(f"[UDP] From {addr}: {cmd}")
                continue
            print(f"[UDP] Ignored unknown command from {addr}: {cmd}")
        except socket.timeout:
            pass
        except Exception as e:
            print(f"[UDP] Error: {e}")


# =========================
# CAMERA SETUP
# =========================
def make_camera():
    if USE_PICAMERA2 and Picamera2 is not None:
        picam2 = Picamera2()
        config = picam2.create_preview_configuration(main={"size": (CAM_W, CAM_H), "format": "RGB888"})
        picam2.configure(config)
        picam2.start()
        time.sleep(1.0)
        return picam2, None

    cap = cv2.VideoCapture(SOURCE)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera/video")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
    return None, cap


def read_frame(picam2, cap):
    if picam2 is not None:
        return picam2.capture_array()
    ok, frame = cap.read()
    return frame if ok else None


# =========================
# MAIN
# =========================
def main():
    print("[INFO] Starting april17full3.py")
    print(f"[INFO] Model: {MODEL_PATH}")
    print(f"[INFO] Auto hard stop front distance: {AUTO_HARD_STOP_FRONT_M:.2f} m")
    print(f"[INFO] UWB port: {UWB_SERIAL_PORT}")
    print(f"[INFO] Motor port: {MOTOR_SERIAL_PORT}")

    udp_thread = threading.Thread(target=udp_motor_listener, daemon=True)
    udp_thread.start()

    detector = YOLOv8ONNX(MODEL_PATH)
    tracker = SimpleTracker(max_misses=MAX_TRACK_MISSES, max_match_dist=MAX_MATCH_DIST)
    controller = FollowController()
    startup_gate = StartupGate()

    init_serial()
    init_uwb_serial()
    init_ultrasonics()
    atexit.register(close_serial)
    atexit.register(close_uwb_serial)
    atexit.register(close_ultrasonics)

    def handle_exit(sig, frame):
        close_serial()
        close_uwb_serial()
        close_ultrasonics()
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    picam2, cap = make_camera()

    out = None
    out_path = None
    if SAVE_VIDEO:
        out_path = make_output_path(OUTPUT_DIR)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(out_path, fourcc, 20.0, (CAM_W, CAM_H))
        print(f"[INFO] Saving video to: {out_path}")

    fps_t0 = time.time()
    fps_count = 0
    fps_val = 0.0

    last_target_id = -1
    last_mode = STATE_SEARCH
    last_left = 0
    last_right = 0
    last_follow_dist = 0.0
    last_front_m = None
    last_ex = 0.0
    last_ed = 0.0
    last_uwb_angle = 0.0
    last_ready = False
    last_ready_time = 0.0
    last_uwb_age = float('inf')

    try:
        while True:
            frame = read_frame(picam2, cap)
            if frame is None:
                print("[WARN] No frame received")
                break

            H, W = frame.shape[:2]
            outputs, ratio, pad_x, pad_y = detector.infer(frame)
            detections = detector.postprocess(outputs, W, H, ratio, pad_x, pad_y, CONF_THRES, IOU_THRES)
            tracked = tracker.update(detections)
            target = pick_camera_target(tracked, W, H, preferred_track_id=last_target_id if last_target_id > 0 else None)
            uwb = get_uwb_snapshot()

            vis = frame.copy()
            person_count = 0
            object_count = 0

            for det in tracked:
                x1, y1, x2, y2 = map(int, det["box"])
                label = det["label"]
                score = det["score"]
                tid = det.get("track_id", -1)

                if label == "person":
                    person_count += 1
                    if det.get("startup_ok"):
                        color = (0, 255, 0)
                    else:
                        color = (0, 165, 255)
                    thickness = 3
                else:
                    object_count += 1
                    color = (255, 128, 0)
                    thickness = 2

                txt = f"{label} ID={tid} {score:.2f}"
                if label == "person":
                    txt += f" cx:{det.get('center_err', 0.0):.2f}"
                    if det.get("startup_ok"):
                        txt += " READY"
                cv2.rectangle(vis, (x1, y1), (x2, y2), color, thickness)
                cv2.putText(vis, txt, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)

            manual_enabled, cmd, timeout_until = get_manual_state()
            ultra_snap_control, ultra_ts_control = get_ultra_snapshot()
            us_age_control = time.time() - ultra_ts_control
            front_m = get_front_ultra_m()
            front_bias_m = get_front_bias_m()

            if us_age_control <= US_STALE_S:
                left_raw = ultra_snap_control.get("left", float("nan"))
                right_raw = ultra_snap_control.get("right", float("nan"))
                left_m = float(left_raw) if np.isfinite(left_raw) else None
                right_m = float(right_raw) if np.isfinite(right_raw) else None
            else:
                left_m = None
                right_m = None

            front_sensor_fresh = front_m is not None
            auto_hard_blocked = (not manual_enabled) and front_sensor_fresh and (front_m <= AUTO_HARD_STOP_FRONT_M)

            if manual_enabled:
                if time.time() < timeout_until:
                    left, right, mode = manual_command_to_pwm(cmd)
                else:
                    left, right, mode = 0, 0, "MANUAL-IDLE"
                controller.reset_motion()
                startup_gate.reset()
                ready_to_follow = False
                e_x = 0.0
                e_d = 0.0
                target_id = -1
                follow_dist = 0.0
            elif auto_hard_blocked:
                left, right, mode = 0, 0, STATE_WAIT
                controller.reset_motion()
                ready_to_follow = False
                e_x = 0.0
                e_d = 0.0
                target_id = -1
                follow_dist = uwb.get("distance_m") or 0.0
            else:
                ready_to_follow = startup_gate.update(uwb, target)
                left, right, mode, e_x, e_d = controller.compute(
                    target,
                    W,
                    uwb=uwb,
                    ready_to_follow=ready_to_follow,
                    tracked=tracked,
                    front_m=front_m,
                    left_m=left_m,
                    right_m=right_m,
                    front_bias_m=front_bias_m,
                    hard_blocked=auto_hard_blocked,
                )
                target_id = target.get("track_id", -1) if target is not None else -1
                follow_dist = uwb.get("distance_m") or 0.0

            if auto_hard_blocked:
                send_motor_pwm(0, 0)
            else:
                send_motor_pwm(right, left)

            if target is not None:
                x1, y1, x2, y2 = map(int, target["box"])
                cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 255), 3)
                target_label = f"TARGET {target.get('target_pick_reason', '?')}"
                if target.get("startup_ok"):
                    target_label += " READY"
                cv2.putText(vis, target_label, (x1, max(20, y1 - 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2, cv2.LINE_AA)

            fps_count += 1
            now = time.time()
            if now - fps_t0 >= 1.0:
                fps_val = fps_count / (now - fps_t0)
                fps_t0 = now
                fps_count = 0

            last_target_id = target_id
            last_mode = mode
            last_left = left
            last_right = right
            last_follow_dist = follow_dist
            last_front_m = front_m
            last_ex = e_x
            last_ed = e_d
            last_ready = ready_to_follow
            last_ready_time = startup_gate.stable_time_s()
            last_uwb_angle = uwb.get("angle_deg") or 0.0
            last_uwb_age = uwb.get("age_s", float('inf'))

            ultra_snap, ultra_ts = get_ultra_snapshot()
            overlay_lines = [
                f"FPS: {fps_val:.1f}",
                f"Mode: {last_mode}",
                f"People: {person_count} | Objects: {object_count}",
                f"Manual: {'ON' if manual_enabled else 'OFF'} Cmd:{cmd} Hold:{max(0.0, timeout_until - time.time()):.2f}s",
                f"Target ID: {last_target_id}",
                f"Ready Latched: {'YES' if last_ready else 'NO'} Stable:{last_ready_time:.2f}/{READY_STABLE_S:.2f}s",
                f"UWB Valid: {'YES' if uwb.get('valid') else 'NO'} Tag:{uwb.get('tag_id', '')}",
                f"UWB Dist: {last_follow_dist:.2f} m  Angle: {last_uwb_angle:.1f} deg  Age:{last_uwb_age:.2f} s",
                f"e_x: {last_ex:.3f}  e_d: {last_ed:.3f}",
                f"Left: {last_left}  Right: {last_right}",
                f"Auto hard stop: {AUTO_HARD_STOP_FRONT_M:.2f} m",
                f"Stop override: {'ACTIVE' if ((not manual_enabled) and (last_front_m is not None) and (last_front_m <= AUTO_HARD_STOP_FRONT_M)) else 'CLEAR'}",
                f"Front US(min): {last_front_m if last_front_m is not None else float('nan'):.2f} m",
                f"US F:{ultra_snap.get('front', float('nan')):.2f}",
                f"US L:{ultra_snap.get('left', float('nan')):.2f} B:{ultra_snap.get('back', float('nan')):.2f}",
                f"US age: {max(0.0, time.time() - ultra_ts):.2f} s",
            ]

            y = 25
            for line in overlay_lines:
                cv2.putText(vis, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2, cv2.LINE_AA)
                y += 28

            if out is not None:
                out.write(cv2.cvtColor(vis, cv2.COLOR_RGB2BGR) if USE_PICAMERA2 else vis)

    finally:
        stop_motors()
        if picam2 is not None:
            try:
                picam2.stop()
            except Exception:
                pass
        if cap is not None:
            cap.release()
        if out is not None:
            out.release()
        close_serial()
        close_uwb_serial()
        close_ultrasonics()
        cv2.destroyAllWindows()
        if out_path is not None:
            print("Saved:", out_path)


if __name__ == "__main__":
    main()
