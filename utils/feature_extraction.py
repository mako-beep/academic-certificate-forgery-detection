import cv2
import numpy as np

# =========================
# COMPUTE ELA
# =========================
def compute_ela(img, quality=90):

    _, buffer = cv2.imencode(
        ".jpg",
        img,
        [cv2.IMWRITE_JPEG_QUALITY, quality]
    )

    compressed = cv2.imdecode(
        buffer,
        1
    )

    ela_map = cv2.absdiff(
        img,
        compressed
    )

    return ela_map

# =========================
# FAST GLCM
# =========================
def fast_glcm(
        img,
        vmin=0,
        vmax=255,
        levels=8,
        kernel_size=5,
        distance=1.0,
        angle=0.0):

    mi, ma = vmin, vmax

    h, w = img.shape

    bins = np.linspace(
        mi,
        ma + 1,
        levels + 1
    )

    gl1 = np.digitize(
        img,
        bins
    ) - 1

    dx = distance * np.cos(
        np.deg2rad(angle)
    )

    dy = distance * np.sin(
        np.deg2rad(-angle)
    )

    mat = np.array([
        [1.0, 0.0, -dx],
        [0.0, 1.0, -dy]
    ], dtype=np.float32)

    gl2 = cv2.warpAffine(
        gl1.astype(np.float32),
        mat,
        (w, h),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_REPLICATE
    ).astype(np.uint8)

    glcm = np.zeros(
        (levels, levels, h, w),
        dtype=np.uint8
    )

    for i in range(levels):
        for j in range(levels):

            mask = (
                (gl1 == i) &
                (gl2 == j)
            )

            glcm[i, j, mask] = 1

    kernel = np.ones(
        (kernel_size, kernel_size),
        dtype=np.uint8
    )

    for i in range(levels):
        for j in range(levels):

            glcm[i, j] = cv2.filter2D(
                glcm[i, j],
                -1,
                kernel
            )

    return glcm.astype(np.float32)

# =========================
# GLCM FEATURES
# =========================
def fast_glcm_contrast(
        img,
        levels=8,
        ks=5):

    glcm = fast_glcm(
        img,
        levels=levels,
        kernel_size=ks
    )

    cont = np.zeros(
        img.shape,
        dtype=np.float32
    )

    for i in range(levels):
        for j in range(levels):

            cont += (
                glcm[i, j] *
                (i - j) ** 2
            )

    return cont

def fast_glcm_dissimilarity(
        img,
        levels=8,
        ks=5):

    glcm = fast_glcm(
        img,
        levels=levels,
        kernel_size=ks
    )

    diss = np.zeros(
        img.shape,
        dtype=np.float32
    )

    for i in range(levels):
        for j in range(levels):

            diss += (
                glcm[i, j] *
                np.abs(i - j)
            )

    return diss

def fast_glcm_homogeneity(
        img,
        levels=8,
        ks=5):

    glcm = fast_glcm(
        img,
        levels=levels,
        kernel_size=ks
    )

    homo = np.zeros(
        img.shape,
        dtype=np.float32
    )

    for i in range(levels):
        for j in range(levels):

            homo += (
                glcm[i, j] /
                (1.0 + (i - j) ** 2)
            )

    return homo

# =========================
# FEATURE EXTRACTION
# =========================
def extract_features(img_path):

    img = cv2.imread(img_path)

    if img is None:
        return None

    # =========================
    # RESIZE
    # =========================
    img = cv2.resize(
        img,
        (600, 600)
    )

    # =========================
    # CENTER CROP
    # =========================
    h, w, _ = img.shape

    y1 = int(h * 0.15)
    y2 = int(h * 0.85)

    x1 = int(w * 0.15)
    x2 = int(w * 0.85)

    img = img[
        y1:y2,
        x1:x2
    ]

    img = cv2.resize(
        img,
        (400, 400)
    )

    # =========================
    # GRAYSCALE
    # =========================
    gray = cv2.cvtColor(
        img,
        cv2.COLOR_BGR2GRAY
    )

    # =========================
    # ELA
    # =========================
    ela_map = compute_ela(img)

    ela_gray = cv2.cvtColor(
        ela_map,
        cv2.COLOR_BGR2GRAY
    )

    # =========================
    # BLOCK ANALYSIS
    # =========================
    h, w = ela_gray.shape

    bh = h // 8
    bw = w // 8

    block_means = []

    for i in range(8):
        for j in range(8):

            block = ela_gray[
                i * bh:(i + 1) * bh,
                j * bw:(j + 1) * bw
            ]

            block_means.append(
                np.mean(block)
            )

    # =========================
    # ELA FEATURES
    # =========================
    f_ela_mean = np.mean(ela_gray)

    f_ela_std = np.std(ela_gray)

    f_ela_max = np.max(ela_gray)

    f_block_var = np.var(block_means)

    # =========================
    # GLCM FEATURES
    # =========================
    f_contrast = fast_glcm_contrast(gray).mean()

    f_dissimilarity = \
        fast_glcm_dissimilarity(gray).mean()

    f_homogeneity = \
        fast_glcm_homogeneity(gray).mean()

    # =========================
    # EDGE DENSITY
    # =========================
    edges = cv2.Canny(
        gray,
        100,
        200
    )

    f_edge = np.sum(
        edges > 0
    ) / edges.size

    # =========================
    # GRADIENT
    # =========================
    gx = cv2.Sobel(
        gray,
        cv2.CV_64F,
        1,
        0
    )

    gy = cv2.Sobel(
        gray,
        cv2.CV_64F,
        0,
        1
    )

    f_grad = np.mean(
        np.sqrt(gx**2 + gy**2)
    )

    # =========================
    # BLUR
    # =========================
    f_blur = cv2.Laplacian(
        gray,
        cv2.CV_64F
    ).var()

    # =========================
    # FINAL FEATURES
    # =========================
    return [[
        f_ela_mean,
        f_ela_std,
        f_ela_max,
        f_block_var,
        f_contrast,
        f_dissimilarity,
        f_homogeneity,
        f_edge,
        f_grad,
        f_blur
    ]]