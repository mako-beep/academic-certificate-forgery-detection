import joblib
import numpy as np

# =========================
# LOAD MODEL & SCALER
# =========================
model = joblib.load("svm_model.pkl")

scaler = joblib.load("scaler.pkl")

# =========================
# PREDICT DOCUMENT
# =========================
def predict_document(features):

    try:

        # =========================
        # CONVERT TO NUMPY
        # =========================
        features = np.array(features)

        # =========================
        # SCALE FEATURES
        # =========================
        features = scaler.transform(features)

        # =========================
        # MODEL PREDICTION
        # =========================
        prediction = model.predict(features)

        # =========================
        # PROBABILITY
        # =========================
        probabilities = model.predict_proba(features)

        confidence = round(
            float(np.max(probabilities) * 100),
            2
        )

        predicted_label = prediction[0]

        # =========================
        # AI DECISION LOGIC
        # =========================

        # LABEL 0 = FORGED
        if predicted_label == 0:

            if confidence >= 55:

                result = "Forged"

                status = "Completed"

            else:

                result = "Pending"

                status = "Not Completed"

        # LABEL 1 = GENUINE
        else:

            if confidence >= 50:

                result = "Genuine"

                status = "Completed"

            else:

                result = "Pending"

                status = "Not Completed"

        # =========================
        # RETURN RESULTS
        # =========================
        return result, confidence, status

    except Exception as e:

        print("Prediction Error:", e)

        return "Prediction Failed", 0, "Error"