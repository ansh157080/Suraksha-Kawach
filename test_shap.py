import joblib
import pandas as pd
import shap
model = joblib.load('final_xgb_model_clean.pkl')
scaler = joblib.load('scaler.pkl')
explainer = shap.TreeExplainer(model)
features = model.feature_names_in_

for score in [0, 20, 50, 80, 100]:
    df = pd.DataFrame([[5000.0, 12, 0, 0, score, 5, 30, 1, 0, 0, 0]], columns=features)
    scaled = pd.DataFrame(scaler.transform(df), columns=features)
    shap_vals = explainer.shap_values(scaled)[0]
    idx = list(features).index("device_trust_score")
    print(f"Score {score}: {shap_vals[idx]}")
