#!/usr/bin/env python3
"""
Real-Time Driver Drowsiness and Distraction Alert (desktop / laptop version)

Uses your laptop's webcam to monitor:
  * Eye Aspect Ratio (EAR)  -> detects eyes closing / micro-sleep
  * Head pose (yaw & pitch) -> detects looking away from the road

An audible alarm triggers if your eyes stay closed or your head is turned
away for more than 2 seconds.

Usage:
    python drowsiness_detector.py

Controls:
    C  recalibrate (after changing your seating position)
    Q  quit

Requirements: see requirements.txt (Python 3.9+)
"""

import time
import statistics

import cv2
import numpy as np
import mediapipe as mp
import pygame  # reliable cross-platform audio alarm


# --------------------------------------------------------------------------
# Tunables
# --------------------------------------------------------------------------
CLOSED_TIME_LIMIT_S = 2.0     # eyes closed this long -> alarm
AWAY_TIME_LIMIT_S = 2.0       # head turned away this long -> alarm
CALIBRATION_FRAMES = 45       # ~1.5-3 s of looking straight ahead
CLOSED_RATIO = 0.72           # eyes count as closed when EAR < baseline * this
YAW_TOLERANCE = 1.9           # multiplied by calibrated yaw jitter
PITCH_TOLERANCE = 1.9         # multiplied by calibrated pitch jitter
CAMERA_INDEX = 0              # 0 = default camera on the device

# MediaPipe FaceMesh landmark indices
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
NOSE_TIP, CHIN, L_CHEEK, R_CHEEK, FOREHEAD = 1, 152, 234, 454, 10


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def dist(a, b):
    return float(np.linalg.norm(np.array(a) - np.array(b)))


def ear(landmarks, idx):
    """Eye Aspect Ratio of one eye (Soukupová & Čech)."""
    p = [np.array([landmarks[i].x, landmarks[i].y]) for i in idx]
    horizontal = dist(p[0], p[3])
    vertical = (dist(p[1], p[5]) + dist(p[2], p[4])) / 2.0
    return vertical / horizontal if horizontal else 0.0


def head_pose(landmarks):
    """Scale-invariant yaw / pitch proxies from landmark geometry."""
    face_w = dist(
        (landmarks[L_CHEEK].x, landmarks[L_CHEEK].y),
        (landmarks[R_CHEEK].x, landmarks[R_CHEEK].y),
    ) or 1e-6
    face_h = dist(
        (landmarks[FOREHEAD].x, landmarks[FOREHEAD].y),
        (landmarks[CHIN].x, landmarks[CHIN].y),
    ) or 1e-6
    nose = landmarks[NOSE_TIP]
    cx = (landmarks[L_CHEEK].x + landmarks[R_CHEEK].x) / 2
    cy = (landmarks[FOREHEAD].y + landmarks[CHIN].y) / 2
    return (nose.x - cx) / face_w, (nose.y - cy) / face_h


class Alarm:
    """Looping alarm tone via pygame (works on Windows/macOS/Linux)."""

    def __init__(self):
        pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
        self.duration_ms = 500
        self.sample_rate = 44100
        self.tone = self._make_tone()
        self.channel = pygame.mixer.Channel(0)

    def _make_tone(self):
        buf = np.zeros((self.sample_rate,), dtype=np.int16)
        t = np.linspace(0, self.duration_ms / 1000, self.sample_rate, endpoint=False)
        wave = 12000 * np.sign(np.sin(2 * np.pi * 880 * t))
        # simple fade in/out to avoid clicks
        fade = int(0.02 * self.sample_rate)
        envelope = np.ones_like(wave)
        envelope[:fade] = np.linspace(0, 1, fade)
        envelope[-fade:] = np.linspace(1, 0, fade)
        buf[:] = (wave * envelope).astype(np.int16)
        stereo = np.column_stack([buf, buf])
        return pygame.sndarray.make_sound(np.ascontiguousarray(stereo))

    def play(self):
        if not self.channel.get_busy():
            self.channel.play(self.tone, loops=0)


