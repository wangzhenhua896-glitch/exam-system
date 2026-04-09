"""
模型配置管理 API — 管理员通过 Web UI 管理大模型配置
"""
import json
import time
from flask import Blueprint, jsonify, request
from openai import OpenAI

from config.settings import (
    QWEN_CONFIG, GLM_CONFIG, ERNIE_CONFIG, DOUBAO_CONFIG,
    XIAOMI_MIMIMO_CONFIG, MINIMAX_CONFIG, SPARK_CONFIG,
)
from app.models.db_models import (
    get_model_configs, get_model_config, get_effective_config,
    upsert_model_config, delete_model_config,
)

config_bp = Blueprint('config', __name__)

# Provider 元信息（名称 + 默认值 + 可用模型列表）
PROVIDER_META = {
    'qwen': {
        'name': '通义千问 (Qwen)',
        'defaults': QWEN_CONFIG,
        'available_models': [
            {'id': 'qwen-max', 'name': 'Qwen-Max'},
            {'id': 'qwen-plus', 'name': 'Qwen-Plus'},
            {'id': 'qwen-turbo', 'name': 'Qwen-Turbo'},
        ],
    },
    'glm': {
        'name': '智谱 GLM',
        'defaults': GLM_CONFIG,
        'available_models': [
            {'id': 'glm-4', 'name': 'GLM-4'},
            {'id': 'glm-4-flash', 'name': 'GLM-4-Flash'},
        ],
    },
    'doubao': {
        'name': '字节跳动豆包 (Doubao)',
        'defaults': DOUBAO_CONFIG,
        'available_models': DOUBAO_CONFIG.get('available_models', []),
    },
    'ernie': {
        'name': '百度文心一言 (ERNIE)',
        'defaults': ERNIE_CONFIG,
        'available_models': [
            {'id': 'ernie-4.0', 'name': 'ERNIE 4.0'},
            {'id': 'ernie-3.5', 'name': 'ERNIE 3.5'},
        ],
        'extra_fields': [
            {'key': 'secret_key', 'label': 'Secret Key'},
        ],
    },
    'spark': {
        'name': '讯飞星火 (Spark)',
        'defaults': SPARK_CONFIG,
        'available_models': [
            {'id': 'spark-3.5', 'name': 'Spark 3.5'},
            {'id': 'spark-4.0', 'name': 'Spark 4.0'},
        ],
        'extra_fields': [
            {'key': 'app_id', 'label': 'App ID'},
            {'key': 'api_secret', 'label': 'API Secret'},
        ],
    },
    'minimax': {
        'name': 'MiniMax',
        'defaults': MINIMAX_CONFIG,
        'available_models': [
            {'id': 'abab6.5-chat', 'name': 'ABAB 6.5'},
        ],
        'extra_fields': [
            {'key': 'group_id', 'label': 'Group ID'},
        ],
    },
    'xiaomi_mimimo': {
        'name': '小米 Mimimo',
        'defaults': XIAOMI_MIMIMO_CONFIG,
        'available_models': [
            {'id': 'claude-3-5-sonnet', 'name': 'Claude 3.5 Sonnet'},
        ],
    },
}


def _get_config_with_meta(provider: str) -> dict:
    """获取 provider 配置 + 元信息（available_models、extra_fields）"""
    meta = PROVIDER_META.get(provider, {})
    cfg = get_effective_config(provider)

    # 提取 extra_config 中的额外字段
    extra_config = {}
    db_cfg = get_model_config(provider)
    if db_cfg:
        try:
            extra_config = json.loads(db_cfg.get('extra_config', '{}'))
        except (json.JSONDecodeError, TypeError):
            extra_config = {}
    for field in meta.get('extra_fields', []):
        key = field['key']
        if key not in extra_config:
            extra_config[key] = cfg.get(key, '')

    # available_models 标记每个模型的启用状态
    enabled_models = set(extra_config.get('enabled_models', []))
    available_models = []
    for m in meta.get('available_models', []):
        item = dict(m)
        # 如果没有单独设置过 enabled_models，默认全部启用
        item['model_enabled'] = m['id'] in enabled_models if enabled_models else True
        available_models.append(item)

    return {
        'provider': provider,
        'name': meta.get('name', provider),
        'api_key': cfg.get('api_key', ''),
        'base_url': cfg.get('base_url', ''),
        'model': cfg.get('model', ''),
        'enabled': cfg.get('enabled', False),
        'available_models': available_models,
        'extra_fields': meta.get('extra_fields', []),
        'extra_config': extra_config,
    }


@config_bp.route('/models', methods=['GET'])
def list_models():
    """列出所有 provider 的有效配置"""
    configs = []
    for provider in PROVIDER_META:
        configs.append(_get_config_with_meta(provider))
    return jsonify(configs)


@config_bp.route('/models/<provider>', methods=['PUT'])
def update_model(provider):
    """更新某个 provider 的配置"""
    if provider not in PROVIDER_META:
        return jsonify({'error': f'未知的 provider: {provider}'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'error': '请求体为空'}), 400

    # 获取当前有效配置作为基础
    current = _get_config_with_meta(provider)

    api_key = data.get('api_key', current['api_key'])
    base_url = data.get('base_url', current['base_url'])
    model = data.get('model', current['model'])
    enabled = data.get('enabled', current['enabled'])

    # 合并 extra_config
    extra = dict(current['extra_config'])
    if 'extra_config' in data and isinstance(data['extra_config'], dict):
        extra.update(data['extra_config'])

    upsert_model_config(provider, api_key, base_url, model, enabled, json.dumps(extra))
    return jsonify({'success': True, 'message': f'{PROVIDER_META[provider]["name"]} 配置已更新'})


