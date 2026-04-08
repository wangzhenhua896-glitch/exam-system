"""
百度文心一言 (ERNIE) 客户端
百度千帆 API
"""

import asyncio
import json
from typing import Dict, Any, Optional
import qianfan

from .base import BaseModelClient, ModelResponse, ModelProvider


class ErnieClient(BaseModelClient):
    """百度文心客户端"""
    
    provider = ModelProvider.ERNIE
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model_name = config.get("model", "ernie-4.0")
        
        # 初始化千帆客户端
        self.client = qianfan.ChatCompletion(
            ak=config.get("api_key", ""),
            sk=config.get("secret_key", ""),
        )
    
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """生成响应"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.do(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=kwargs.get("temperature", 0.7),
                    max_output_tokens=kwargs.get("max_tokens", 2000),
                )
            )

            content = response["result"]
            usage = response.get("usage", {})

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
