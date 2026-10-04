
import os

import cv2
import numpy as np
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# def read_imgs(img_list):
#     frames = []
#     logger.info('reading images...')
#     for img_path in tqdm(img_list):
#         frame = cv2.imread(img_path)
#         frames.append(frame)
#     return frames

def read_imgs(img_list):
    def load_image(index, img_path):
        return index, cv2.imread(img_path)

    frames = [None] * len(img_list)  # Initialize a list with the same length as img_list
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(load_image, idx, img_path): idx for idx, img_path in enumerate(img_list)}
        for future in tqdm(as_completed(futures), total=len(img_list)):
            idx, img = future.result()
            frames[idx] = img
    return frames

def mirror_index(size, index):
    turn = index // size
    res = index % size
    if turn % 2 == 0:
        return res
    else:
        return size - res - 1


def blend_lower_face(original, generated):
    """Feather a Wav2Lip result into the lower face while preserving eyes/glasses."""
    if original.shape != generated.shape or original.ndim != 3:
        raise ValueError("face blend inputs must have identical HxWxC shapes")
    height, width = original.shape[:2]
    mask = np.zeros((height, width), dtype=np.float32)
    start = max(0, int(height * 0.38))
    full = max(start + 1, int(height * 0.56))
    mask[full:, :] = 1.0
    mask[start:full, :] = np.linspace(0.0, 1.0, full - start, dtype=np.float32)[:, None]
    edge = max(2, int(min(height, width) * 0.055))
    horizontal = np.ones(width, dtype=np.float32)
    horizontal[:edge] = np.linspace(0.0, 1.0, edge, dtype=np.float32)
    horizontal[-edge:] = np.linspace(1.0, 0.0, edge, dtype=np.float32)
    mask *= horizontal[None, :]
    kernel = max(3, edge // 2 * 2 + 1)
    mask = cv2.GaussianBlur(mask, (kernel, kernel), 0)[:, :, None]
    mixed = original.astype(np.float32) * (1.0 - mask) + generated.astype(np.float32) * mask
    return np.clip(mixed, 0, 255).astype(np.uint8)


def composite_wav2lip_face(original, generated, mode=None):
    """Composite a generated face with an explicit, auditable mode.

    ``full`` matches upstream LiveTalking and is useful for quality
    calibration. ``lower`` preserves the glasses/eye region and remains the
    compatibility default until the calibrated UX5 evidence selects a mode.
    """
    selected = (mode or os.environ.get("CW_AVATAR_BLEND_MODE", "lower")).strip().lower()
    if selected == "full":
        if original.shape != generated.shape:
            raise ValueError("face blend inputs must have identical shapes")
        return generated.astype(np.uint8, copy=False)
    if selected == "lower":
        return blend_lower_face(original, generated)
    raise ValueError(f"unsupported Wav2Lip blend mode: {selected}")
