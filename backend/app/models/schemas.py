"""数据模型定义"""

from typing import List, Optional, Union, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
import uuid


# ============ 请求模型 ============

class TripRequest(BaseModel):
    """旅行规划请求"""
    city: str = Field(..., description="目的地城市", example="北京")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD", example="2025-06-01")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD", example="2025-06-03")
    travel_days: int = Field(..., description="旅行天数", ge=1, le=30, example=3)
    transportation: str = Field(..., description="交通方式", example="公共交通")
    accommodation: str = Field(..., description="住宿偏好", example="经济型酒店")
    preferences: List[str] = Field(default=[], description="旅行偏好标签", example=["历史文化", "美食"])
    free_text_input: Optional[str] = Field(default="", description="额外要求", example="希望多安排一些博物馆")
    
    class Config:
        json_schema_extra = {
            "example": {
                "city": "北京",
                "start_date": "2025-06-01",
                "end_date": "2025-06-03",
                "travel_days": 3,
                "transportation": "公共交通",
                "accommodation": "经济型酒店",
                "preferences": ["历史文化", "美食"],
                "free_text_input": "希望多安排一些博物馆"
            }
        }


class POISearchRequest(BaseModel):
    """POI搜索请求"""
    keywords: str = Field(..., description="搜索关键词", example="故宫")
    city: str = Field(..., description="城市", example="北京")
    citylimit: bool = Field(default=True, description="是否限制在城市范围内")


class RouteRequest(BaseModel):
    """路线规划请求"""
    origin_address: str = Field(..., description="起点地址", example="北京市朝阳区阜通东大街6号")
    destination_address: str = Field(..., description="终点地址", example="北京市海淀区上地十街10号")
    origin_city: Optional[str] = Field(default=None, description="起点城市")
    destination_city: Optional[str] = Field(default=None, description="终点城市")
    route_type: str = Field(default="walking", description="路线类型: walking/driving/transit")


# ============ 响应模型 ============

class Location(BaseModel):
    """地理位置"""
    longitude: float = Field(..., description="经度")
    latitude: float = Field(..., description="纬度")


class Attraction(BaseModel):
    """景点信息"""
    name: str = Field(..., description="景点名称")
    address: str = Field(..., description="地址")
    location: Location = Field(..., description="经纬度坐标")
    visit_duration: int = Field(..., description="建议游览时间(分钟)")
    description: str = Field(..., description="景点描述")
    category: Optional[str] = Field(default="景点", description="景点类别")
    rating: Optional[float] = Field(default=None, description="评分")
    photos: Optional[List[str]] = Field(default_factory=list, description="景点图片URL列表")
    poi_id: Optional[str] = Field(default="", description="POI ID")
    image_url: Optional[str] = Field(default=None, description="图片URL")
    ticket_price: int = Field(default=0, description="门票价格(元)")


class Meal(BaseModel):
    """餐饮信息"""
    type: str = Field(..., description="餐饮类型: breakfast/lunch/dinner/snack")
    name: str = Field(..., description="餐饮名称")
    address: Optional[str] = Field(default=None, description="地址")
    location: Optional[Location] = Field(default=None, description="经纬度坐标")
    description: Optional[str] = Field(default=None, description="描述")
    estimated_cost: int = Field(default=0, description="预估费用(元)")


class Hotel(BaseModel):
    """酒店信息"""
    name: str = Field(..., description="酒店名称")
    address: str = Field(default="", description="酒店地址")
    location: Optional[Location] = Field(default=None, description="酒店位置")
    price_range: str = Field(default="", description="价格范围")
    rating: str = Field(default="", description="评分")
    distance: str = Field(default="", description="距离景点距离")
    type: str = Field(default="", description="酒店类型")
    estimated_cost: int = Field(default=0, description="预估费用(元/晚)")


