import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score, brier_score_loss, confusion_matrix
from strategies.base_strategy import BaseStrategy
from core.indicators import calculate_rsi, calculate_macd, calculate_bollinger_bands, calculate_atr, calculate_sma
from core.institutional_data import calculate_garman_klass_volatility, calculate_parkinson_volatility

class MLPredictorStrategy(BaseStrategy):
    """
    机构级机器学习预测与概率下注模型 (Institutional ML Hedge Fund Engine)
    - 引入 Garman-Klass 与 Parkinson 高频日内波动率特征
    - Meta-Labeling 概率动态仓位调节 (Probability Bet Sizing: 根据预测胜率缩放头寸)
    - 净化时序交叉验证 (Purged & Embargoed Cross-Validation 机制)
    - 机构风险诊断：ROC-AUC、Brier 校准分数、混淆矩阵、MDI 特征贡献度
    """
    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "model_type": "rf",          # 'rf' or 'gb'
            "n_estimators": 100,
            "max_depth": 5,
            "train_ratio": 0.70,
            "embargo_days": 5,           # 机构去重与隔离期 (Embargo period to prevent leakage)
            "horizon": 3,                # Forward prediction horizon in days
            "prob_threshold": 0.54,      # Multi-factor conviction threshold
            "dynamic_bet_sizing": True   # 机构概率下注调节
        }
        if params:
            default_params.update(params)
        super().__init__("Institutional Machine Learning", default_params)

    def extract_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        close = df['Close']
        high = df['High']
        low = df['Low']
        open_p = df['Open']
        vol = df['Volume'] if 'Volume' in df.columns else pd.Series(1, index=df.index)

        features = pd.DataFrame(index=df.index)

        # 1. Price Momentum & Lagged Returns
        features['ret_1d'] = close.pct_change(1)
        features['ret_3d'] = close.pct_change(3)
        features['ret_5d'] = close.pct_change(5)
        features['ret_10d'] = close.pct_change(10)
        features['ret_20d'] = close.pct_change(20)

        # 2. Moving Average Distance
        sma_10 = calculate_sma(close, 10)
        sma_20 = calculate_sma(close, 20)
        sma_50 = calculate_sma(close, 50)
        features['dist_sma10'] = (close - sma_10) / sma_10
        features['dist_sma20'] = (close - sma_20) / sma_20
        features['dist_sma50'] = (close - sma_50) / sma_50

        # 3. Oscillators & Indicators
        features['rsi_14'] = calculate_rsi(close, 14) / 100.0
        dif, dea, hist = calculate_macd(close, 12, 26, 9)
        features['macd_norm'] = dif / close
        features['macd_hist_norm'] = hist / close

        bb_up, bb_mid, bb_low, pct_b = calculate_bollinger_bands(close, 20, 2.0)
        features['bb_pct_b'] = pct_b.clip(0, 1)

        # 4. Institutional High-Frequency Volatilities
        gk_vol = calculate_garman_klass_volatility(high, low, open_p, close, window=20)
        park_vol = calculate_parkinson_volatility(high, low, window=20)
        features['garman_klass_vol'] = gk_vol / 100.0
        features['parkinson_vol'] = park_vol / 100.0

        atr = calculate_atr(high, low, close, 14)
        features['atr_norm'] = atr / close
        features['hl_spread'] = (high - low) / close
        
        vol_ma20 = calculate_sma(vol, 20)
        features['vol_ratio'] = (vol / vol_ma20.replace(0, np.nan)).fillna(1.0).clip(0.1, 5.0)

        # Target: Forward Return > 0.3% over 'horizon' days
        horizon = int(self.params.get("horizon", 3))
        forward_return = close.shift(-horizon) / close - 1.0
        target = (forward_return > 0.003).astype(int)

        return features, target

    def generate_signals(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict[str, Any]]:
        features, target = self.extract_features(df)
        
        horizon = int(self.params.get("horizon", 3))
        embargo = int(self.params.get("embargo_days", 5))

        valid_mask = features.notna().all(axis=1) & target.notna()
        valid_indices = df.index[valid_mask].tolist()[:-horizon]

        if len(valid_indices) < 60:
            return pd.Series(0, index=df.index), {"error": "Not enough data for ML"}

        X = features.loc[valid_indices]
        y = target.loc[valid_indices]

        # Purged & Embargoed Train-Test Split
        train_ratio = float(self.params.get("train_ratio", 0.70))
        split_idx = int(len(X) * train_ratio)
        train_end_idx = max(10, split_idx - embargo)  # Embargo gap prevents overlapping forward returns

        X_train, y_train = X.iloc[:train_end_idx], y.iloc[:train_end_idx]
        X_test, y_test = X.iloc[split_idx:], y.iloc[split_idx:]

        # Initialize model
        model_type = self.params.get("model_type", "rf")
        n_estimators = int(self.params.get("n_estimators", 100))
        max_depth = int(self.params.get("max_depth", 5))

        if model_type == "gb":
            clf = GradientBoostingClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        else:
            clf = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42, n_jobs=-1)

        clf.fit(X_train, y_train)

        def _get_pos_probs(classifier, dataset):
            if len(dataset) == 0:
                return np.array([], dtype=np.float64)
            proba = classifier.predict_proba(dataset)
            if proba.shape[1] > 1:
                return proba[:, 1]
            elif len(classifier.classes_) == 1 and classifier.classes_[0] == 1:
                return np.ones(len(dataset), dtype=np.float64)
            else:
                return np.zeros(len(dataset), dtype=np.float64)

        # Diagnostics on Out-Of-Sample Test Set
        test_probs = _get_pos_probs(clf, X_test)
        test_preds = (test_probs > 0.5).astype(int) if len(test_probs) > 0 else np.array([])

        accuracy = float(accuracy_score(y_test, test_preds)) if len(y_test) > 0 else 0.0
        precision = float(precision_score(y_test, test_preds, zero_division=0)) if len(y_test) > 0 else 0.0
        recall = float(recall_score(y_test, test_preds, zero_division=0)) if len(y_test) > 0 else 0.0
        brier = float(brier_score_loss(y_test, test_probs)) if len(y_test) > 0 else 0.25

        roc_auc = 0.5
        try:
            if len(np.unique(y_test)) > 1:
                roc_auc = float(roc_auc_score(y_test, test_probs))
        except Exception:
            pass

        # Confusion Matrix
        cm = confusion_matrix(y_test, test_preds).tolist() if len(y_test) > 0 else [[0, 0], [0, 0]]

        # Feature Importance
        feature_names = X.columns.tolist()
        importances = clf.feature_importances_
        feature_importance_list = [
            {"feature": name, "importance": round(float(imp), 4)}
            for name, imp in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
        ]

        # Probability prediction across full series
        all_probs = _get_pos_probs(clf, X)
        prob_series = pd.Series(all_probs, index=valid_indices)

        prob_cutoff = float(self.params.get("prob_threshold", 0.54))
        raw_sigs = np.select([all_probs >= prob_cutoff, all_probs < 0.47], [1, -1], default=0)

        # Out-Of-Sample (OOS) evaluation prevents in-sample overfitting leakage
        eval_mode = str(self.params.get("eval_mode", "oos")).lower()
        signals = pd.Series(0, index=df.index, dtype=int)
        if eval_mode == "oos":
            # Warmup in training phase, strictly trade out-of-sample test period
            signals.loc[valid_indices[split_idx:]] = raw_sigs[split_idx:]
        else:
            signals.loc[valid_indices] = raw_sigs

        # Meta-Labeling Probability Bet Sizing
        use_dynamic_bet = bool(self.params.get("dynamic_bet_sizing", True))
        if use_dynamic_bet:
            # Scale capital fraction according to prediction conviction
            conviction = np.where(all_probs >= prob_cutoff, (all_probs - 0.5) / 0.35, 0.5)
            conviction_clipped = np.clip(conviction, 0.25, 1.0)
            pos_sizes = pd.Series(conviction_clipped, index=valid_indices).reindex(df.index).fillna(1.0)
        else:
            pos_sizes = pd.Series(1.0, index=df.index)

        meta = {
            "model_type": "Random Forest" if model_type == "rf" else "Gradient Boosting",
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "embargo_days": embargo,
            "eval_mode": eval_mode,
            "oos_start_date": str(valid_indices[split_idx]) if split_idx < len(valid_indices) else "",
            "accuracy": round(accuracy * 100.0, 1),
            "precision": round(precision * 100.0, 1),
            "recall": round(recall * 100.0, 1),
            "roc_auc": round(roc_auc, 3),
            "brier_score": round(brier, 3),
            "confusion_matrix": cm,
            "feature_importances": feature_importance_list[:10],
            "prediction_probs": {str(d): round(float(p), 3) for d, p in zip(valid_indices[-60:], all_probs[-60:])},
            "position_sizes": pos_sizes
        }

        return signals, meta
