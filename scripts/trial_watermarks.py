import os
import random

import numpy as np

PATH = "/Users/ole/Documents/HG_TRIAL/footwear"
EXPORT_PATH = "/Users/ole/Documents/HG_TRIAL/footwear2"


def get_xy_quarters(img):
    h, w, _ = img.shape
    return (
        (0, 0, w // 2, h // 2),
        (w // 2, 0, w, h // 2),
        (0, h // 2, w // 2, h),
        (w // 2, h // 2, w, h),
    )


def main():
    import cv2

    wm = cv2.imread(
        "/Users/ole/Library/Application Support/Blender/3.2/scripts/addons/HumGen3D/scripts/trial_watermark.png",
        -1,
    )
    hwm, wwm, _ = wm.shape
    for root, dirs, files in os.walk(PATH):
        for file in files:
            if not file.endswith(".png"):
                print(f"Skipping {file}")
                continue
            path = os.path.join(root, file)
            relpath = os.path.relpath(path, PATH)
            export_path = os.path.join(EXPORT_PATH, relpath)
            if not os.path.exists(os.path.dirname(export_path)):
                os.makedirs(os.path.dirname(export_path))
            print(f"Processing {path}")
            img = cv2.imread(path)
            quarters = get_xy_quarters(img)

            filename_seed = hash(file[:6])
            random.seed(filename_seed)
            for quarter in quarters:
                x_min, y_min, x_max, y_max = quarter
                top_left_x = random.randint(x_min, x_max)
                top_left_y = random.randint(y_min, y_max)
                overlay_image_alpha(
                    img, wm[:, :, :3], top_left_x, top_left_y, wm[:, :, 3] / 255.0
                )
            cv2.imwrite(export_path, img)


def overlay_image_alpha(img, img_overlay, x, y, alpha_mask):
    """Overlay `img_overlay` onto `img` at (x, y) and blend using `alpha_mask`.

    `alpha_mask` must have same HxW as `img_overlay` and values in range [0, 1].
    """
    # Image ranges
    y1, y2 = max(0, y), min(img.shape[0], y + img_overlay.shape[0])
    x1, x2 = max(0, x), min(img.shape[1], x + img_overlay.shape[1])

    # Overlay ranges
    y1o, y2o = max(0, -y), min(img_overlay.shape[0], img.shape[0] - y)
    x1o, x2o = max(0, -x), min(img_overlay.shape[1], img.shape[1] - x)

    # Exit if nothing to do
    if y1 >= y2 or x1 >= x2 or y1o >= y2o or x1o >= x2o:
        return

    # Blend overlay within the determined ranges
    img_crop = img[y1:y2, x1:x2]
    img_overlay_crop = img_overlay[y1o:y2o, x1o:x2o]
    alpha = alpha_mask[y1o:y2o, x1o:x2o, np.newaxis]
    alpha_inv = 1.0 - alpha

    img_crop[:] = alpha * img_overlay_crop + alpha_inv * img_crop


if __name__ == "__main__":
    main()
