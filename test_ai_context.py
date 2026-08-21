# -*- coding: utf-8 -*-
"""测试 AI 上下文记忆功能"""
import json
import requests
import time

BASE_URL = "http://127.0.0.1:8010"

def test_conversation():
    """测试多轮对话上下文"""
    print("=" * 60)
    print("测试 1: 多轮对话上下文")
    print("=" * 60)
    
    # 第一轮：推荐电影
    print("\n[用户] 推荐一部类似《花样年华》的电影")
    r1 = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "推荐一部类似《花样年华》的电影",
        "device_id": "test_device_001",
        "mode": "rec",
        "spoiler": True
    })
    reply1 = r1.json()
    print(f"[AI] {reply1['text'][:100]}...")
    conv_id = reply1.get("conversation_id")
    print(f"  → conversation_id: {conv_id}")
    
    time.sleep(1)
    
    # 第二轮：追问（应该理解上下文）
    print("\n[用户] 为什么？")
    r2 = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "为什么？",
        "device_id": "test_device_001",
        "mode": "rec",
        "spoiler": True,
        "conversation_id": conv_id
    })
    reply2 = r2.json()
    print(f"[AI] {reply2['text'][:100]}...")
    
    # 检查是否理解了上下文
    if "花样年华" in reply2['text'] or "重庆森林" in reply2['text']:
        print("  ✓ AI 理解了上下文（提到了相关电影）")
    else:
        print("  ✗ AI 可能没有理解上下文")
    
    return conv_id

def test_movie_context():
    """测试电影上下文（从详情页进入 AI 陪看）"""
    print("\n" + "=" * 60)
    print("测试 2: 电影上下文（AI 陪看）")
    print("=" * 60)
    
    # 先获取一部电影的 ID
    movies_r = requests.get(f"{BASE_URL}/api/movies?limit=1")
    movies = movies_r.json()
    if not movies.get("items"):
        print("  ✗ 无法获取电影列表")
        return
    
    movie_id = movies["items"][0]["movie_id"]
    movie_title = movies["items"][0]["title"]
    print(f"\n当前电影: 《{movie_title}》 (ID: {movie_id})")
    
    # 从详情页进入 AI 陪看，带 movie_id
    print("\n[用户] 这个结局是不是很遗憾？")
    r = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "这个结局是不是很遗憾？",
        "device_id": "test_device_002",
        "mode": "talk",
        "spoiler": False,
        "movie_id": movie_id
    })
    reply = r.json()
    print(f"[AI] {reply['text'][:100]}...")
    
    # 检查是否知道当前电影
    if movie_title in reply['text'] or "结局" in reply['text']:
        print(f"  ✓ AI 知道在讨论《{movie_title}》")
    else:
        print(f"  ✗ AI 可能不知道当前电影")

def test_new_conversation():
    """测试清空聊天创建新会话"""
    print("\n" + "=" * 60)
    print("测试 3: 清空聊天创建新会话")
    print("=" * 60)
    
    # 第一次对话
    print("\n[对话 1] 推荐科幻片")
    r1 = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "推荐科幻片",
        "device_id": "test_device_003",
        "mode": "rec"
    })
    conv_id_1 = r1.json().get("conversation_id")
    print(f"  conversation_id: {conv_id_1}")
    
    time.sleep(1)
    
    # 清空后第二次对话（不传 conversation_id，自动创建新会话）
    print("\n[对话 2 - 新会话] 推荐爱情片")
    r2 = requests.post(f"{BASE_URL}/api/chat", json={
        "message": "推荐爱情片",
        "device_id": "test_device_003",
        "mode": "rec"
    })
    conv_id_2 = r2.json().get("conversation_id")
    print(f"  conversation_id: {conv_id_2}")
    
    if conv_id_1 != conv_id_2:
        print("  ✓ 成功创建新会话")
    else:
        print("  ✗ 未创建新会话")

if __name__ == "__main__":
    print("\n影灵 CINE · AI 上下文记忆功能测试")
    print("=" * 60)
    
    try:
        # 检查服务是否运行
        requests.get(f"{BASE_URL}/api/movies?limit=1", timeout=2)
    except:
        print("\n✗ 后端服务未启动，请先运行：")
        print("  $env:HF_ENDPOINT = 'https://hf-mirror.com'")
        print("  python -m uvicorn cine.main:app --port 8010")
        exit(1)
    
    try:
        test_conversation()
        test_movie_context()
        test_new_conversation()
        
        print("\n" + "=" * 60)
        print("测试完成！")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
