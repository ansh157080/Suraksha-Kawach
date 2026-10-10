import pandas as pd
import numpy as np
import joblib
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score, precision_recall_curve

# 1. Load data
print("Loading data...")
df = pd.read_csv('credit_card_fraud_10k.csv')

# 2. Adjust device_trust_score to logically match fraud
print("Adjusting device_trust_score logic...")
np.random.seed(42)  # for reproducibility
# If fraud, assign low trust score (0 to 30)
fraud_mask = df['is_fraud'] == 1
df.loc[fraud_mask, 'device_trust_score'] = np.random.randint(0, 31, size=fraud_mask.sum())
# If safe, assign high trust score (60 to 100)
safe_mask = df['is_fraud'] == 0
df.loc[safe_mask, 'device_trust_score'] = np.random.randint(60, 101, size=safe_mask.sum())

# Save the adjusted dataset so it persists
df.to_csv('credit_card_fraud_10k.csv', index=False)

# 3. Preprocess features
print("Preprocessing features...")
# One-hot encode merchant_category
df = pd.get_dummies(df, columns=['merchant_category'])

# Ensure all expected columns are present
expected_features = [
    'amount', 'transaction_hour', 'foreign_transaction', 'location_mismatch',
    'device_trust_score', 'velocity_last_24h', 'cardholder_age',
    'merchant_category_Electronics', 'merchant_category_Food',
    'merchant_category_Grocery', 'merchant_category_Travel'
]

# Create any missing columns with 0s (just in case)
for col in expected_features:
    if col not in df.columns:
        df[col] = 0

# Extract X and y
X = df[expected_features]
y = df['is_fraud']

# 4. Standard Scaling
print("Scaling features...")
scaler = StandardScaler()
X_scaled_array = scaler.fit_transform(X)
X_scaled = pd.DataFrame(X_scaled_array, columns=X.columns)

# Save the scaler
joblib.dump(scaler, 'scaler.pkl')

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42, stratify=y)

# 5. Train XGBoost Model
print("Training XGBoost...")
model = XGBClassifier(n_estimators=100, learning_rate=0.1, max_depth=5, 
                      scale_pos_weight=sum(y==0)/sum(y==1), random_state=42)
model.fit(X_train, y_train)

# Save the model
joblib.dump(model, 'final_xgb_model_clean.pkl')

# 6. Determine Optimal Threshold
print("Finding optimal threshold...")
probs = model.predict_proba(X_test)[:, 1]
precisions, recalls, thresholds = precision_recall_curve(y_test, probs)

# Calculate F1 score for each threshold
f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
best_f1_idx = np.argmax(f1_scores)
optimal_threshold = thresholds[best_f1_idx] if best_f1_idx < len(thresholds) else 0.5

# Save threshold
joblib.dump(optimal_threshold, 'final_threshold_clean.pkl')

print(f"Retraining complete! Saved models. New Threshold: {optimal_threshold:.4f}")
