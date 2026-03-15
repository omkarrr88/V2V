"""
export_model.py — Export Trained XGBoost Model for Deployment
==============================================================
Exports the trained BSD XGBoost model to ONNX format for embedded
deployment on automotive hardware (ONNX Runtime / TensorRT).

Usage: python export_model.py
Output: ../Outputs/bsd_model.onnx
"""
import os
import sys
import json
import numpy as np

def main():
    model_path = os.path.join('..', 'Outputs', 'bsd_xgboost_model.json')
    report_path = os.path.join('..', 'Outputs', 'bsd_training_report.json')
    onnx_path = os.path.join('..', 'Outputs', 'bsd_model.onnx')

    if not os.path.exists(model_path):
        print(f"❌ Model file not found: {model_path}")
        print("   Run train_ai_model.py first.")
        sys.exit(1)

    # Load model info for feature count
    n_features = 18  # default
    if os.path.exists(report_path):
        with open(report_path) as f:
            info = json.load(f)
            n_features = len(info.get('features', []))
            print(f"📄 Model features: {n_features}")

    try:
        import xgboost as xgb
        import onnxmltools
        from onnxmltools.convert import convert_xgboost
        from onnxconverter_common import FloatTensorType

        model = xgb.XGBClassifier()
        model.load_model(model_path)

        initial_type = [('float_input', FloatTensorType([None, n_features]))]
        onnx_model = convert_xgboost(model, initial_types=initial_type)

        with open(onnx_path, 'wb') as f:
            f.write(onnx_model.SerializeToString())

        print(f"✅ ONNX model exported to {onnx_path}")
        print(f"   File size: {os.path.getsize(onnx_path) / 1024:.1f} KB")
        print(f"   Ready for ONNX Runtime or TensorRT deployment")

    except ImportError as e:
        print(f"⚠️  ONNX export requires additional packages: {e}")
        print("   Install with: pip install onnxmltools onnxconverter-common")
        print("\n   Falling back to XGBoost JSON format (universally loadable)...")

        # Always provide the JSON format export as fallback
        import xgboost as xgb
        booster = xgb.Booster()
        booster.load_model(model_path)
        deploy_path = os.path.join('..', 'Outputs', 'bsd_model_deploy.json')
        booster.save_model(deploy_path)
        print(f"✅ XGBoost JSON model saved to {deploy_path}")
        print(f"   This can be loaded by any XGBoost runtime (C++, Java, Python)")

    # Print deployment checklist
    print("\n📋 Deployment Checklist:")
    print("   1. Load model on embedded ECU (ONNX Runtime / XGBoost C++ API)")
    print("   2. Feed 18 features per BSM cycle (see bsd_training_report.json)")
    print("   3. Inference latency target: < 10ms per vehicle pair")
    print("   4. Physics model (BSDEngine) remains primary authority")
    print("   5. AI model provides complementary CRITICAL-class recall")


if __name__ == '__main__':
    main()
