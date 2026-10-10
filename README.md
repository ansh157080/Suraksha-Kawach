# Suraksha Kawach

Suraksha Kawach is an AI-powered fraud intelligence and secure transaction monitoring system built with Python and Streamlit. It helps detect suspicious digital payments, simulates banking workflows, and provides explainable risk insights for financial transactions.

## Overview

The project combines:
- a credit-card fraud detection model trained on transaction features,
- a web dashboard for bank and user-side simulation,
- secure local authentication for users,
- transaction risk scoring with SHAP-based explainability,
- PDF receipt generation and QR verification for safe/unsafe transactions.

It is designed as a demo fintech/security application to showcase how AI can support fraud detection and user trust in digital payment environments.

## Key Features

- User authentication and registration
- Secure session-based access flow
- Bank system mode and user simulation mode
- AI risk score generation for incoming payments
- Fraud, medium-risk, and safe verdict classification
- SHAP explainability for model decisions
- Transaction history and verdict tracking
- PDF receipt generation with transaction hash and QR code
- SQLite-backed user database

## Tech Stack

- Python
- Streamlit
- Pandas / NumPy
- XGBoost
- Scikit-learn
- SHAP
- Plotly
- FPDF
- qrcode
- SQLite

## Project Structure

```text
Mini_Project -PRO/
├── app.py                  # Main Streamlit application
├── auth_db.py             # Authentication and SQLite DB logic
├── credit_card_fraud_10k.csv
├── retrain.py             # Model retraining script
├── retrain2.py            # Additional retraining / experimentation file
├── retrain3.py            # Additional retraining / experimentation file
├── final_xgb_model_clean.pkl
├── final_threshold_clean.pkl
├── scaler.pkl
├── users.db               # Local SQLite database for users
├── shap_explainer.pkl
├── .venv                  # Local virtual environment
└── README.md
```

## Installation

1. Open a terminal in the project folder.
2. Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install streamlit pandas numpy joblib shap plotly fpdf qrcode xgboost scikit-learn
```

## Running the App

From the project directory:

```bash
streamlit run app.py
```

Then open the local URL shown in the terminal (typically http://localhost:8501).

## How It Works

- The application loads a trained XGBoost fraud detection model.
- The model predicts whether a transaction is suspicious based on features like amount, hour, merchant type, and device trust.
- A threshold is used to classify results as safe, medium-risk, or high-risk.
- SHAP is used to explain which features contributed most to the model verdict.
- User authentication is handled through SQLite, and the system supports multiple login modes.

## Notes

- The application creates the SQLite database automatically when needed.
- Model artifacts such as `.pkl` files are loaded at runtime.
- The project is intended for demo and educational use in fraud analytics and secure payment simulation.

## License

This project is provided for educational and demonstration purposes.

## Contact / Repository

Repository: `ansh157080/Suraksha-Kawach`
