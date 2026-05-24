"""支持多轮对话的旅行规划 Agent"""

import json
import asyncio
from typing import AsyncIterator, Optional, List
from ..agents.trip_planner_agent import MultiAgentTripPlanner, get_trip_planner_agent
from ..services.memory_service import MemoryService
from ..services.profile_service import ProfileService
from ..models.schemas import ChatMessage, TripRequest
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


CHAT_SYSTEM_PROMPT = """你是一个专业的旅行规划助手，擅长根据用户需求制定个性化的旅行计划。

你的能力：
1. 理解用户的旅行需求（目的地、时间、预算、偏好等）
2. 调用多智能体系统生成详细的旅行计划
3. 根据用户反馈调整和优化计划
4. 记住用户的偏好，提供个性化建议

交互原则：
- 如果用户需求不明确，主动询问关键信息（城市、日期、天数、预算、偏好）
- 生成计划后，询问用户是否满意，是否需要调整
- 记住用户在对话中提到的偏好，用于后续推荐
- 保持友好、专业的语气

当用户提供完整信息后，你需要：
1. 提取关键信息（城市、开始日期、结束日期、天数、交通方式、住宿偏好、兴趣偏好）
2. 调用旅行规划系统生成计划
3. 以友好的方式呈现计划，并询问是否需要调整
"""


