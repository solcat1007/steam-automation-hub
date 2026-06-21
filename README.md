# Steam Automation Hub — Steam 全自动 AI 助手

> 基于腾讯云 SCF 的 Steam 全自动 AI 助手 — 消息监控、库存管理、交易机器人、愿望单追踪、市场分析一站式解决方案。
> **一键云端部署，7x24 小时无人值守，零本地运维。**

## 项目概述

本项目提供了一个完整的 Steam 自动化解决方案，基于腾讯云云函数（SCF）和 GitHub Actions 实现全自动运维。从搭建到上线，全程傻瓜式部署，无需任何服务器管理经验。

### 包含的核心模块

| 模块 | 功能 |
|------|------|
| **消息监控** | Steam 聊天消息实时抓取、自动回复、关键词告警 |
| **库存管理** | 库存扫描、物品自动上架/下架、批量操作 |
| **交易机器人** | 自动报价、自动确认、库存核对、交易记录 |
| **愿望单追踪** | 愿望单游戏价格监控、折扣推送、链接生成 |
| **市场分析** | 市场物品价格追踪、趋势分析、价格预警 |

## 技术架构

```
用户 → SCF API 网关 → Steam Web API + Steamworks SDK
                          ↓
                    数据处理层 (Python/Node.js)
                          ↓
                    云数据库/云存储 → 告警/推送
```

- **运行时**：Python 3.10 / Node.js 18
- **部署平台**：腾讯云云函数 SCF + API 网关
- **CI/CD**：GitHub Actions 自动化部署
- **存储**：腾讯云 COS + 云数据库 Redis
- **通知**：Server酱 / PushPlus / QQ Bot 多渠道推送

## 快速部署

### 前置条件
1. 腾讯云账号（开通 SCF 和 API 网关）
2. Steam API Key（从 [Steam Community](https://steamcommunity.com/dev/apikey) 获取）
3. GitHub 账号（fork 本项目）

### 部署步骤
```bash
# 1. 克隆项目
git clone https://github.com/solcat1007/steam-automation-hub.git
cd steam-automation-hub

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量（复制并编辑）
cp .env.example .env
# 编辑 .env 填入 Steam API Key、SCF 配置等

# 4. 本地测试
python main.py --test

# 5. 部署到腾讯云 SCF
# 按照 docs/DEPLOY.md 中的步骤操作
```

## 功能特性

### Steam 消息监控
- WebSocket 实时连接 Steam Chat
- 关键词匹配自动回复
- 敏感操作告警推送
- 多语言消息支持

### 库存/交易管理
- 自动接受/拒绝交易报价
- 库存扫描与 CSV 导出
- 批量上架/下架市场
- 价格监控与自动调价

### 愿望单追踪
- 多账号愿望单批量管理
- 折扣推送（邮件/QQ/Server酱）
- 历史价格走势图
- 愿望单分享页生成

### 市场分析
- 物品价格历史数据采集
- 价格波动告警
- 热门物品排行榜
- 利润计算器

## 配置说明

所有配置通过环境变量管理，支持 `.env` 文件或 SCF 控制台配置：

| 变量 | 说明 | 必填 |
|------|------|------|
| STEAM_API_KEY | Steam Web API 密钥 | 是 |
| STEAM_USERNAME | Steam 登录用户名 | 是 |
| STEAM_PASSWORD | Steam 登录密码 | 是 |
| SCF_REGION | 腾讯云 SCF 部署区域 | 是 |
| NOTIFY_CHANNEL | 通知渠道 (serverchan/pushplus/qq) | 否 |
| REDIS_URL | 云数据库 Redis 连接地址 | 否 |

## 许可证

MIT (c) solcat1007