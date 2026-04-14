#!/usr/bin/env python3
"""
测试Swagger文档集成
"""

import requests
import json
import time

def test_swagger_docs():
    """测试Swagger文档页面"""
    print("🧪 测试Swagger文档集成...")
    
    # 等待服务启动
    time.sleep(2)
    
    # 测试API文档页面
    urls = [
        "http://localhost:5001/api/docs/",
        "http://localhost:5001/apispec.json",
        "http://localhost:5001/api/dashboard"
    ]
    
    for url in urls:
        try:
            response = requests.get(url, timeout=5)
            print(f"✅ {url} - 状态码: {response.status_code}")
            
            if "api/docs" in url and response.status_code == 200:
                print("   🎉 Swagger UI 页面可访问！")
            elif "apispec.json" in url and response.status_code == 200:
                print("   📄 OpenAPI 规范文件可访问！")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ {url} - 连接失败: {e}")
    
    print("\n📋 下一步：")
    print("1. 访问 http://localhost:5001/api/docs/ 查看API文档")
    print("2. 测试API接口在线调试功能")
    print("3. 导出OpenAPI规范文件")

if __name__ == "__main__":
    test_swagger_docs()
