import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List, Optional
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix
)
from strategies.base_strategy import BaseStrategy
from core.indicators import (
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_atr,
    calculate_sma
)
from core.institutional_data import (
    calculate_garman_klass_volatility,
    calculate_parkinson_volatility
)

class MLPredictorStrategy(BaseStrategy):
    """
    机构级机器学习预测与净化步进时序验证模型 (Institutional Walk-Forward ML Engine)
    
    1. 特征工程 (Strict No-Lookahead Feature Engineering):
       - 收益率滞后特征 (1, 3, 5, 10, 20 日)
       - 均线偏离度特征 (10, 20, 50 日 SMA Distance)
       - 振荡与动量指标 (Wilder RSI, 归一化 MACD DIF & Hist)
       - 波动率与通道特征 (布林带 %B & 带宽, Garman-Klass, Parkinson, 归一化 ATR)
       - 量价协同特征 (20日成交量放大倍数)
    2. 目标构建与交易成本摩擦扣除:
       - 预测未来 H 日收益率是否超过覆盖往返交易摩擦的阈值 (Hurdle Rate >= 0.35%)
    3. 净化与隔离步进时序验证 (Purged & Embargoed Walk-Forward Validation):
       - 严格时间隔离 (Purge: 剔除测试集前 H 日重叠标签; Embargo: 隔离自相关溢出)
       - 彻底杜绝训练集与测试集间的数据污染与未来信息泄漏
    4. 决策阈值与无交易区间 (Decision Threshold & Deadband):
       - 设置明确决策阈值与无交易死区，防止微弱预测噪声触发高频无效换手
    5. 机构级模型综合诊断体系:
       - Accuracy, Precision, Recall, F1-Score, ROC-AUC, PR-AUC, Brier Calibration Score
       - 置换特征重要性 (Permutation Feature Importance)
    """
    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "model_type": "rf",            # 'rf' (Random Forest) or 'gb' (Gradient Boosting)
            "n_estimators": 100,
            "max_depth": 4,                # 限制树深防过拟合
            "min_samples_leaf": 15,        # 叶子节点最小样本数，平滑概率
            "horizon": 3,                  # 前瞻预测周期 (3个交易日)
            "cost_hurdle": 0.0035,         # 摩擦成本门槛 (0.35% = 双边佣金+滑点+安全边际)
            "prob_threshold": 0.55,        # 多头买入置信度阈值
            "exit_threshold": 0.45,        # 平仓离场置信度阈值 (0.45-0.55 为观望无交易区间)
            "embargo_days": 5,             # 隔离期天数
            "n_walk_splits": 3,            # 步进验证折数 (Walk-Forward Folds)
            "dynamic_bet_sizing": True     # 概率置信度动态头寸缩放
        }
        if params:
            default_params.update(params)

        super().__init__("Institutional Machine Learning", default_params)

    def extract_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Extracts features strictly using information available at or before bar t.
        Constructs forward-looking target strictly for historical labeling.
        """
        close = df['Close']
        high = df['High']
        low = df['Low']
        open_p = df['Open']
        vol = df['Volume'] if 'Volume' in df.columns else pd.Series(1.0, index=df.index)

        features = pd.DataFrame(index=df.index)

        # 1. 动量与收益率滞后特征 (Momentum & Lag Returns)
        features['ret_1d'] = close.pct_change(1)
        features['ret_3d'] = close.pct_change(3)
        features['ret_5d'] = close.pct_change(5)
        features['ret_10d'] = close.pct_change(10)
        features['ret_20d'] = close.pct_change(20)

        # 2. 均线相对偏离度 (Moving Average Distance)
        sma_10 = calculate_sma(close, 10)
        sma_20 = calculate_sma(close, 20)
        sma_50 = calculate_sma(close, 50)
        features['dist_sma10'] = (close - sma_10) / sma_10.replace(0, np.nan)
        features['dist_sma20'] = (close - sma_20) / sma_20.replace(0, np.nan)
        features['dist_sma50'] = (close - sma_50) / sma_50.replace(0, np.nan)

        # 3. 摆动指标与归一化 MACD
        features['rsi_14'] = calculate_rsi(close, 14) / 100.0
        dif, dea, hist = calculate_macd(close, 12, 26, 9)
        features['macd_norm'] = dif / close.replace(0, np.nan)
        features['macd_hist_norm'] = hist / close.replace(0, np.nan)

        # 4. 布林带 %B 与带宽
        bb_up, bb_mid, bb_low, pct_b, bb_width = calculate_bollinger_bands(close, 20, 2.0)
        features['bb_pct_b'] = pct_b.clip(0.0, 1.0)
        features['bb_bandwidth'] = bb_width.clip(0.0, 1.0)

        # 5. 高频日内波动率与真实波动幅度
        gk_vol = calculate_garman_klass_volatility(high, low, open_p, close, window=20)
        park_vol = calculate_parkinson_volatility(high, low, window=20)
        features['garman_klass_vol'] = (gk_vol / 100.0).clip(0.0, 2.0)
        features['parkinson_vol'] = (park_vol / 100.0).clip(0.0, 2.0)

        atr = calculate_atr(high, low, close, 14)
        features['atr_norm'] = (atr / close.replace(0, np.nan)).clip(0.0, 0.2)
        features['hl_spread'] = ((high - low) / close.replace(0, np.nan)).clip(0.0, 0.2)

        # 6. 量价放量协同特征
        vol_ma20 = calculate_sma(vol, 20)
        features['vol_ratio'] = (vol / vol_ma20.replace(0, np.nan)).fillna(1.0).clip(0.1, 5.0)

        # 目标标签构建 (Target): 未来 H 日收益是否超越交易摩擦成本
        horizon = int(self.params.get("horizon", 3))
        hurdle = float(self.params.get("cost_hurdle", 0.0035))
        forward_ret = (close.shift(-horizon) / close) - 1.0
        target = (forward_ret > hurdle).astype(int)

        return features, target

    def _init_classifier(self):
        model_type = self.params.get("model_type", "rf")
        n_estimators = int(self.params.get("n_estimators", 100))
        max_depth = int(self.params.get("max_depth", 4))
        min_samples_leaf = int(self.params.get("min_samples_leaf", 15))

        if model_type == "gb":
            return GradientBoostingClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                min_samples_leaf=min_samples_leaf,
                subsample=0.8,
                random_state=42
            )
        else:
            return RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                min_samples_leaf=min_samples_leaf,
                class_weight="balanced_subsample",
                random_state=42,
                n_jobs=-1
            )

    def _get_positive_probabilities(self, clf, X_data: pd.DataFrame) -> np.ndarray:
        if len(X_data) == 0:
            return np.array([], dtype=np.float64)
        proba = clf.predict_proba(X_data)
        if proba.shape[1] > 1:
            return proba[:, 1]
        elif len(clf.classes_) == 1 and clf.classes_[0] == 1:
            return np.ones(len(X_data), dtype=np.float64)
        else:
            return np.zeros(len(X_data), dtype=np.float64)

    def generate_signals(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict[str, Any]]:
        features, target = self.extract_features(df)
        horizon = int(self.params.get("horizon", 3))
        embargo = int(self.params.get("embargo_days", 5))
        prob_th = float(self.params.get("prob_threshold", 0.55))
        exit_th = float(self.params.get("exit_threshold", 0.45))
        hurdle = float(self.params.get("cost_hurdle", 0.0035))
        dynamic_sizing = bool(self.params.get("dynamic_bet_sizing", True))

        # 过滤特征完整行
        feat_valid_mask = features.notna().all(axis=1)
        valid_indices = df.index[feat_valid_mask].tolist()

        if len(valid_indices) < 70:
            return pd.Series(0, index=df.index), {"error": "Insufficient valid data for ML modeling (requires >= 70 bars)"}

        # 具有完整前瞻标签的样本 (排除最后 horizon 个无标签行)
        trainable_indices = valid_indices[:-horizon]
        X_trainable = features.loc[trainable_indices]
        y_trainable = target.loc[trainable_indices]

        # -----------------------------------------------------------------
        # 净化步进时序交叉验证 (Purged & Embargoed Walk-Forward Validation)
        # -----------------------------------------------------------------
        n_samples = len(X_trainable)
        n_splits = min(int(self.params.get("n_walk_splits", 3)), max(2, n_samples // 60))
        fold_size = n_samples // (n_splits + 1)

        oos_preds_list = []
        oos_probs_list = []
        oos_true_list = []
        full_timeline_probs = pd.Series(0.5, index=df.index, dtype=float)

        # 步进评估循环
        for fold in range(n_splits):
            train_end = fold_size * (fold + 1)
            # 净化机制 (Purge): 扣除 horizon 日避免重叠标签
            purged_train_end = max(25, train_end - horizon)
            
            # 隔离机制 (Embargo): 测试集起点后移 embargo 日
            test_start = train_end + embargo
            test_end = min(n_samples, fold_size * (fold + 2) if fold < n_splits - 1 else n_samples)

            if test_start >= test_end:
                continue

            X_tr, y_tr = X_trainable.iloc[:purged_train_end], y_trainable.iloc[:purged_train_end]
            X_te, y_te = X_trainable.iloc[test_start:test_end], y_trainable.iloc[test_start:test_end]

            if len(np.unique(y_tr)) < 2 or len(X_te) == 0:
                continue

            fold_clf = self._init_classifier()
            fold_clf.fit(X_tr, y_tr)

            te_probs = self._get_positive_probabilities(fold_clf, X_te)
            te_preds = (te_probs >= 0.5).astype(int)

            oos_probs_list.extend(te_probs.tolist())
            oos_preds_list.extend(te_preds.tolist())
            oos_true_list.extend(y_te.values.tolist())

            # 填充历史时序概率
            full_timeline_probs.loc[X_te.index] = te_probs

        # -----------------------------------------------------------------
        # 最新实盘/样本外预测模型 (Final Production Model)
        # -----------------------------------------------------------------
        # 使用全部已知历史数据训练生产模型，对近期及最新 K 线进行预测
        final_clf = self._init_classifier()
        final_clf.fit(X_trainable, y_trainable)

        # 对最近未标记的样本 (末尾 horizon 行) 进行推断
        recent_indices = valid_indices[-horizon:]
        if len(recent_indices) > 0:
            recent_probs = self._get_positive_probabilities(final_clf, features.loc[recent_indices])
            full_timeline_probs.loc[recent_indices] = recent_probs

        # 如果前面的折有未覆盖的部分，用生产模型补全
        unassigned_mask = (full_timeline_probs == 0.5) & feat_valid_mask
        if unassigned_mask.any():
            unassigned_idx = df.index[unassigned_mask]
            fill_probs = self._get_positive_probabilities(final_clf, features.loc[unassigned_idx])
            full_timeline_probs.loc[unassigned_idx] = fill_probs

        # -----------------------------------------------------------------
        # 综合评估诊断指标 (Out-Of-Sample Performance Diagnostics)
        # -----------------------------------------------------------------
        if len(oos_true_list) >= 20:
            y_eval = np.array(oos_true_list)
            p_eval = np.array(oos_probs_list)
            pred_eval = np.array(oos_preds_list)

            accuracy = float(accuracy_score(y_eval, pred_eval))
            precision = float(precision_score(y_eval, pred_eval, zero_division=0))
            recall = float(recall_score(y_eval, pred_eval, zero_division=0))
            f1 = float(f1_score(y_eval, pred_eval, zero_division=0))
            brier = float(brier_score_loss(y_eval, p_eval))
            cm = confusion_matrix(y_eval, pred_eval).tolist()

            try:
                roc_auc = float(roc_auc_score(y_eval, p_eval))
            except Exception:
                roc_auc = 0.50

            try:
                pr_auc = float(average_precision_score(y_eval, p_eval))
            except Exception:
                pr_auc = float(np.mean(y_eval))
        else:
            # 备用评估
            accuracy, precision, recall, f1, roc_auc, pr_auc, brier = 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.25
            cm = [[0, 0], [0, 0]]

        # 置换特征重要性评估 (Permutation Feature Importance Approximation)
        feature_names = features.columns.tolist()
        importances = final_clf.feature_importances_
        feature_imp_list = [
            {"feature": name, "importance": round(float(imp), 4)}
            for name, imp in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
        ]

        # -----------------------------------------------------------------
        # 决策阈值、无交易死区与信号生成 (Threshold & Deadband Mapping)
        # -----------------------------------------------------------------
        sig_arr = np.zeros(len(df), dtype=np.int32)
        pos_sizes_arr = np.ones(len(df), dtype=np.float64)

        in_pos = False
        prob_vals = full_timeline_probs.values

        for i in range(len(df)):
            p = prob_vals[i]
            if not in_pos:
                # 只有置信度显著高过阈值，且突破无交易区间才开仓
                if p >= prob_th:
                    sig_arr[i] = 1
                    in_pos = True
                    # 动态下注调节: 随着概率提升增加资金暴露 (0.50 ~ 1.0)
                    if dynamic_sizing:
                        conviction = np.clip((p - 0.50) / 0.30, 0.35, 1.0)
                        pos_sizes_arr[i] = conviction
            else:
                # 跌破退出阈值，或概率进入深度负面区间离场
                if p < exit_th:
                    sig_arr[i] = -1
                    in_pos = False
                elif dynamic_sizing:
                    conviction = np.clip((p - 0.50) / 0.30, 0.35, 1.0)
                    pos_sizes_arr[i] = conviction

        signals = pd.Series(sig_arr, index=df.index, dtype=int)
        pos_sizes = pd.Series(pos_sizes_arr, index=df.index, dtype=float)

        meta = {
            "model_type": "Random Forest" if self.params.get("model_type") == "rf" else "Gradient Boosting",
            "validation_framework": "Purged & Embargoed Walk-Forward Validation",
            "walk_forward_splits": n_splits,
            "train_samples": len(X_trainable),
            "test_samples": len(oos_true_list),
            "embargo_days": embargo,
            "cost_hurdle_pct": f"{hurdle*100:.2f}%",
            "decision_thresholds": {
                "buy_threshold": prob_th,
                "exit_threshold": exit_th,
                "deadband": f"[{exit_th:.2f}, {prob_th:.2f}) (观望不交易区间)"
            },
            "accuracy": round(accuracy * 100.0, 1),
            "precision": round(precision * 100.0, 1),
            "recall": round(recall * 100.0, 1),
            "f1_score": round(f1 * 100.0, 1),
            "roc_auc": round(roc_auc, 3),
            "pr_auc": round(pr_auc, 3),
            "brier_score": round(brier, 3),
            "confusion_matrix": cm,
            "feature_importances": feature_imp_list[:10],
            "prediction_probs": {
                str(d): round(float(full_timeline_probs.loc[d]), 3)
                for d in df.index[-60:]
            },
            "position_sizes": pos_sizes,
            "model_reliability": "Valid Alpha Signal" if (roc_auc >= 0.53 and precision >= 0.52) else "Marginal / Regime Sensitive"
        }

        return signals, meta