class ChatTripPlannerAgent:
    """支持多轮对话的旅行规划 Agent"""

    def __init__(
        self,
        memory_service: MemoryService,
        profile_service: ProfileService
    ):
        self.memory = memory_service
        self.profile_service = profile_service
        self.planner = get_trip_planner_agent()
        logger.info("ChatTripPlannerAgent initialized")

    async def chat(
        self,
        conv_id: str,
        user_id: str,
        user_input: str
    ) -> AsyncIterator[str]:
        """流式多轮对话

        Args:
            conv_id: 会话ID
            user_id: 用户ID
            user_input: 用户输入

        Yields:
            流式响应文本
        """
        try:
            # 1. 构建上下文（历史对话 + 用户画像）
            # 这里的上下文构建略显简陋，可以用helloagents框架中的GSSC流水线
            context = await self.memory.build_context_for_agent(
                conv_id=conv_id,
                user_id=user_id,
                current_query=user_input,
                window_size=10
            )

            # 2. 判断用户意图
            intent = await self._analyze_intent(user_input, context)
            logger.info(f"User intent detected: {intent} for input: {user_input[:50]}...")

            # 3. 根据意图处理
            if intent == "plan_trip":
                # 生成旅行计划
                async for chunk in self._handle_trip_planning(user_input, context, conv_id, user_id):
                    yield chunk
            elif intent == "modify_plan":
                # 修改现有计划
                async for chunk in self._handle_plan_modification(user_input, context):
                    yield chunk
            else:
                # 普通对话
                async for chunk in self._handle_general_chat(user_input, context):
                    yield chunk

        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
            yield f"很抱歉，我遇到了一些技术问题。\n\n"
            yield f"错误详情：{str(e)}\n\n"
            yield "您可以尝试：\n"
            yield "1. 换一种方式提问\n"
            yield "2. 如果想规划旅行，请告诉我目的地和天数\n"
            yield "3. 如果问题持续，请联系技术支持"

    async def _analyze_intent(
        self,
        user_input: str,
        context: str
    ) -> str:
        """分析用户意图

        Returns:
            "plan_trip" | "modify_plan" | "general_chat"
        """
        # 使用LLM进行更准确的意图识别
        intent_prompt = [
            {
                "role": "system",
                "content": """你是一个意图识别助手。分析用户的输入，判断用户的意图类型。

意图类型定义：
1. plan_trip（生成旅行计划）：用户明确表达想要规划一次旅行，通常包含目的地、天数等信息
   - 例如："我想去北京玩3天"、"帮我规划一下上海5日游"、"计划下个月去成都旅游"

2. modify_plan（修改现有计划）：用户想要调整已经生成的旅行计划
   - 前提：对话历史中已经有旅行计划
   - 例如："把天数改成5天"、"换成上海吧"、"预算太高了，调整一下"

3. general_chat（普通问答）：用户在询问信息、咨询问题，但不需要生成完整的旅行计划
   - 例如："龙门石窟和洛邑古城距离多远？"、"北京有什么好吃的？"、"现在去三亚天气怎么样？"
   - 例如："故宫门票多少钱？"、"西湖周边有什么景点？"

判断原则：
- 只有用户明确表达要"规划行程"、"安排旅行"、"制定计划"，且提供了天数信息时，才判定为plan_trip
- 如果只是询问信息、咨询问题，即使提到景点名称，也应该判定为general_chat
- 如果对话中已有计划，且用户表达修改意图，才判定为modify_plan"""
            },
            {
                "role": "user",
                "content": f"""对话历史：
{context}

用户当前输入：
{user_input}

请判断用户意图，只返回以下三个选项之一：
- plan_trip
- modify_plan
- general_chat

只返回意图类型，不要其他内容。"""
            }
        ]

        try:
            response = self.planner.llm.invoke(intent_prompt)
            intent = response.strip().lower()

            # 清理响应
            if "plan_trip" in intent:
                intent = "plan_trip"
            elif "modify_plan" in intent:
                intent = "modify_plan"
            else:
                intent = "general_chat"

            logger.info(f"LLM detected intent: {intent} for input: {user_input[:50]}...")
            return intent

        except Exception as e:
            logger.error(f"Intent analysis error: {e}", exc_info=True)
            # 降级到关键词匹配
            return self._fallback_intent_analysis(user_input, context)

    def _fallback_intent_analysis(self, user_input: str, context: str) -> str:
        """降级的意图识别（基于关键词）"""
        user_input_lower = user_input.lower()

        # 检查是否是明确的规划请求（必须同时包含规划意图+天数）
        plan_keywords = ["规划", "安排", "计划旅行", "制定行程", "帮我安排"]
        has_plan_keyword = any(kw in user_input_lower for kw in plan_keywords)
        has_days = any(word in user_input for word in ["天", "日游", "周", "星期"])

        if has_plan_keyword and has_days:
            return "plan_trip"

        # 检查是否是修改请求
        modify_keywords = ["修改", "调整", "换成", "改成", "重新规划"]
        has_existing_plan = "TRIP_PLAN_CARD" in context or "已为您生成" in context
        has_modify_keyword = any(kw in user_input_lower for kw in modify_keywords)

        if has_existing_plan and has_modify_keyword:
            return "modify_plan"

        # 默认为普通对话
        return "general_chat"

    async def _handle_trip_planning(
        self,
        user_input: str,
        context: str,
        conv_id: str = None,
        user_id: str = "default_user"
    ) -> AsyncIterator[str]:
        """处理旅行规划请求"""
        try:
            # 1. 从用户输入中提取旅行参数
            trip_params = await self._extract_trip_params(user_input, context)

            if not trip_params:
                yield "我需要更多信息来为您规划行程。请告诉我：\n"
                yield "1. 您想去哪个城市？\n"
                yield "2. 计划什么时候出发？\n"
                yield "3. 打算玩几天？\n"
                yield "4. 有什么特别的偏好吗（如美食、历史、自然等）？"
                return

            # 2. 检查必要参数
            if not all([trip_params.get("city"), trip_params.get("travel_days")]):
                missing = []
                if not trip_params.get("city"):
                    missing.append("目的地城市")
                if not trip_params.get("travel_days"):
                    missing.append("旅行天数")

                yield f"还需要您提供：{', '.join(missing)}"
                return

            # 3. 构建 TripRequest
            trip_request = self._build_trip_request(trip_params)

            # 4. 调用旅行规划系统
            yield f"好的，我正在为您规划{trip_request.city}{trip_request.travel_days}日游...\n\n"

            # 同步调用（因为 plan_trip 是同步方法）
            loop = asyncio.get_event_loop()
            trip_plan = await loop.run_in_executor(
                None,
                self.planner.plan_trip,
                trip_request
            )

            # 5. 保存计划到持久化存储
            from ..services.plan_service import get_plan_service
            plan_service = get_plan_service()

            # 生成计划标题
            title = f"{trip_plan.city}{trip_request.travel_days}日游"

            saved_plan = await plan_service.save_plan(
                user_id=user_id,
                conversation_id=conv_id,
                title=title,
                plan=trip_plan
            )

            # 6. 返回卡片标记（JSON格式）
            from ..models.schemas import TripPlanCardMessage

            # 提取亮点
            highlights = []
            if trip_plan.days and len(trip_plan.days) > 0:
                # 取前3个景点作为亮点
                for day in trip_plan.days[:min(2, len(trip_plan.days))]:
                    if day.attractions:
                        for attr in day.attractions[:2]:
                            highlights.append(attr.name)
                            if len(highlights) >= 3:
                                break
                    if len(highlights) >= 3:
                        break

            card = TripPlanCardMessage(
                plan_id=saved_plan.plan_id,
                title=title,
                city=trip_plan.city,
                start_date=trip_plan.start_date,
                end_date=trip_plan.end_date,
                days_count=trip_request.travel_days,
                highlights=highlights
            )

            # 返回特殊标记，前端据此渲染卡片
            yield f"\n\n[TRIP_PLAN_CARD]{card.model_dump_json()}[/TRIP_PLAN_CARD]\n\n"
            yield f"✅ 已为您生成{title}计划，点击上方卡片查看详情。"

        except Exception as e:
            logger.error(f"Trip planning error: {e}")
            yield f"\n抱歉，生成旅行计划时出现了问题：{str(e)}"

    async def _handle_plan_modification(
        self,
        user_input: str,
        context: str
    ) -> AsyncIterator[str]:
        """处理计划修改请求"""
        try:
            # 1. 从上下文中提取原有计划的参数
            original_params = await self._extract_trip_params_from_context(context)

            if not original_params:
                yield "我没有找到之前的旅行计划。请告诉我您想去哪里、玩几天，我会为您重新规划。"
                return

            # 2. 从用户输入中提取修改意图
            modification_prompt = [
                {
                    "role": "system",
                    "content": "你是一个信息提取助手。分析用户想要修改旅行计划的哪些方面，以JSON格式返回。"
                },
                {
                    "role": "user",
                    "content": f"""原计划参数：
{json.dumps(original_params, ensure_ascii=False, indent=2)}

用户修改请求：
{user_input}

请分析用户想修改什么，返回JSON格式：
{{
    "city": "如果要换城市，填新城市名；否则null",
    "travel_days": "如果要改天数，填新天数；否则null",
    "start_date": "如果要改日期，填新日期(YYYY-MM-DD)；否则null",
    "budget_per_day": "如果要调整预算，填新预算；否则null",
    "interests": ["如果要改兴趣偏好，填新偏好列表；否则null"],
    "accommodation_preference": "如果要改住宿偏好，填新偏好；否则null",
    "transportation_mode": "如果要改交通方式，填新方式；否则null",
    "modification_summary": "用一句话总结用户想修改什么"
}}

只返回JSON，不要其他内容。"""
                }
            ]

            # 调用LLM提取修改意图
            response = self.planner.llm.invoke(modification_prompt)

            # 解析JSON
            try:
                # 清理响应，提取JSON部分
                json_str = response.strip()
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()

                modifications = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse modification JSON: {e}, response: {response}")
                yield "我理解您想调整计划。请更具体地告诉我：\n"
                yield "- 想去哪个城市？\n"
                yield "- 玩几天？\n"
                yield "- 预算是多少？\n"
                yield "- 有什么特别的偏好？\n\n"
                yield "我会根据您的新需求重新生成计划。"
                return

            # 3. 合并原参数和修改
            updated_params = original_params.copy()
            for key, value in modifications.items():
                if key == "modification_summary":
                    continue
                if value is not None and value != "null":
                    updated_params[key] = value

            # 4. 确认修改并重新生成计划
            summary = modifications.get("modification_summary", "调整计划")
            yield f"好的，我明白了：{summary}\n\n"
            yield "正在为您重新生成计划...\n\n"

            # 5. 调用旅行规划逻辑
            async for chunk in self._handle_trip_planning(
                user_input=json.dumps(updated_params, ensure_ascii=False),
                context=context,
                conv_id=None,
                user_id="default_user"
            ):
                yield chunk

        except Exception as e:
            logger.error(f"Plan modification error: {e}", exc_info=True)
            yield "抱歉，处理您的修改请求时出现了问题。\n\n"
            yield "请直接告诉我您的新需求（目的地、天数、预算等），我会为您重新规划。"

    async def _handle_general_chat(
        self,
        user_input: str,
        context: str
    ) -> AsyncIterator[str]:
        """处理普通对话，支持调用工具"""
        try:
            # 1. 判断是否需要调用工具
            tool_decision = await self._decide_tool_usage(user_input)

            if tool_decision.get("need_tool", False):
                # 需要调用工具
                tool_type = tool_decision.get("tool_type")

                if tool_type == "distance":
                    # 查询两地距离
                    async for chunk in self._handle_distance_query(user_input, tool_decision):
                        yield chunk
                elif tool_type == "poi_search":
                    # 搜索景点信息
                    async for chunk in self._handle_poi_search(user_input, tool_decision):
                        yield chunk
                elif tool_type == "weather":
                    # 查询天气
                    async for chunk in self._handle_weather_query(user_input, tool_decision):
                        yield chunk
                else:
                    # 其他工具调用，使用通用处理
                    async for chunk in self._handle_tool_call(user_input, tool_decision):
                        yield chunk
            else:
                # 不需要工具，直接用LLM回答
                async for chunk in self._handle_llm_chat(user_input, context):
                    yield chunk

        except Exception as e:
            logger.error(f"General chat error: {e}", exc_info=True)
            yield f"抱歉，我在处理您的问题时遇到了一些困难。\n\n请尝试换一种方式提问，或者告诉我您想规划一次旅行。"

    async def _decide_tool_usage(self, user_input: str) -> dict:
        """判断是否需要调用工具以及调用什么工具"""
        decision_prompt = [
            {
                "role": "system",
                "content": """你是一个工具调用决策助手。分析用户问题，判断是否需要调用工具。

可用工具类型：
1. distance - 查询两个地点之间的距离
2. poi_search - 搜索景点、餐厅、酒店等POI信息
3. weather - 查询天气信息
4. none - 不需要工具，直接回答即可

判断原则：
- 如果用户询问"距离"、"多远"、"多少公里"等，使用distance工具
- 如果用户询问"有什么景点"、"推荐餐厅"、"附近的酒店"等，使用poi_search工具
- 如果用户询问"天气"、"气温"、"下雨"等，使用weather工具
- 如果是一般性问题（如"北京有什么特色"），不需要工具"""
            },
            {
                "role": "user",
                "content": f"""用户问题：{user_input}

请判断是否需要工具，返回JSON格式：
{{
    "need_tool": true/false,
    "tool_type": "distance/poi_search/weather/none",
    "reason": "为什么需要/不需要工具",
    "extracted_params": {{
        // 如果是distance: {{"origin": "起点", "destination": "终点"}}
        // 如果是poi_search: {{"keyword": "搜索关键词", "city": "城市"}}
        // 如果是weather: {{"city": "城市"}}
    }}
}}

只返回JSON，不要其他内容。"""
            }
        ]

        try:
            response = self.planner.llm.invoke(decision_prompt)

            # 解析JSON
            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            decision = json.loads(json_str)
            logger.info(f"Tool decision: {decision}")
            return decision

        except Exception as e:
            logger.error(f"Tool decision error: {e}", exc_info=True)
            return {"need_tool": False, "tool_type": "none"}

    async def _handle_distance_query(self, user_input: str, tool_decision: dict) -> AsyncIterator[str]:
        """处理距离查询"""
        try:
            params = tool_decision.get("extracted_params", {})
            origin = params.get("origin")
            destination = params.get("destination")

            if not origin or not destination:
                yield f"请告诉我您想查询哪两个地点之间的距离。"
                return

            yield f"正在查询{origin}到{destination}的距离...\n\n"

            # 使用高德地图工具查询距离
            # 构建工具调用格式
            query = f"请使用amap_maps_direction工具查询从{origin}到{destination}的距离和路线。\n[TOOL_CALL:amap_maps_direction:origin={origin},destination={destination}]"

            # 调用景点搜索Agent（它有高德地图工具）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.planner.attraction_agent.run,
                query
            )

            # 模拟流式输出
            chunk_size = 30
            for i in range(0, len(result), chunk_size):
                chunk = result[i:i + chunk_size]
                yield chunk
                await asyncio.sleep(0.05)

        except Exception as e:
            logger.error(f"Distance query error: {e}", exc_info=True)
            yield f"抱歉，查询距离时出现问题。您可以使用地图软件查询{origin}到{destination}的距离。"

    async def _handle_poi_search(self, user_input: str, tool_decision: dict) -> AsyncIterator[str]:
        """处理POI搜索"""
        try:
            params = tool_decision.get("extracted_params", {})
            keyword = params.get("keyword")
            city = params.get("city", "")

            if not keyword:
                yield "请告诉我您想搜索什么。"
                return

            yield f"正在搜索{city}{keyword}...\n\n"

            # 构建工具调用格式
            query = f"请使用amap_maps_text_search工具搜索{city}的{keyword}。\n[TOOL_CALL:amap_maps_text_search:keywords={keyword},city={city}]"

            # 调用景点搜索Agent（使用正确的.run()方法）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.planner.attraction_agent.run,
                query
            )

            # 模拟流式输出
            chunk_size = 30
            for i in range(0, len(result), chunk_size):
                chunk = result[i:i + chunk_size]
                yield chunk
                await asyncio.sleep(0.05)

        except Exception as e:
            logger.error(f"POI search error: {e}", exc_info=True)
            yield f"抱歉，搜索时出现问题。"

    async def _handle_weather_query(self, user_input: str, tool_decision: dict) -> AsyncIterator[str]:
        """处理天气查询"""
        try:
            params = tool_decision.get("extracted_params", {})
            city = params.get("city")

            if not city:
                yield "请告诉我您想查询哪个城市的天气。"
                return

            yield f"正在查询{city}的天气...\n\n"

            # 构建查询请求（天气agent可能需要特定格式）
            query = f"查询{city}的天气情况"

            # 调用天气查询Agent（使用正确的.run()方法）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.planner.weather_agent.run,
                query
            )

            # 模拟流式输出
            chunk_size = 30
            for i in range(0, len(result), chunk_size):
                chunk = result[i:i + chunk_size]
                yield chunk
                await asyncio.sleep(0.05)

        except Exception as e:
            logger.error(f"Weather query error: {e}", exc_info=True)
            yield f"抱歉，查询天气时出现问题。"

    async def _handle_tool_call(self, user_input: str, tool_decision: dict) -> AsyncIterator[str]:
        """通用工具调用处理"""
        yield "正在为您查询信息...\n\n"
        yield "抱歉，该功能正在开发中。"

    async def _handle_llm_chat(self, user_input: str, context: str) -> AsyncIterator[str]:
        """使用LLM直接回答"""
        messages = [
            {
                "role": "system",
                "content": CHAT_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": f"""{context}

用户当前输入: {user_input}

请给出友好、专业的回复。如果用户询问某地的美食、景点、天气等信息，你可以提供一般性的建议和介绍。"""
            }
        ]

        try:
            # 同步调用 LLM
            response = self.planner.llm.invoke(messages)

            # 模拟流式输出
            chunk_size = 20
            for i in range(0, len(response), chunk_size):
                chunk = response[i:i + chunk_size]
                yield chunk
                await asyncio.sleep(0.05)

        except Exception as e:
            logger.error(f"LLM chat error: {e}", exc_info=True)
            yield f"抱歉，我在处理您的问题时遇到了一些困难。请尝试换一种方式提问。"

    async def _extract_trip_params(
        self,
        user_input: str,
        context: str
    ) -> Optional[dict]:
        """从用户输入中提取旅行参数"""
        # 使用 LLM 提取结构化信息
        extraction_prompt = [
            {
                "role": "system",
                "content": "你是一个信息提取助手。从用户对话中提取旅行规划的关键信息，以JSON格式返回。"
            },
            {
                "role": "user",
                "content": f"""从以下对话中提取旅行规划的关键信息。

上下文：
{context}

用户输入：
{user_input}

请以 JSON 格式返回提取的信息（如果某项信息未提及，则不包含该字段）：
{{
  "city": "目的地城市",
  "start_date": "YYYY-MM-DD",
  "travel_days": 天数（整数）,
  "transportation": "交通方式",
  "accommodation": "住宿偏好",
  "preferences": ["偏好1", "偏好2"],
  "free_text_input": "其他要求"
}}

只返回JSON，不要有其他文字。"""
            }
        ]

        try:
            # 调用 LLM（不使用 response_format，因为可能不支持）
            response = self.planner.llm.invoke(extraction_prompt)

            # 提取 JSON
            response = response.strip()

            # 尝试多种方式提取 JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            # 如果响应中包含其他文字，尝试找到 JSON 部分
            if not response.startswith("{"):
                # 查找第一个 { 和最后一个 }
                start = response.find("{")
                end = response.rfind("}")
                if start != -1 and end != -1:
                    response = response[start:end+1]

            params = json.loads(response)
            logger.info(f"Extracted trip params: {params}")
            return params

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}")
            logger.error(f"LLM response was: {response[:200]}")
            return None
        except Exception as e:
            logger.error(f"Failed to extract trip params: {e}", exc_info=True)
            return None

    async def _extract_trip_params_from_context(self, context: str) -> Optional[dict]:
        """从对话上下文中提取原有的旅行计划参数"""
        extraction_prompt = [
            {
                "role": "system",
                "content": "你是一个信息提取助手。从对话历史中提取之前生成的旅行计划的参数。"
            },
            {
                "role": "user",
                "content": f"""从以下对话历史中提取之前的旅行计划参数：

{context}

请以JSON格式返回提取的信息：
{{
  "city": "目的地城市",
  "start_date": "YYYY-MM-DD",
  "travel_days": 天数（整数）,
  "transportation": "交通方式",
  "accommodation": "住宿偏好",
  "preferences": ["偏好1", "偏好2"],
  "budget_per_day": 每日预算（整数，如果有的话）
}}

如果对话中没有提到旅行计划，返回 null。
只返回JSON，不要其他内容。"""
            }
        ]

        try:
            response = self.planner.llm.invoke(extraction_prompt)
            response = response.strip()

            # 检查是否返回null
            if response.lower() == "null" or "没有" in response or "未找到" in response:
                return None

            # 提取JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            if not response.startswith("{"):
                start = response.find("{")
                end = response.rfind("}")
                if start != -1 and end != -1:
                    response = response[start:end+1]

            params = json.loads(response)
            logger.info(f"Extracted original trip params from context: {params}")
            return params

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse context params JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to extract params from context: {e}", exc_info=True)
            return None

    def _build_trip_request(self, params: dict) -> TripRequest:
        """构建 TripRequest 对象"""
        # 处理日期
        start_date = params.get("start_date")
        if not start_date:
            # 默认明天出发
            start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        travel_days = params.get("travel_days", 3)
        end_date = params.get("end_date")
        if not end_date:
            end_date = (
                datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=travel_days - 1)
            ).strftime("%Y-%m-%d")

        return TripRequest(
            city=params.get("city", "北京"),
            start_date=start_date,
            end_date=end_date,
            travel_days=travel_days,
            transportation=params.get("transportation", "公共交通"),
            accommodation=params.get("accommodation", "经济型酒店"),
            preferences=params.get("preferences", []),
            free_text_input=params.get("free_text_input", "")
        )

    def _format_trip_plan(self, trip_plan) -> str:
        """格式化旅行计划为文本"""
        output = []

        output.append(f"# {trip_plan.city}旅行计划\n")
        output.append(f"📅 日期：{trip_plan.start_date} 至 {trip_plan.end_date}\n")

        # 天气信息
        if trip_plan.weather_info:
            output.append("\n## 🌤️ 天气预报\n")
            for weather in trip_plan.weather_info:
                output.append(
                    f"- {weather.date}: {weather.day_weather}，"
                    f"{weather.day_temp}°C ~ {weather.night_temp}°C\n"
                )

        # 每日行程
        output.append("\n## 📍 详细行程\n")
        for day in trip_plan.days:
            output.append(f"\n### 第{day.day_index + 1}天 ({day.date})\n")
            output.append(f"{day.description}\n\n")

            # 景点
            if day.attractions:
                output.append("**景点：**\n")
                for attr in day.attractions:
                    output.append(f"- {attr.name}（{attr.visit_duration}分钟）\n")
                    output.append(f"  {attr.description}\n")
                output.append("\n")

            # 餐饮
            if day.meals:
                output.append("**餐饮：**\n")
                for meal in day.meals:
                    meal_type_map = {
                        "breakfast": "早餐",
                        "lunch": "午餐",
                        "dinner": "晚餐"
                    }
                    output.append(
                        f"- {meal_type_map.get(meal.type, meal.type)}: {meal.name}\n"
                    )
                output.append("\n")

            # 住宿
            if day.hotel:
                output.append(f"**住宿：** {day.hotel.name}\n\n")

        # 预算
        if hasattr(trip_plan, 'budget') and trip_plan.budget:
            output.append("\n## 💰 预算估算\n")
            budget = trip_plan.budget
            output.append(f"- 景点门票：¥{budget.total_attractions}\n")
            output.append(f"- 住宿费用：¥{budget.total_hotels}\n")
            output.append(f"- 餐饮费用：¥{budget.total_meals}\n")
            output.append(f"- 交通费用：¥{budget.total_transportation}\n")
            output.append(f"**总计：¥{budget.total}**\n")

        # 建议
        if trip_plan.overall_suggestions:
            output.append(f"\n## 💡 旅行建议\n{trip_plan.overall_suggestions}\n")

        output.append("\n---\n如果您对计划有任何疑问或想调整，请随时告诉我！")

        return "".join(output)


# 全局单例
_chat_agent: Optional[ChatTripPlannerAgent] = None


def get_chat_agent(
    memory_service: MemoryService,
    profile_service: ProfileService
) -> ChatTripPlannerAgent:
    """获取聊天 Agent 单例"""
    global _chat_agent
    if _chat_agent is None:
        _chat_agent = ChatTripPlannerAgent(memory_service, profile_service)
    return _chat_agent
