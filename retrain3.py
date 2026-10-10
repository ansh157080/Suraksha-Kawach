import pandas as pd
import numpy as np
import joblib
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

df = pd.read_csv('credit_card_fraud_10k.csv')
encoded_df = pd.get_dummies(df, columns=['merchant_category'])

expected_features = [
    'amount', 'transaction_hour', 'foreign_transaction', 'location_mismatch',
    'device_trust_score', 'velocity_last_24h', 'cardholder_age',
    'merchant_category_Electronics', 'merchant_category_Food',
    'merchant_category_Grocery', 'merchant_category_Travel'
]

for col in expected_features:
    if col not in encoded_df.columns:
        encoded_df[col] = 0

X = encoded_df[expected_features]
y = encoded_df['is_fraud']

scaler = StandardScaler()
X_scaledArray = scaler.fit_transform(X)
X_scaled = pd.DataFrame(X_scaledArray, columns=X.columns)
joblib.dump(scaler, 'scaler.pkl')

X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42, stratify=y)
# L2 reg = 5, lower learning_rate=0.03 to make probabilities beautifully smooth!
# pos_weight=20 gently boosts it without snapping to 99% immediately.
model = XGBClassifier(n_estimators=100, learning_rate=0.03, max_depth=3, scale_pos_weight=10, random_state=42, reg_lambda=5.0)
model.fit(X_train, y_train)

joblib.dump(model, 'final_xgb_model_clean.pkl')
joblib.dump(0.5, 'final_threshold_clean.pkl')  # Standard balanced anchor
print("Model dynamically retrained for smooth probabilities.")
