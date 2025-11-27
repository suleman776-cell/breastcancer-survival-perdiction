from flask import Flask, request, render_template, jsonify, abort
import os
import logging
import pickle
import numpy as np
from typing import Dict, Tuple

# Configure app
app = Flask(__name__)
app.config['MODEL_PATH'] = os.environ.get('MODEL_PATH', os.path.join(os.path.dirname(__file__), 'model_rf.pkl'))
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'False').lower() in ('1', 'true', 'yes')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Feature options (encoded values -> display label)
OPTIONS = {
    'Age': None,  # numeric
    'Race': {0: 'Race 0', 1: 'Race 1', 2: 'Race 2', 3: 'Race 3'},
    'Marital': {0: 'Single', 1: 'Married', 2: 'Other'},
    'Tstage': {0: 'T0', 1: 'T1', 2: 'T2', 3: 'T3'},
    'Nstage': {0: 'N0', 1: 'N1', 2: 'N2', 3: 'N3'},
    'Stage6': {0: 'Stage 0', 1: 'Stage I', 2: 'Stage II', 3: 'Stage III', 4: 'Stage IV'},
    'Diff': {0: 'Differentiation 0', 1: 'Differentiation 1', 2: 'Differentiation 2'},
    'Grade': {1: 'Grade I', 2: 'Grade II', 3: 'Grade III'},
    'Astage': {0: 'A0', 1: 'A1', 2: 'A2'},
    'Tumor': None,  # numeric (size)
    'Estrogen': {0: 'Negative', 1: 'Positive'},
    'Progesterone': {0: 'Negative', 1: 'Positive'},
    'Examined': None,  # numeric
    'Positive': None,   # numeric
}

# Allowed ranges helper (for numeric fields)
NUMERIC_BOUNDS = {
    'Age': (18, 120),
    'Tumor': (0, 200),
    'Examined': (0, 1000),
    'Positive': (0, 1000)
}

# Load model
def load_model(path: str):
    if not os.path.exists(path):
        logger.error("Model file missing: %s", path)
        raise FileNotFoundError(f"Model file not found at: {path}")
    with open(path, 'rb') as f:
        model = pickle.load(f)
    logger.info("Loaded model from %s", path)
    return model

try:
    model_rf = load_model(app.config['MODEL_PATH'])
except Exception as e:
    logger.exception("Failed to load model. The app will still start but prediction will error.")
    model_rf = None

def validate_and_parse(form: Dict) -> Tuple[list, list]:
    """
    Validate form inputs and return (errors, values) where values
    is a list ordered correctly for the model input.
    """
    errors = []
    values = []

    # fields in the exact order required by the model
    fields = ['Age', 'Race', 'Marital', 'Tstage', 'Nstage', 'Stage6',
              'Diff', 'Grade', 'Astage', 'Tumor', 'Estrogen', 'Progesterone',
              'Examined', 'Positive']

    for f in fields:
        raw = form.get(f)
        if raw is None or raw == '':
            errors.append(f"{f} is required")
            continue
        try:
            v = int(raw)
        except ValueError:
            errors.append(f"{f} must be an integer")
            continue

        # numeric bounds check if applicable
        if f in NUMERIC_BOUNDS:
            lo, hi = NUMERIC_BOUNDS[f]
            if not (lo <= v <= hi):
                errors.append(f"{f} must be between {lo} and {hi}")
                continue

        # categorical check: if there are defined options, validate
        opt = OPTIONS.get(f)
        if isinstance(opt, dict) and v not in opt:
            errors.append(f"{f} not a valid option")
            continue

        values.append(v)

    return errors, values

def predict_from_values(vals: list) -> Dict:
    if model_rf is None:
        raise RuntimeError("Model is not loaded")
    arr = np.array([vals])
    pred = model_rf.predict(arr)[0]
    prob = None
    if hasattr(model_rf, 'predict_proba'):
        probs = model_rf.predict_proba(arr)[0]
        # class 1 -> 'Dead' in previous mapping
        prob = float(probs[1]) if len(probs) > 1 else float(probs[0])
    prediction_label = 'Alive' if int(pred) == 0 else 'Dead'
    return {'prediction': prediction_label, 'probability': prob, 'raw_pred': int(pred)}

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    errors = []
    form_values = {}
    if request.method == 'POST':
        errors, vals = validate_and_parse(request.form)
        form_values = {k: request.form.get(k) for k in OPTIONS.keys()}
        if not errors:
            try:
                out = predict_from_values(vals)
                result = out
            except Exception as e:
                logger.exception("Prediction failed")
                errors.append("Prediction failed: " + str(e))

    return render_template('index.html', options=OPTIONS, result=result, errors=errors, form_values=form_values)

@app.route('/api/predict', methods=['POST'])
def api_predict():
    if not request.is_json:
        return jsonify({'error': 'JSON payload required'}), 400
    data = request.get_json()
    # Minimal request payload validation: allow keys in OPTIONS
    payload = {}
    for k in OPTIONS.keys():
        if k not in data:
            return jsonify({'error': f'Missing field: {k}'}), 400
        payload[k] = str(data[k])

    errors, vals = validate_and_parse(payload)
    if errors:
        return jsonify({'errors': errors}), 400
    try:
        out = predict_from_values(vals)
        return jsonify(out)
    except Exception as e:
        logger.exception("API prediction failed")
        return jsonify({'error': 'prediction failed', 'details': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'model_loaded': model_rf is not None})

if __name__ == '__main__':
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    app.run(host=host, port=port, debug=app.config['DEBUG'])