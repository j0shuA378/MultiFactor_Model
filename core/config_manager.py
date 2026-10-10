import os
import json
import logging
from datetime import datetime

logger = logging.getLogger("ConfigManager")

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "config.json")

DEFAULT_CONFIG = {
    "account": {
        "initial_capital": 100000.0,
        "commission_rate": 0.05,
        "slippage_rate": 0.05,
        "stop_loss_pct": None,
        "take_profit_pct": None
    },
    "momentum": {
        "preset_id": "aqr_momentum",
        "w_mom_12_1": 0.30,
        "w_risk_adj": 0.25,
        "w_residual": 0.20,
        "w_trend_qual": 0.15,
        "w_vol_confirm": 0.10,
        "use_vol_target": True,
        "target_vol": 15.0,
        "z_win": 30,
        "alpha_th": 0.30,
        "exit_th": -0.20,
        "fast_ma": 10,
        "slow_ma": 30
    },
    "ml": {
        "model_type": "rf",
        "n_estimators": 100,
        "max_depth": 5,
        "prob_threshold": 0.55,
        "train_split": 0.70
    },
    "turtle": {
        "donchian_entry": 20,
        "donchian_exit": 10,
        "atr_period": 20,
        "risk_pct": 1.0,
        "stop_loss_n": 2.0
    },
    "updated_at": "2026-10-10T14:50:00"
}

INSTITUTIONAL_PRESETS = [
    {
        "id": "aqr_momentum",
        "name": "AQR 动量优化型 (低波动缩放 + 残差Alpha)",
        "tag": "AQR Style",
        "description": "借鉴 AQR 资本经典风格：重仓特质波动率缩放与残差动量，开启动态波动率目标仓位管理，平滑回撤。",
        "config": {
            "w_mom_12_1": 0.30,
            "w_risk_adj": 0.25,
            "w_residual": 0.20,
            "w_trend_qual": 0.15,
            "w_vol_confirm": 0.10,
            "use_vol_target": True,
            "target_vol": 15.0,
            "alpha_th": 0.30,
            "exit_th": -0.20,
            "fast_ma": 10,
            "slow_ma": 30
        }
    },
    {
        "id": "bridgewater_all_weather",
        "name": "桥水全天候风险平价型 (注重路径质量与低波)",
        "tag": "Bridgewater Style",
        "description": "借鉴 Bridgewater 全天候风险均衡理念：大幅增加波动率调整与 R² 路径平滑度权重，目标年化波动率收敛至 12%。",
        "config": {
            "w_mom_12_1": 0.20,
            "w_risk_adj": 0.35,
            "w_residual": 0.15,
            "w_trend_qual": 0.20,
            "w_vol_confirm": 0.10,
            "use_vol_target": True,
            "target_vol": 12.0,
            "alpha_th": 0.25,
            "exit_th": -0.15,
            "fast_ma": 12,
            "slow_ma": 36
        }
    },
    {
        "id": "classic_jegadeesh",
        "name": "经典 JT 12M-1M 动量 (学术截面基准)",
        "tag": "Jegadeesh & Titman",
        "description": "基于 Jegadeesh & Titman (1993) 经典文献：以 12M-1M 纯动量为主导核心 (55%)，纯净捕捉中长期溢价。",
        "config": {
            "w_mom_12_1": 0.55,
            "w_risk_adj": 0.15,
            "w_residual": 0.10,
            "w_trend_qual": 0.10,
            "w_vol_confirm": 0.10,
            "use_vol_target": False,
            "target_vol": 18.0,
            "alpha_th": 0.35,
            "exit_th": -0.25,
            "fast_ma": 10,
            "slow_ma": 30
        }
    },
    {
        "id": "goldman_quant",
        "name": "高盛量化激进趋势型 (量价协同 + 敏捷Alpha)",
        "tag": "Goldman Sachs Quant",
        "description": "偏向高敏捷多头进攻：调高量价放量协同 (25%) 与纯截面动量 (35%)，缩短 EMA 快慢线均线滤波，快速响应突破。",
        "config": {
            "w_mom_12_1": 0.35,
            "w_risk_adj": 0.15,
            "w_residual": 0.15,
            "w_trend_qual": 0.10,
            "w_vol_confirm": 0.25,
            "use_vol_target": True,
            "target_vol": 20.0,
            "alpha_th": 0.40,
            "exit_th": -0.30,
            "fast_ma": 8,
            "slow_ma": 24
        }
    },
    {
        "id": "balanced_institutional",
        "name": "标准机构平衡配置 (五大支柱均权)",
        "tag": "Standard Balanced",
        "description": "五大动量支柱各按 20% 均匀配置，不偏科，兼具稳定性与 Alpha 捕捉能力。",
        "config": {
            "w_mom_12_1": 0.20,
            "w_risk_adj": 0.20,
            "w_residual": 0.20,
            "w_trend_qual": 0.20,
            "w_vol_confirm": 0.20,
            "use_vol_target": True,
            "target_vol": 15.0,
            "alpha_th": 0.30,
            "exit_th": -0.20,
            "fast_ma": 10,
            "slow_ma": 30
        }
    }
]

def ensure_config_dir():
    d = os.path.dirname(CONFIG_FILE)
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def load_config() -> dict:
    """Loads configuration from data/config.json, falling back to DEFAULT_CONFIG"""
    ensure_config_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge with default to guarantee completeness
                merged = json.loads(json.dumps(DEFAULT_CONFIG))
                for section in ["account", "momentum", "ml", "turtle"]:
                    if section in data and isinstance(data[section], dict):
                        merged[section].update(data[section])
                if "updated_at" in data:
                    merged["updated_at"] = data["updated_at"]
                return merged
        except Exception as e:
            logger.warning(f"Error loading {CONFIG_FILE}: {e}. Using defaults.")

    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG

def save_config(new_config: dict) -> dict:
    """Saves configuration dict to data/config.json"""
    ensure_config_dir()
    merged = load_config() if os.path.exists(CONFIG_FILE) else json.loads(json.dumps(DEFAULT_CONFIG))
    for section in ["account", "momentum", "ml", "turtle"]:
        if section in new_config and isinstance(new_config[section], dict):
            merged[section].update(new_config[section])

    merged["updated_at"] = datetime.now().isoformat()
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        return merged
    except Exception as e:
        logger.error(f"Error saving {CONFIG_FILE}: {e}")
        return merged

def apply_preset(preset_id: str) -> dict:
    """Applies a preset to momentum config and saves"""
    preset = next((p for p in INSTITUTIONAL_PRESETS if p["id"] == preset_id), None)
    if not preset:
        raise ValueError(f"Preset '{preset_id}' not found")
    
    current = load_config()
    current["momentum"].update(preset["config"])
    current["momentum"]["preset_id"] = preset_id
    return save_config(current)

def reset_to_defaults() -> dict:
    """Resets configuration to factory defaults"""
    return save_config(DEFAULT_CONFIG)
