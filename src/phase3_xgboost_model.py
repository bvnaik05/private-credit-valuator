import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    roc_auc_score, roc_curve, confusion_matrix, classification_report,
    precision_recall_curve, f1_score, precision_score, recall_score
)
import matplotlib.pyplot as plt
import seaborn as sns
import pickle
import os
from datetime import datetime

def train_xgboost_model():
    """
    Phase 3: Train XGBoost Default Prediction Model
    - Load processed training data
    - Train XGBoost classifier
    - Evaluate on test set
    - Save model and predictions
    """
    
    print("\n" + "="*70)
    print("PHASE 3: XGBOOST DEFAULT PREDICTION MODEL")
    print("="*70)
    
    # ==============================================================================
    # STEP 1: Load processed data
    # ==============================================================================
    print("\n[1/5] LOADING PROCESSED DATA...")
    
    # Load train/test split
    data = np.load('data/processed/train_test_split.npz')
    X_train = data['X_train']
    X_test = data['X_test']
    y_train = data['y_train']
    y_test = data['y_test']
    
    print(f"   ✓ Train: {X_train.shape[0]:,} samples, {X_train.shape[1]} features")
    print(f"   ✓ Test: {X_test.shape[0]:,} samples, {X_test.shape[1]} features")
    print(f"   ✓ Training default rate: {y_train.mean()*100:.2f}%")
    print(f"   ✓ Test default rate: {y_test.mean()*100:.2f}%")
    
    # Load feature names
    with open('data/processed/feature_names.pkl', 'rb') as f:
        feature_names = pickle.load(f)
    
    # ==============================================================================
    # STEP 2: Train XGBoost
    # ==============================================================================
    print("\n[2/5] TRAINING XGBOOST CLASSIFIER...")
    
    # XGBoost hyperparameters optimized for credit classification
    xgb_params = {
        'max_depth': 6,
        'learning_rate': 0.05,
        'n_estimators': 200,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'objective': 'binary:logistic',
        'random_state': 42,
        'eval_metric': 'logloss',
        'scale_pos_weight': (len(y_train) - y_train.sum()) / y_train.sum(),  # Handle class imbalance
        'tree_method': 'hist',
        'device': 'cpu'
    }
    
    # Train model
    model = xgb.XGBClassifier(**xgb_params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )
    
    print("   ✓ XGBoost model trained successfully")
    
    # ==============================================================================
    # STEP 3: Evaluate Model
    # ==============================================================================
    print("\n[3/5] MODEL EVALUATION...")
    
    # Get predictions
    y_pred_proba_train = model.predict_proba(X_train)[:, 1]
    y_pred_proba_test = model.predict_proba(X_test)[:, 1]
    y_pred_test = model.predict(X_test)
    
    # Calculate metrics
    auc_train = roc_auc_score(y_train, y_pred_proba_train)
    auc_test = roc_auc_score(y_test, y_pred_proba_test)
    
    print("   AUC-ROC Scores:")
    print(f"      • Training: {auc_train:.4f}")
    print(f"      • Test: {auc_test:.4f}")
    
    # Classification metrics on test set
    precision = precision_score(y_test, y_pred_test)
    recall = recall_score(y_test, y_pred_test)
    f1 = f1_score(y_test, y_pred_test)
    
    print("\n   Classification Metrics (Test Set @ 0.5 threshold):")
    print(f"      • Precision: {precision:.4f}")
    print(f"      • Recall: {recall:.4f}")
    print(f"      • F1-Score: {f1:.4f}")
    
    # Confusion Matrix
    cm = confusion_matrix(y_test, y_pred_test)
    print("\n   Confusion Matrix:")
    print(f"      • True Negatives: {cm[0,0]:,}")
    print(f"      • False Positives: {cm[0,1]:,}")
    print(f"      • False Negatives: {cm[1,0]:,}")
    print(f"      • True Positives: {cm[1,1]:,}")
    
    # Detailed classification report
    print("\n   Detailed Classification Report:")
    print(classification_report(y_test, y_pred_test, target_names=['No Default', 'Default']))
    
    # ==============================================================================
    # STEP 4: Feature Importance
    # ==============================================================================
    print("\n[4/5] FEATURE IMPORTANCE...")
    
    # Get feature importance
    feature_importance = model.feature_importances_
    feature_importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': feature_importance
    }).sort_values('importance', ascending=False)
    
    print("\n   Top 10 Most Important Features:")
    for i, row in feature_importance_df.head(10).iterrows():
        print(f"      {i+1:2d}. {row['feature']:<25}: {row['importance']:.4f}")
    
    # ==============================================================================
    # STEP 5: Save Model & Predictions
    # ==============================================================================
    print("\n[5/5] SAVING MODEL & ARTIFACTS...")
    
    os.makedirs('models', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save model
    model_path = f'models/xgboost_pd_model_{timestamp}.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"   ✓ Model saved: {model_path}")
    
    # Save feature importance
    feature_importance_df.to_csv(f'models/feature_importance_{timestamp}.csv', index=False)
    print(f"   ✓ Feature importance saved: models/feature_importance_{timestamp}.csv")
    
    # Save predictions
    predictions_df = pd.DataFrame({
        'actual': y_test,
        'pred_default_prob': y_pred_proba_test,
        'pred_class': y_pred_test
    })
    predictions_df.to_csv(f'data/processed/test_predictions_{timestamp}.csv', index=False)
    print(f"   ✓ Test predictions saved: data/processed/test_predictions_{timestamp}.csv")
    
    # ==============================================================================
    # Generate Visualizations
    # ==============================================================================
    print("\n" + "="*70)
    print("GENERATING VISUALIZATIONS...")
    print("="*70)
    
    os.makedirs('outputs/plots', exist_ok=True)
    
    # 1. ROC Curve
    fpr, tpr, _ = roc_curve(y_test, y_pred_proba_test)
    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, label=f'ROC AUC = {auc_test:.4f}', linewidth=2)
    plt.plot([0, 1], [0, 1], 'k--', label='Random', linewidth=1)
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curve - Default Prediction Model')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f'outputs/plots/roc_curve_{timestamp}.png', dpi=300)
    print(f"   ✓ ROC curve saved: outputs/plots/roc_curve_{timestamp}.png")
    plt.close()
    
    # 2. Feature Importance (Top 15)
    top_features = feature_importance_df.head(15)
    plt.figure(figsize=(10, 6))
    plt.barh(top_features['feature'], top_features['importance'])
    plt.xlabel('Importance')
    plt.title('Top 15 Feature Importances - XGBoost')
    plt.tight_layout()
    plt.savefig(f'outputs/plots/feature_importance_{timestamp}.png', dpi=300)
    print(f"   ✓ Feature importance plot saved: outputs/plots/feature_importance_{timestamp}.png")
    plt.close()
    
    # 3. Probability Distribution
    plt.figure(figsize=(10, 6))
    plt.hist(y_pred_proba_test[y_test == 0], bins=50, alpha=0.7, label='Non-Default', density=True)
    plt.hist(y_pred_proba_test[y_test == 1], bins=50, alpha=0.7, label='Default', density=True)
    plt.xlabel('Predicted Default Probability')
    plt.ylabel('Density')
    plt.title('Distribution of Predicted Default Probability (Test Set)')
    plt.legend()
    plt.tight_layout()
    plt.savefig(f'outputs/plots/prob_distribution_{timestamp}.png', dpi=300)
    print(f"   ✓ Probability distribution saved: outputs/plots/prob_distribution_{timestamp}.png")
    plt.close()
    
    # 4. Confusion Matrix Heatmap
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=False,
                xticklabels=['Non-Default', 'Default'],
                yticklabels=['Non-Default', 'Default'])
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.title('Confusion Matrix - Test Set')
    plt.tight_layout()
    plt.savefig(f'outputs/plots/confusion_matrix_{timestamp}.png', dpi=300)
    print(f"   ✓ Confusion matrix saved: outputs/plots/confusion_matrix_{timestamp}.png")
    plt.close()
    
    # 5. SHAP Explainability Analysis
    print("\n[5/5] GENERATING SHAP EXPLAINABILITY PLOTS...")
    try:
        import shap
        
        # Create SHAP explainer (TreeExplainer for XGBoost)
        explainer = shap.TreeExplainer(model)
        
        # Use sample of 500 for speed (SHAP calculations can be intensive)
        sample_size = min(500, X_test.shape[0])
        shap_sample_indices = np.random.choice(X_test.shape[0], size=sample_size, replace=False)
        X_sample = X_test[shap_sample_indices]
        
        print(f"   Computing SHAP values for {sample_size} test samples...")
        shap_values = explainer.shap_values(X_sample)
        
        # SHAP Summary Plot (shows feature importance via SHAP)
        plt.figure(figsize=(12, 8))
        shap.summary_plot(
            shap_values,
            X_sample,
            feature_names=feature_names,
            show=False,
            max_display=15,
            plot_type='bar'
        )
        plt.tight_layout()
        plt.savefig(f'outputs/plots/shap_summary_{timestamp}.png', dpi=300, bbox_inches='tight')
        print(f"   ✓ SHAP summary plot saved: outputs/plots/shap_summary_{timestamp}.png")
        plt.close()
        
        # SHAP Dependence Plot (relationship between feature and prediction)
        # Show for top 3 features
        top_features = feature_importance_df.head(3)['feature'].values
        
        for feature in top_features:
            if feature in feature_names:
                feature_idx = feature_names.index(feature)
                plt.figure()
                shap.dependence_plot(
                    feature_idx,
                    shap_values,
                    X_sample,
                    feature_names=feature_names,
                    show=False
                )
                plt.tight_layout()
                plt.savefig(f'outputs/plots/shap_dependence_{feature}_{timestamp}.png', dpi=300, bbox_inches='tight')
                plt.close()
        
        print(f"   ✓ SHAP dependence plots generated for top 3 features")
        
    except ImportError:
        print("   ⚠️  SHAP not installed. Install with: pip install shap")
    except Exception as e:
        print(f"   ⚠️  SHAP calculation failed: {str(e)}")
    
    # ==============================================================================
    # Summary Report
    # ==============================================================================
    print("\n" + "="*70)
    print("PHASE 3 SUMMARY REPORT")
    print("="*70)
    
    summary = f"""
MODEL PERFORMANCE SUMMARY
========================

Dataset:
  • Training samples: {X_train.shape[0]:,}
  • Test samples: {X_test.shape[0]:,}
  • Total features: {X_train.shape[1]}

Model: XGBoost Classifier
  • Max depth: {xgb_params['max_depth']}
  • Learning rate: {xgb_params['learning_rate']}
  • Estimators: {xgb_params['n_estimators']}

Performance Metrics (Test Set):
  • AUC-ROC: {auc_test:.4f}
  • Precision: {precision:.4f}
  • Recall: {recall:.4f}
  • F1-Score: {f1:.4f}

Feature Importance:
  • Most important feature: {feature_importance_df.iloc[0]['feature']}
  • Top feature importance: {feature_importance_df.iloc[0]['importance']:.4f}

Output Files:
  • Model: {model_path}
  • Predictions: data/processed/test_predictions_{timestamp}.csv
  • Feature importance: models/feature_importance_{timestamp}.csv
"""
    
    print(summary)
    
    # Save summary
    with open(f'outputs/PHASE3_Summary_{timestamp}.txt', 'w') as f:
        f.write(summary)
    
    print("="*70)
    print("✅ PHASE 3 COMPLETE: DEFAULT PREDICTION MODEL TRAINED")
    print("="*70)
    print("\nNext Steps (Phase 4):")
    print("  • Build DCF fair value engine")
    print("  • Calculate expected loss (PD × LGD)")
    print("  • Implement stress testing scenarios")
    print("  • Score full portfolio with PD + FV")
    print("="*70 + "\n")
    
    return model, predictions_df, feature_importance_df

if __name__ == "__main__":
    train_xgboost_model()
