import numpy as np
import cv2
import os
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score
)

# =========================
# COMPUTE ELA
# =========================
def compute_ela(img, quality=90):

    _, buffer = cv2.imencode(
        '.jpg',
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
    ks = kernel_size

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
        (ks, ks),
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
def fast_glcm_contrast(img, levels=8, ks=5):

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


def fast_glcm_dissimilarity(img, levels=8, ks=5):

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


def fast_glcm_homogeneity(img, levels=8, ks=5):

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
                (1. + (i - j) ** 2)
            )

    return homo

# =========================
# FEATURE EXTRACTION
# =========================
def extract_features(img_path):

    img = cv2.imread(img_path)

    if img is None:
        return None

    img = cv2.resize(
        img,
        (600, 600)
    )

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

    gray = cv2.cvtColor(
        img,
        cv2.COLOR_BGR2GRAY
    )

    ela_map = compute_ela(img)

    ela_gray = cv2.cvtColor(
        ela_map,
        cv2.COLOR_BGR2GRAY
    )

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

    f_ela_mean = np.mean(ela_gray)
    f_ela_std = np.std(ela_gray)
    f_ela_max = np.max(ela_gray)

    f_block_var = np.var(block_means)

    f_contrast = fast_glcm_contrast(gray).mean()

    f_dissimilarity = \
        fast_glcm_dissimilarity(gray).mean()

    f_homogeneity = \
        fast_glcm_homogeneity(gray).mean()

    edges = cv2.Canny(
        gray,
        100,
        200
    )

    f_edge = np.sum(
        edges > 0
    ) / edges.size

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

    f_blur = cv2.Laplacian(
        gray,
        cv2.CV_64F
    ).var()

    return [
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
    ]

# =========================
# DATASET
# =========================
base_path = "dataset"

X = []
y = []

print("Extracting forensic features...")

for idx, cat in enumerate([
    'forged',
    'genuine'
]):

    folder = os.path.join(
        base_path,
        cat
    )

    if not os.path.exists(folder):
        continue

    for f in os.listdir(folder):

        if f.lower().endswith(
            ('.jpg', '.jpeg', '.png')
        ):

            img_path = os.path.join(
                folder,
                f
            )

            features = extract_features(
                img_path
            )

            if features is not None:

                X.append(features)
                y.append(idx)

X = np.array(X)
y = np.array(y)

print("Feature shape:", X.shape)

# =========================
# CHECK DATASET
# =========================
if len(X) < 10:

    print("NOT_ENOUGH_DATA")
    exit()

# =========================
# SPLIT
# =========================
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    stratify=y,
    random_state=42
)

print("Train:", len(X_train))
print("Test:", len(X_test))

# =========================
# SCALING
# =========================
scaler = StandardScaler()

X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)

# =========================
# MODEL
# =========================
model = SVC(
    kernel='rbf',
    C=10,
    gamma='scale',
    probability=True
)

# =========================
# TRAIN
# =========================
model.fit(
    X_train,
    y_train
)

print("Model trained")

# =========================
# EVALUATION
# =========================
train_pred = model.predict(X_train)
test_pred = model.predict(X_test)

train_accuracy = accuracy_score(
    y_train,
    train_pred
) * 100

test_accuracy = accuracy_score(
    y_test,
    test_pred
) * 100

print(
    f"Training Accuracy: {train_accuracy:.2f}%"
)

print(
    f"Testing Accuracy: {test_accuracy:.2f}%"
)

print(
    classification_report(
        y_test,
        test_pred
    )
)

print(
    confusion_matrix(
        y_test,
        test_pred
    )
)

# =========================
# SAVE TEMP MODEL
# =========================
joblib.dump(
    model,
    'temp_model.pkl'
)

joblib.dump(
    scaler,
    'temp_scaler.pkl'
)

print("Temporary model saved")

# =========================
# FINAL ACCURACY
# =========================
print(
    f"FINAL_ACCURACY:{test_accuracy:.2f}"
)

