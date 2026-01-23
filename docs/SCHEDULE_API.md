# 排班数据推送接口文档 (Schedule Push API)

## 1. 接口概述
本接口用于接收外部系统推送的排班数据。接口设计灵活，能够自动识别常见的字段名，并将所有未识别的字段完整保留在 `extra_info` 中，确保数据不丢失。

- **URL**: `http://<服务器IP>:8000/api/schedules/`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **鉴权**: 当前开放访问 (AllowAny)，后续可配置 API Key。

## 2. 数据格式

接收 JSON 格式的对象。系统会尝试从 Payload 中解析出核心字段（人员、日期、班次），其余所有字段都会自动存入附加信息中。

### 核心字段映射规则
系统会按顺序查找以下字段，取第一个找到的值：

| 目标字段 | 建议字段名 | 兼容字段名 (自动识别) | 类型 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| **人员名称** | `staff_name` | `employee`, `user`, `name`, `person` | String | 员工姓名 |
| **排班日期** | `shift_date` | `date`, `day`, `time` | String | 格式 `YYYY-MM-DD` |
| **班次类型** | `shift_type` | `shift`, `type`, `period` | String | 如 `Morning`, `Night` 等 |

> **注意**: 即使你不使用上述任何字段名，数据也会被接收并存储在 `extra_info` 中，但在日历视图上可能无法正确显示名称和时间。建议至少匹配上述一个别名。

## 3. 请求示例

### 示例 1：标准格式
```json
{
    "staff_name": "张三",
    "shift_date": "2023-10-27",
    "shift_type": "Morning",
    "department": "IT部",
    "notes": "值班组长"
}
```

### 示例 2：第三方系统格式 (完全兼容)
假设外部系统字段名完全不同，只要包含类似信息即可：
```json
{
    "employee": "Alice",
    "date": "2023-10-28",
    "shift": "Night",
    "meta": {
        "location": "Zone A",
        "weather": "Rainy"
    },
    "source_id": "LEGACY_001"
}
```

## 4. 响应示例

### 成功
- **Status**: `201 Created`
- **Body**:
```json
{
    "id": 15,
    "staff_name": "Alice",
    "shift_date": "2023-10-28",
    "shift_type": "Night",
    "extra_info": {
        "employee": "Alice",
        "date": "2023-10-28",
        "shift": "Night",
        "meta": { ... },
        "source_id": "LEGACY_001"
    },
    "created_at": "2023-10-27T10:00:00Z"
}
```

### 失败
- **Status**: `400 Bad Request` (仅当数据格式严重错误，非 JSON 时)
