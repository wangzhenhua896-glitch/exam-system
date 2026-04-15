"""
模型配置 CRUD + effective config（DB 覆盖 > .env 默认值）
"""
from typing import Optional, List, Dict
from app.models._db_core import get_db_connection


def get_model_configs() -> List[Dict]:
    """获取所有模型配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM model_configs ORDER BY provider')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_model_config(provider: str) -> Optional[Dict]:
    """获取单个 provider 的模型配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM model_configs WHERE provider = ?', (provider,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_model_config(provider: str, api_key: str, base_url: str, model: str, enabled: bool, extra_config: str = '{}') -> int:
    """新增或更新模型配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT provider FROM model_configs WHERE provider = ?', (provider,))
    existing = cursor.fetchone()
    if existing:
        cursor.execute(
            'UPDATE model_configs SET api_key = ?, base_url = ?, model = ?, enabled = ?, extra_config = ?, updated_at = CURRENT_TIMESTAMP WHERE provider = ?',
            (api_key, base_url, model, 1 if enabled else 0, extra_config, provider)
        )
    else:
        cursor.execute(
            'INSERT INTO model_configs (provider, api_key, base_url, model, enabled, extra_config) VALUES (?, ?, ?, ?, ?, ?)',
            (provider, api_key, base_url, model, 1 if enabled else 0, extra_config)
        )
    conn.commit()
    conn.close()
    return 1


def delete_model_config(provider: str) -> bool:
    """删除模型配置（回退到 .env 默认值）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM model_configs WHERE provider = ?', (provider,))
    conn.commit()
    changes = cursor.rowcount
    conn.close()
    return changes > 0


# provider → .env 默认配置 映射
_PROVIDER_DEFAULTS = {}


def _get_env_defaults():
    """延迟导入，避免循环引用"""
    global _PROVIDER_DEFAULTS
    if not _PROVIDER_DEFAULTS:
        from config.settings import (
            QWEN_CONFIG, GLM_CONFIG, ERNIE_CONFIG, DOUBAO_CONFIG,
            XIAOMI_MIMIMO_CONFIG, MINIMAX_CONFIG, SPARK_CONFIG,
        )
        _PROVIDER_DEFAULTS = {
            'qwen': QWEN_CONFIG,
            'glm': GLM_CONFIG,
            'ernie': ERNIE_CONFIG,
            'doubao': DOUBAO_CONFIG,
            'xiaomi_mimimo': XIAOMI_MIMIMO_CONFIG,
            'minimax': MINIMAX_CONFIG,
            'spark': SPARK_CONFIG,
        }
    return _PROVIDER_DEFAULTS


def get_effective_config(provider: str) -> dict:
    """获取 provider 的有效配置：DB 覆盖 > .env 默认值"""
    import json
    defaults = _get_env_defaults().get(provider, {})

    # 以 .env 默认值为基础，保留所有额外字段（available_models、secret_key 等）
    effective = dict(defaults)
    effective['provider'] = provider

    # DB 覆盖
    db = get_model_config(provider)
    if db:
        if db.get('api_key'):
            effective['api_key'] = db['api_key']
        if db.get('base_url'):
            effective['base_url'] = db['base_url']
        if db.get('model'):
            effective['model'] = db['model']
        effective['enabled'] = bool(db['enabled'])
        try:
            extra = json.loads(db.get('extra_config', '{}')) if db.get('extra_config') else {}
            effective['extra_config'] = extra
        except (json.JSONDecodeError, Exception):
            effective['extra_config'] = {}

    return effective


def get_all_effective_configs() -> dict:
    """获取所有 provider 的有效配置，返回 {provider: config} 字典"""
    defaults = _get_env_defaults()
    result = {}
    for provider in defaults:
        result[provider] = get_effective_config(provider)
    return result