@config_bp.route('/models/<provider>/toggle', methods=['POST'])
def toggle_model(provider):
    """启用/禁用某个 provider"""
    if provider not in PROVIDER_META:
        return jsonify({'error': f'未知的 provider: {provider}'}), 400

    data = request.get_json()
    enabled = data.get('enabled', True)

    current = _get_config_with_meta(provider)
    upsert_model_config(
        provider, current['api_key'], current['base_url'],
        current['model'], enabled, json.dumps(current['extra_config'])
    )
    return jsonify({'success': True, 'enabled': enabled})


@config_bp.route('/models/toggle-all', methods=['POST'])
def toggle_all_models():
    """批量启用/禁用所有 provider"""
    data = request.get_json()
    enabled = data.get('enabled', True)

    for provider in PROVIDER_META:
        current = _get_config_with_meta(provider)
        upsert_model_config(
            provider, current['api_key'], current['base_url'],
            current['model'], enabled, json.dumps(current['extra_config'])
        )
    return jsonify({'success': True, 'enabled': enabled})


@config_bp.route('/models/<provider>/toggle-model', methods=['POST'])
def toggle_single_model(provider):
    """启用/禁用 provider 下的单个模型"""
    if provider not in PROVIDER_META:
        return jsonify({'error': f'未知的 provider: {provider}'}), 400

    data = request.get_json()
    model_id = data.get('model_id', '')
    model_enabled = data.get('enabled', True)

    if not model_id:
        return jsonify({'error': '缺少 model_id'}), 400

    current = _get_config_with_meta(provider)
    extra = dict(current['extra_config'])
    enabled_models = set(extra.get('enabled_models', []))

    # 未设置过 enabled_models 时，先初始化为全部启用
    if not enabled_models:
        meta = PROVIDER_META.get(provider, {})
        enabled_models = {m['id'] for m in meta.get('available_models', [])}

    if model_enabled:
        enabled_models.add(model_id)
    else:
        enabled_models.discard(model_id)

    extra['enabled_models'] = sorted(enabled_models)

    upsert_model_config(
        provider, current['api_key'], current['base_url'],
        current['model'], current['enabled'], json.dumps(extra)
    )
    return jsonify({'success': True, 'model_id': model_id, 'enabled': model_enabled})


@config_bp.route('/models/<provider>/test', methods=['POST'])
def test_model(provider):
    """测试单个 provider 的连通性"""
    if provider not in PROVIDER_META:
        return jsonify({'error': f'未知的 provider: {provider}'}), 400

    config = _get_config_with_meta(provider)
    if not config['api_key']:
        return jsonify({'provider': provider, 'name': config['name'], 'success': False, 'error': '未配置 API Key', 'latency_ms': 0})

    try:
        client = OpenAI(api_key=config['api_key'], base_url=config['base_url'])
        start = time.time()
        response = client.chat.completions.create(
            model=config['model'],
            messages=[{'role': 'user', 'content': '你好'}],
            max_tokens=10,
            stream=False,
        )
        latency = int((time.time() - start) * 1000)
        reply = response.choices[0].message.content
        return jsonify({
            'provider': provider,
            'name': config['name'],
            'success': True,
            'latency_ms': latency,
            'reply': reply[:50] if reply else '',
        })
    except Exception as e:
        return jsonify({
            'provider': provider,
            'name': config['name'],
            'success': False,
            'error': str(e)[:200],
            'latency_ms': 0,
        })


@config_bp.route('/models/test-all', methods=['POST'])
def test_all_models():
    """测试所有已启用 provider 的所有可用模型"""
    results = []
    for provider in PROVIDER_META:
        config = _get_config_with_meta(provider)
        if not config['enabled']:
            results.append({
                'provider': provider,
                'name': config['name'],
                'model': '',
                'success': None,
                'error': '未启用，跳过',
                'latency_ms': 0,
            })
            continue

        if not config['api_key']:
            results.append({
                'provider': provider,
                'name': config['name'],
                'model': '',
                'success': False,
                'error': '未配置 API Key',
                'latency_ms': 0,
            })
            continue

        available_models = config.get('available_models', [])
        # 只测试已启用的模型；没有 available_models 的 provider 测试默认模型
        if available_models:
            models_to_test = [m for m in available_models if m.get('model_enabled', True)]
        else:
            models_to_test = [{'id': config['model'], 'name': config['model']}]

        client = OpenAI(api_key=config['api_key'], base_url=config['base_url'])

        for m in models_to_test:
            model_id = m['id']
            model_name = m.get('name', model_id)
            try:
                start = time.time()
                response = client.chat.completions.create(
                    model=model_id,
                    messages=[{'role': 'user', 'content': '你好'}],
                    max_tokens=10,
                    stream=False,
                )
                latency = int((time.time() - start) * 1000)
                reply = response.choices[0].message.content
                results.append({
                    'provider': provider,
                    'name': config['name'],
                    'model': model_id,
                    'model_name': model_name,
                    'success': True,
                    'latency_ms': latency,
                    'reply': reply[:50] if reply else '',
                })
            except Exception as e:
                results.append({
                    'provider': provider,
                    'name': config['name'],
                    'model': model_id,
                    'model_name': model_name,
                    'success': False,
                    'error': str(e)[:200],
                    'latency_ms': 0,
                })

    return jsonify(results)
