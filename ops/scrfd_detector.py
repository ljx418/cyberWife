"""Small offline SCRFD runner used by portrait preprocessing.

The runtime intentionally depends only on OpenCV, NumPy and onnxruntime; it
does not import the full InsightFace package or download models.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


def _distance_to_box(points: np.ndarray, distances: np.ndarray) -> np.ndarray:
    return np.stack(
        (points[:, 0] - distances[:, 0], points[:, 1] - distances[:, 1],
         points[:, 0] + distances[:, 2], points[:, 1] + distances[:, 3]),
        axis=-1,
    )


def _nms(boxes: np.ndarray, threshold: float = 0.4) -> list[int]:
    x1, y1, x2, y2, scores = boxes.T
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size:
        current = int(order[0])
        keep.append(current)
        xx1 = np.maximum(x1[current], x1[order[1:]])
        yy1 = np.maximum(y1[current], y1[order[1:]])
        xx2 = np.minimum(x2[current], x2[order[1:]])
        yy2 = np.minimum(y2[current], y2[order[1:]])
        overlap = np.maximum(0, xx2 - xx1 + 1) * np.maximum(0, yy2 - yy1 + 1)
        iou = overlap / (areas[current] + areas[order[1:]] - overlap)
        order = order[np.where(iou <= threshold)[0] + 1]
    return keep


def detect_faces(image: np.ndarray, model_path: Path, threshold: float = 0.5) -> np.ndarray:
    """Return N x 5 ``x1,y1,x2,y2,confidence`` detections."""
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_cfg = session.get_inputs()[0]
    input_size = (640, 640)
    height, width = image.shape[:2]
    scale = min(input_size[0] / width, input_size[1] / height)
    resized = cv2.resize(image, (int(width * scale), int(height * scale)))
    canvas = np.zeros((input_size[1], input_size[0], 3), dtype=np.uint8)
    canvas[:resized.shape[0], :resized.shape[1]] = resized
    blob = cv2.dnn.blobFromImage(canvas, 1 / 128.0, input_size, (127.5,) * 3, swapRB=True)
    outputs = session.run(None, {input_cfg.name: blob})
    output_count = len(outputs)
    if output_count not in {6, 9, 10, 15}:
        raise RuntimeError(f"unsupported SCRFD outputs: {output_count}")
    feature_count = 3 if output_count in {6, 9} else 5
    strides = [8, 16, 32] if feature_count == 3 else [8, 16, 32, 64, 128]
    anchors = 2 if feature_count == 3 else 1
    candidates: list[np.ndarray] = []
    for index, stride in enumerate(strides):
        scores = np.asarray(outputs[index]).reshape(-1)
        distances = np.asarray(outputs[index + feature_count]).reshape(-1, 4) * stride
        grid_h, grid_w = input_size[1] // stride, input_size[0] // stride
        centers = np.stack(np.mgrid[:grid_h, :grid_w][::-1], axis=-1).astype(np.float32)
        centers = (centers * stride).reshape(-1, 2)
        if anchors > 1:
            centers = np.repeat(centers, anchors, axis=0)
        positive = np.where(scores >= threshold)[0]
        if positive.size:
            decoded = _distance_to_box(centers, distances)
            candidates.append(np.hstack((decoded[positive], scores[positive, None])))
    if not candidates:
        return np.empty((0, 5), dtype=np.float32)
    detections = np.vstack(candidates)
    detections[:, :4] /= scale
    detections = detections[detections[:, 4].argsort()[::-1]]
    return detections[_nms(detections)]