def main():
    alarm = Alarm()

    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise SystemExit(
            f"Could not open camera {CAMERA_INDEX}. "
            "Try changing CAMERA_INDEX at the top of the script."
        )

    print("Look straight at the camera for calibration...")
    calib_ear, calib_yaw, calib_pitch = [], [], []
    eye_closed_start = None
    look_away_start = None
    alert_count = 0
    calibrated = False

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Camera frame grab failed — exiting.")
            break

        frame = cv2.flip(frame, 1)  # mirror view
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)
        h, w = frame.shape[:2]

        if results.multi_face_landmarks:
            lm = results.multi_face_landmarks[0].landmark
            e = (ear(lm, LEFT_EYE) + ear(lm, RIGHT_EYE)) / 2
            yaw, pitch = head_pose(lm)

            if not calibrated:
                calib_ear.append(e)
                calib_yaw.append(yaw)
                calib_pitch.append(pitch)
                cv2.putText(
                    frame,
                    f"Calibrating - look straight ahead ({len(calib_ear)}/{CALIBRATION_FRAMES})",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2,
                )
                if len(calib_ear) >= CALIBRATION_FRAMES:
                    calibrated = True
                    print("Calibrated. Monitoring... (C = recalibrate, Q = quit)")
            else:
                ear_base = statistics.median(calib_ear)
                yaw_base = statistics.median(calib_yaw)
                pitch_base = statistics.median(calib_pitch)
                yaw_jit = max(0.01, statistics.median([abs(v - yaw_base) for v in calib_yaw]))
                pitch_jit = max(0.01, statistics.median([abs(v - pitch_base) for v in calib_pitch]))

                eyes_closed = e < ear_base * CLOSED_RATIO
                turned_away = (
                    abs(yaw - yaw_base) > yaw_jit * YAW_TOLERANCE
                    or abs(pitch - pitch_base) > pitch_jit * PITCH_TOLERANCE
                )
                now = time.time()

                if eyes_closed:
                    eye_closed_start = eye_closed_start or now
                    closed_s = now - eye_closed_start
                    if closed_s >= CLOSED_TIME_LIMIT_S:
                        alarm.play()
                        alert_count += 1
                else:
                    eye_closed_start = None
                    closed_s = 0.0

                if turned_away:
                    look_away_start = look_away_start or now
                    away_s = now - look_away_start
                    if away_s >= AWAY_TIME_LIMIT_S:
                        alarm.play()
                        alert_count += 1
                else:
                    look_away_start = None
                    away_s = 0.0

                # status line
                state = "EYES CLOSED" if eyes_closed else "eyes open"
                if turned_away:
                    state += " | LOOKING AWAY"
                cv2.putText(frame, state, (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (0, 0, 255) if (eyes_closed or turned_away) else (0, 200, 0), 2)
                cv2.putText(frame, f"closed {closed_s:.1f}s  away {away_s:.1f}s  alerts {alert_count}",
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                # draw eye landmarks
                for i in LEFT_EYE + RIGHT_EYE:
                    x, y = int(lm[i].x * w), int(lm[i].y * h)
                    cv2.circle(frame, (x, y), 2, (255, 180, 60), -1)

            # draw the box frame for face bounds
            xs = [p.x * w for p in lm]
            ys = [p.y * h for p in lm]
            cv2.rectangle(frame, (int(min(xs)), int(min(ys))),
                          (int(max(xs)), int(max(ys))), (120, 120, 120), 1)
        else:
            eye_closed_start = None
            look_away_start = None
            if calibrated:
                cv2.putText(frame, "NO FACE DETECTED", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        cv2.imshow("Driver Drowsiness Detector (C recalibrate, Q quit)", frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q")):
            break
        if key in (ord("c"), ord("C")):
            calib_ear, calib_yaw, calib_pitch = [], [], []
            calibrated = False
            eye_closed_start = None
            look_away_start = None
            print("Recalibrating...")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
