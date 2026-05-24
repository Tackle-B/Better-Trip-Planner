"""测试脚本 - 验证改造后的功能"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def test_basic_imports():
    """测试基础导入"""
    print("=" * 60)
    print("Test 1: Basic Module Imports")
    print("=" * 60)

    try:
        from app.models.schemas import Conversation, ChatMessage, UserProfile
        print("[OK] Data models imported successfully")

        # 测试创建实例
        conv = Conversation(title="Test Conversation")
        print(f"[OK] Created conversation instance: {conv.id}")

        msg = ChatMessage(conversation_id=conv.id, role="user", content="Test message")
        print(f"[OK] Created message instance: {msg.id}")

        profile = UserProfile(user_id="test_user", preferences={"budget": "medium"})
        print(f"[OK] Created user profile instance: {profile.user_id}")

        return True
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        return False

async def test_services_without_redis():
    """测试服务层（不依赖 Redis）"""
    print("\n" + "=" * 60)
    print("Test 2: Service Layer Structure")
    print("=" * 60)

    try:
        # 测试导入（不实例化）
        from app.services import memory_service, conversation_service, profile_service
        print("[OK] Service modules imported successfully")

        from app.agents import chat_agent
        print("[OK] Chat Agent module imported successfully")

        from app.api.routes import conversation
        print("[OK] API route module imported successfully")

        return True
    except Exception as e:
        print(f"[FAIL] Service layer test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_api_structure():
    """测试 API 结构"""
    print("\n" + "=" * 60)
    print("Test 3: API Structure")
    print("=" * 60)

    try:
        from app.api.main import app
        print("[OK] FastAPI application imported successfully")

        # 检查路由
        routes = [route.path for route in app.routes]
        print(f"[OK] Registered routes: {len(routes)}")

        conversation_routes = [r for r in routes if '/conversations' in r]
        print(f"[OK] Conversation routes: {len(conversation_routes)}")
        for route in conversation_routes:
            print(f"   - {route}")

        return True
    except Exception as e:
        print(f"[FAIL] API structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    print("\nStarting refactor tests...\n")

    results = []

    # 测试 1: 基础导入
    results.append(await test_basic_imports())

    # 测试 2: 服务层
    results.append(await test_services_without_redis())

    # 测试 3: API 结构
    results.append(await test_api_structure())

    # 总结
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n[OK] All tests passed! Project refactor successful.")
        print("\nNOTE:")
        print("1. Install new dependencies: pip install redis chromadb")
        print("2. Redis service is running on port 6379")
        print("3. Chroma will auto-create local database")
    else:
        print("\n[FAIL] Some tests failed. Please check error messages.")

    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