class DayPlan(BaseModel):
    """单日行程"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    day_index: int = Field(..., description="第几天(从0开始)")
    description: str = Field(..., description="当日行程描述")
    transportation: str = Field(..., description="交通方式")
    accommodation: str = Field(..., description="住宿")
    hotel: Optional[Hotel] = Field(default=None, description="推荐酒店")
    attractions: List[Attraction] = Field(default=[], description="景点列表")
    meals: List[Meal] = Field(default=[], description="餐饮列表")


class WeatherInfo(BaseModel):
    """天气信息"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    day_weather: str = Field(default="", description="白天天气")
    night_weather: str = Field(default="", description="夜间天气")
    day_temp: Union[int, str] = Field(default=0, description="白天温度")
    night_temp: Union[int, str] = Field(default=0, description="夜间温度")
    wind_direction: str = Field(default="", description="风向")
    wind_power: str = Field(default="", description="风力")

    @field_validator('day_temp', 'night_temp', mode='before') # before表示数据自定义转换发生在pydantic之前。这个验证器会在创建对象之前自动执行，将字符串转换成整数。
    @classmethod
    def parse_temperature(cls, v):
        """解析温度,移除°C等单位"""
        if isinstance(v, str):
            # 移除°C, ℃等单位符号
            v = v.replace('°C', '').replace('℃', '').replace('°', '').strip()
            try:
                return int(v)
            except ValueError:
                return 0
        return v


class Budget(BaseModel):
    """预算信息"""
    total_attractions: int = Field(default=0, description="景点门票总费用")
    total_hotels: int = Field(default=0, description="酒店总费用")
    total_meals: int = Field(default=0, description="餐饮总费用")
    total_transportation: int = Field(default=0, description="交通总费用")
    total: int = Field(default=0, description="总费用")


class TripPlan(BaseModel):
    """旅行计划"""
    city: str = Field(..., description="目的地城市")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    days: List[DayPlan] = Field(..., description="每日行程")
    weather_info: List[WeatherInfo] = Field(default=[], description="天气信息")
    overall_suggestions: str = Field(..., description="总体建议")
    budget: Optional[Budget] = Field(default=None, description="预算信息")


class TripPlanResponse(BaseModel):
    """旅行计划响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[TripPlan] = Field(default=None, description="旅行计划数据")


class POIInfo(BaseModel):
    """POI信息"""
    id: str = Field(..., description="POI ID")
    name: str = Field(..., description="名称")
    type: str = Field(..., description="类型")
    address: str = Field(..., description="地址")
    location: Location = Field(..., description="经纬度坐标")
    tel: Optional[str] = Field(default=None, description="电话")


class POISearchResponse(BaseModel):
    """POI搜索响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: List[POIInfo] = Field(default=[], description="POI列表")


class RouteInfo(BaseModel):
    """路线信息"""
    distance: float = Field(..., description="距离(米)")
    duration: int = Field(..., description="时间(秒)")
    route_type: str = Field(..., description="路线类型")
    description: str = Field(..., description="路线描述")


class RouteResponse(BaseModel):
    """路线规划响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[RouteInfo] = Field(default=None, description="路线信息")


class WeatherResponse(BaseModel):
    """天气查询响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: List[WeatherInfo] = Field(default=[], description="天气信息")


# ============ 错误响应 ============

class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = Field(default=False, description="是否成功")
    message: str = Field(..., description="错误消息")
    error_code: Optional[str] = Field(default=None, description="错误代码")


# ============ 对话系统模型 ============

class Conversation(BaseModel):
    """会话模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="会话ID")
    title: str = Field(..., description="会话标题", example="北京三日游")
    user_id: str = Field(default="default_user", description="用户ID")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "北京三日游",
                "user_id": "default_user",
                "created_at": "2025-06-01T10:00:00",
                "updated_at": "2025-06-01T10:30:00",
                "metadata": {}
            }
        }


class ChatMessage(BaseModel):
    """聊天消息"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="消息ID")
    conversation_id: str = Field(..., description="会话ID")
    role: Literal["user", "assistant"] = Field(..., description="角色")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "660e8400-e29b-41d4-a716-446655440001",
                "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                "role": "user",
                "content": "我想去北京玩三天",
                "timestamp": "2025-06-01T10:00:00",
                "metadata": {}
            }
        }


