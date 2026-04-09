"""
模型注册表
管理所有可用的国产大模型
"""

from typing import Dict, Any, List, Optional
from .base import BaseModelClient, ModelProvider


class ModelRegistry:
    """模型注册表"""
    
    _instance: Optional["ModelRegistry"] = None
    _models: Dict[str, BaseModelClient] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, model: BaseModelClient) -> None:
        """注册模型"""
        key = f"{model.provider.value}_{model.model_name}"
        self._models[key] = model
    
    def get(self, key: str) -> Optional[BaseModelClient]:
        """获取模型"""
        return self._models.get(key)
    
    def get_enabled_models(self) -> List[BaseModelClient]:
        """获取所有启用的模型"""
        return [m for m in self._models.values() if m.enabled]
    
    def get_model_by_provider(self, provider: ModelProvider) -> Optional[BaseModelClient]:
        """根据提供商获取模型"""
        for model in self._models.values():
            if model.provider == provider and model.enabled:
                return model
        return None
    
    def list_models(self) -> List[Dict[str, Any]]:
        """列出所有模型"""
        return [m.get_info() for m in self._models.values()]
    
    def clear(self) -> None:
        """清空注册表"""
        self._models.clear()


# 全局实例
model_registry = ModelRegistry()


def init_models(config: Dict[str, Any]) -> None:
    """
    初始化所有模型

    Args:
        config: 配置字典，包含各模型的配置
    """
    from .qwen import QwenClient

    # 通义千问 (使用 openai 兼容接口，无需额外 SDK)
    qwen_cfg = config.get("qwen", {})
    if qwen_cfg.get("enabled", False):
        # 检查是否有 enabled_models 配置
        enabled_models = set(qwen_cfg.get("extra_config", {}).get("enabled_models", []))
        available_models = qwen_cfg.get("available_models", [])
        
        # 如果有 available_models 列表，为每个启用的模型创建实例
        if available_models:
            for model_info in available_models:
                model_id = model_info["id"]
                # 如果没有设置 enabled_models，默认全部启用
                if not enabled_models or model_id in enabled_models:
                    model_cfg = {
                        **qwen_cfg,
                        "model": model_id,
                        "display_name": model_info.get("name", model_id),
                    }
                    client = QwenClient(model_cfg)
                    model_registry.register(client)
        else:
            # 回退：只注册默认模型
            qwen = QwenClient(qwen_cfg)
            model_registry.register(qwen)

    # 智谱 GLM (需要 zhipuai SDK)
    glm_cfg = config.get("glm", {})
    if glm_cfg.get("enabled", False):
        try:
            from .glm import GLMClient
            # 检查是否有 enabled_models 配置
            enabled_models = set(glm_cfg.get("extra_config", {}).get("enabled_models", []))
            available_models = glm_cfg.get("available_models", [])
            
            if available_models:
                for model_info in available_models:
                    model_id = model_info["id"]
                    if not enabled_models or model_id in enabled_models:
                        model_cfg = {
                            **glm_cfg,
                            "model": model_id,
                            "display_name": model_info.get("name", model_id),
                        }
                        client = GLMClient(model_cfg)
                        model_registry.register(client)
            else:
                glm = GLMClient(glm_cfg)
                model_registry.register(glm)
        except ImportError:
            print("⚠️  智谱 GLM 需要安装 SDK: pip install zhipuai")

    # MiniMax (使用 httpx 直接调用)
    minimax_cfg = config.get("minimax", {})
    if minimax_cfg.get("enabled", False):
        try:
            from .minimax import MiniMaxClient
            enabled_models = set(minimax_cfg.get("extra_config", {}).get("enabled_models", []))
            available_models = minimax_cfg.get("available_models", [])
            
            if available_models:
                for model_info in available_models:
                    model_id = model_info["id"]
                    if not enabled_models or model_id in enabled_models:
                        model_cfg = {
                            **minimax_cfg,
                            "model": model_id,
                            "display_name": model_info.get("name", model_id),
                        }
                        client = MiniMaxClient(model_cfg)
                        model_registry.register(client)
            else:
                minimax = MiniMaxClient(minimax_cfg)
                model_registry.register(minimax)
        except ImportError:
            print("⚠️  MiniMax 需要安装 httpx: pip install httpx")

    # 百度文心 (需要 qianfan SDK)
    ernie_cfg = config.get("ernie", {})
    if ernie_cfg.get("enabled", False):
        try:
            from .ernie import ErnieClient
            enabled_models = set(ernie_cfg.get("extra_config", {}).get("enabled_models", []))
            available_models = ernie_cfg.get("available_models", [])
            
            if available_models:
                for model_info in available_models:
                    model_id = model_info["id"]
                    if not enabled_models or model_id in enabled_models:
                        model_cfg = {
                            **ernie_cfg,
                            "model": model_id,
                            "display_name": model_info.get("name", model_id),
                        }
                        client = ErnieClient(model_cfg)
                        model_registry.register(client)
            else:
                ernie = ErnieClient(ernie_cfg)
                model_registry.register(ernie)
        except ImportError:
            print("⚠️  百度文心需要安装 SDK: pip install qianfan")

    # 字节跳动豆包（火山引擎，使用 openai 兼容接口，无需额外 SDK）
    doubao_cfg = config.get("doubao", {})
    if doubao_cfg.get("enabled", False):
        try:
            from .doubao import DoubaoClient
            # 读取 enabled_models 配置
            enabled_models = set(doubao_cfg.get("extra_config", {}).get("enabled_models", []))
            available_models = doubao_cfg.get("available_models", [])
            
            if available_models:
                # 为每个启用的模型创建独立实例
                for model_info in available_models:
                    model_id = model_info["id"]
                    # 如果没有设置 enabled_models，默认全部启用
                    if not enabled_models or model_id in enabled_models:
                        model_cfg = {
                            **doubao_cfg,
                            "model": model_id,
                            "display_name": model_info.get("name", model_id),
                        }
                        client = DoubaoClient(model_cfg)
                        model_registry.register(client)
            else:
                # 回退：只注册默认模型
                doubao = DoubaoClient(doubao_cfg)
                model_registry.register(doubao)
        except Exception as e:
            print(f"⚠️  豆包模型注册失败: {e}")
