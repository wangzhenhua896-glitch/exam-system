"""
MiniMax 客户端
MiniMax Open API
"""

import asyncio
import json
from typing import Dict, Any, Optional
import httpx

from .base import BaseModelClient, ModelResponse, ModelProvider


class MiniMaxClient(BaseModelClient):
    """MiniMax 客户端"""
    
    provider = ModelProvider.MINIMAX
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model_name = config.get("model", "abab6.5-chat")
        self.display_name = config.get("display_name", self.model_name)
        self.api_key = config.get("api_key", "")
        self.group_id = config.get("group_id", "")
        self.base_url = config.get("base_url", "https://api.minimax.chat/v1")
    
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """生成响应"""
        try:
            url = f"{self.base_url}/text/chatcompletion_v2"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2000),
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=60)
                response.raise_for_status()
                data = response.json()

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            return ModelResponse(
                content=content,
                model_name=self.model_name,
                usage=usage,
            )
        except Exception as e:
            return ModelResponse(
                content="",
                model_name=self.model_name,
                error=str(e)
            )

    def get_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "provider": self.provider.value,
            "model_name": self.model_name,
            "display_name": self.display_name,
            "enabled": self.enabled,
        }