class UserProfile(BaseModel):
    """用户画像"""
    user_id: str = Field(..., description="用户ID")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="用户偏好")
    tags: List[str] = Field(default_factory=list, description="用户标签")
    embedding: Optional[List[float]] = Field(default=None, description="向量嵌入")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "default_user",
                "preferences": {
                    "budget": "medium",
                    "style": "quiet",
                    "interests": ["food", "nature"]
                },
                "tags": ["foodie", "nature_lover", "budget_conscious"],
                "embedding": None,
                "created_at": "2025-06-01T10:00:00",
                "updated_at": "2025-06-01T10:00:00"
            }
        }


class ConversationCreateRequest(BaseModel):
    """创建会话请求"""
    title: str = Field(default="新对话", description="会话标题")
    user_id: str = Field(default="default_user", description="用户ID")


class ConversationUpdateRequest(BaseModel):
    """更新会话请求"""
    title: str = Field(..., description="新标题")


class MessageSendRequest(BaseModel):
    """发送消息请求"""
    content: str = Field(..., description="消息内容", example="我想去北京玩三天，预算中等")
    user_id: str = Field(default="default_user", description="用户ID")


class ConversationListResponse(BaseModel):
    """会话列表响应"""
    success: bool = Field(default=True, description="是否成功")
    data: List[Conversation] = Field(..., description="会话列表")


class MessageListResponse(BaseModel):
    """消息列表响应"""
    success: bool = Field(default=True, description="是否成功")
    data: List[ChatMessage] = Field(..., description="消息列表")


# ============ 持久化旅行计划模型 ============

class SavedTripPlan(BaseModel):
    """持久化的旅行计划"""
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="计划ID")
    user_id: str = Field(default="default_user", description="用户ID")
    conversation_id: Optional[str] = Field(default=None, description="关联的会话ID")
    title: str = Field(..., description="计划标题", example="北京三日游")
    plan: TripPlan = Field(..., description="旅行计划详情")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Config:
        json_schema_extra = {
            "example": {
                "plan_id": "770e8400-e29b-41d4-a716-446655440000",
                "user_id": "default_user",
                "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "北京三日游",
                "created_at": "2025-06-01T10:00:00",
                "updated_at": "2025-06-01T10:00:00"
            }
        }


class SaveTripPlanRequest(BaseModel):
    """保存旅行计划请求"""
    user_id: str = Field(default="default_user", description="用户ID")
    conversation_id: Optional[str] = Field(default=None, description="关联的会话ID")
    title: str = Field(..., description="计划标题")
    plan: TripPlan = Field(..., description="旅行计划详情")


class UpdateTripPlanRequest(BaseModel):
    """更新旅行计划请求"""
    title: Optional[str] = Field(default=None, description="计划标题")
    plan: Optional[TripPlan] = Field(default=None, description="旅行计划详情")


class SavedTripPlanResponse(BaseModel):
    """保存的旅行计划响应"""
    success: bool = Field(default=True, description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[SavedTripPlan] = Field(default=None, description="计划数据")


class TripPlanListResponse(BaseModel):
    """旅行计划列表响应"""
    success: bool = Field(default=True, description="是否成功")
    data: List[SavedTripPlan] = Field(..., description="计划列表")


class TripPlanCardMessage(BaseModel):
    """旅行计划卡片消息（用于聊天中显示）"""
    type: Literal["trip_plan_card"] = Field(default="trip_plan_card", description="消息类型")
    plan_id: str = Field(..., description="计划ID")
    title: str = Field(..., description="计划标题")
    city: str = Field(..., description="目的地城市")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    days_count: int = Field(..., description="天数")
    highlights: List[str] = Field(default_factory=list, description="亮点摘要")
    thumbnail_url: Optional[str] = Field(default=None, description="缩略图URL")

