"""
智谱 GLM 客户端
智谱 AI Open API
"""

import asyncio
import json
from typing import Dict, Any, Optional
from zhipuai import ZhipuAI

from .base import BaseModelClient, ModelResponse, ModelProvider


class GLMClient(BaseModelClient):
    """智谱 GLM 客户端"""
    
    provider = ModelProvider.GLM
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model_name = config.get("model", "glm-4")
        self.display_name = config.get("display_name", self.model_name)

        # 初始化智谱客户端
        self.client = ZhipuAI(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", "https://open.bigmodel.cn/api/paas/v4"),
        )
    
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """生成响应"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=kwargs.get("temperature", 0.7),
                    max_tokens=kwargs.get("max_tokens", 2000),
                )
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
