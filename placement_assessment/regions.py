import json
from pathlib import Path
import cv2,numpy as np
POLICY=json.loads(Path(__file__).with_name('region_policy.json').read_text())

def regions(rgb):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    green = cv2.inRange(hsv, np.array(POLICY['green_hsv_min']), np.array(POLICY['green_hsv_max']))
    red = (((hsv[:, :, 0] <= POLICY['red_hue_max']) | (hsv[:, :, 0] >= POLICY['red_hue_min'])) &
           (hsv[:, :, 1] >= POLICY['red_saturation_min']) & (hsv[:, :, 2] >= POLICY['red_value_min']))
    # No mask closing that could bridge an object/robot gap.
    count, labels, stats, centers = cv2.connectedComponentsWithStats(green, 8)
    candidates = []
    red_distance = cv2.distanceTransform((~red).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) if red.any() else None
    for i in range(1, count):
        x, y, w, h, area = stats[i].tolist()
        if not POLICY['minimum_component_fraction'] <= area / green.size <= POLICY['maximum_component_fraction']:
            continue
        mask = labels == i
        contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        hull_area = cv2.contourArea(cv2.convexHull(max(contours, key=cv2.contourArea)))
        solidity = min(1., area / max(1., hull_area))
        if solidity < POLICY['minimum_solidity']:
            continue
        candidates.append(dict(mask=mask, bbox=[x, y, x+w, y+h], area=area, center=centers[i].tolist(),
                               solidity=solidity, red_gap_px=float(red_distance[mask].min()) if red_distance is not None else None))
    return candidates

