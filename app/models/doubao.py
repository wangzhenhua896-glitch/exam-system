"""
字节跳动豆包 (Doubao) 客户端
火山引擎 Coding Plan API
"""

import asyncio
import json
from typing import Dict, Any, Optional
from openai import AsyncOpenAI

from .base import BaseModelClient, ModelResponse, ModelProvider


class DoubaoClient(BaseModelClient):
    """字节跳动豆包客户端（火山引擎）"""

    provider = ModelProvider.DOUBAO

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # 在火山引擎 Coding Plan 中，model 就是你的端点ID (endpoint ID)
        # 格式类似：ep-xxxxxxxxxxxxxxxxxxxx 或带版本号的 model-id
        self.model_name = config.get("model", "")
        self.display_name = config.get("display_name", self.model_name)

        # 初始化 OpenAI 兼容客户端
        # 火山引擎 Coding Plan 专用 endpoint
        # 注意：这和通用推理接口不同，使用这个才会走 Coding Plan 额度
        api_key = config.get("api_key", "")
        base_url = config.get("base_url", "https://ark.cn-beijing.volces.com/api/coding/v3")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """生成响应"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 2000),
            )

            content = response.choices[0].message.content

            return ModelResponse(
                content=content,
                model_name=self.model_name,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }
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
