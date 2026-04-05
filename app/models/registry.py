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
    if config.get("qwen", {}).get("enabled", False):
        qwen = QwenClient(config["qwen"])
        model_registry.register(qwen)
    
    # 智谱 GLM (需要 zhipuai SDK)
    if config.get("glm", {}).get("enabled", False):
        try:
            from .glm import GLMClient
            glm = GLMClient(config["glm"])
            model_registry.register(glm)
        except ImportError:
            print("⚠️  智谱 GLM 需要安装 SDK: pip install zhipuai")
    
    # MiniMax (使用 httpx 直接调用)
    if config.get("minimax", {}).get("enabled", False):
        try:
            from .minimax import MiniMaxClient
            minimax = MiniMaxClient(config["minimax"])
            model_registry.register(minimax)
        except ImportError:
            print("⚠️  MiniMax 需要安装 httpx: pip install httpx")
    
    # 百度文心 (需要 qianfan SDK)
    if config.get("ernie", {}).get("enabled", False):
        try:
            from .ernie import ErnieClient
            ernie = ErnieClient(config["ernie"])
            model_registry.register(ernie)
        except ImportError:
            print("⚠️  百度文心需要安装 SDK: pip install qianfan")
