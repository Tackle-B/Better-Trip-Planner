"""测试意图识别功能"""

# 测试用例
test_cases = [
    {
        "input": "我想去北京玩3天",
        "expected": "plan_trip",
        "description": "明确的旅行规划请求"
    },
    {
        "input": "帮我规划一下上海5日游",
        "expected": "plan_trip",
        "description": "明确的旅行规划请求"
    },
    {
        "input": "龙门石窟和洛邑古城距离多远？",
        "expected": "general_chat",
        "description": "询问距离，不需要生成计划"
    },
    {
        "input": "北京有什么好吃的？",
        "expected": "general_chat",
        "description": "询问美食信息"
    },
    {
        "input": "故宫门票多少钱？",
        "expected": "general_chat",
        "description": "询问门票价格"
    },
    {
        "input": "现在去三亚天气怎么样？",
        "expected": "general_chat",
        "description": "询问天气信息"
    },
    {
        "input": "把天数改成5天",
        "expected": "modify_plan",
        "description": "修改现有计划（需要上下文中有计划）"
    },
    {
        "input": "换成上海吧",
        "expected": "modify_plan",
        "description": "修改目的地（需要上下文中有计划）"
    },
    {
        "input": "西湖周边有什么景点？",
        "expected": "general_chat",
        "description": "询问景点信息"
    },
    {
        "input": "洛阳有什么值得去的地方？",
        "expected": "general_chat",
        "description": "询问推荐景点"
    }
]

print("=" * 60)
print("意图识别测试用例")
print("=" * 60)

for i, case in enumerate(test_cases, 1):
    print(f"\n{i}. {case['description']}")
    print(f"   输入: {case['input']}")
    print(f"   期望意图: {case['expected']}")
    print(f"   说明: ", end="")

    if case['expected'] == 'plan_trip':
        print("应该生成旅行计划")
    elif case['expected'] == 'modify_plan':
        print("应该修改现有计划")
    else:
        print("应该调用工具或LLM回答，不生成计划")

print("\n" + "=" * 60)
print("测试说明：")
print("- plan_trip: 用户明确要规划旅行，包含目的地和天数")
print("- modify_plan: 用户想修改已有计划（需要对话历史中有计划）")
print("- general_chat: 用户询问信息，不需要生成完整计划")
print("=" * 60)
