# 🎮 Steam Automation Hub

> 基于腾讯云 SCF 的 Steam 全自动 AI 助手，从零搭建到云端上线，一站式解决方案。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Tencent%20Cloud%20SCF-orange)](https://cloud.tencent.com/product/scf)

## 📖 项目简介

Steam Automation Hub 是一套完整的 Steam 自动化工具集，深度集成 Steam Web API 与 SteamKit 协议，支持腾讯云 SCF 云端 7×24 小时无人值守运行。覆盖消息实时监控、库存管理、交易机器人、愿望单追踪等核心场景，完整源码开箱即用，一键部署即可拥有专属 Steam 自动化管家。

### 🚀 核心功能

| 模块 | 功能 | 说明 |
|------|------|------|
| 📨 消息监控 | Steam 消息实时抓取、自动回复、关键词触发 | 基于 SteamKit 长连接，毫秒级响应 |
| 🎒 库存管理 | 饰品库存同步、自动上架、价格追踪 | 支持 CS2/Dota2/TF2 等多游戏 |
| 🤖 交易机器人 | 自动接收报价、条件审批、拒绝规则 | 灵活的交易策略引擎 |
| ⭐ 愿望单追踪 | 愿望单变动监控、降价通知、上新提醒 | 支持多渠道推送 |
| ☁️ 云端部署 | 腾讯云 SCF + 云数据库，零成本运维 | 一键部署，永久在线 |

## 🛠️ 快速开始

### 环境要求

- Python 3.10+
- 腾讯云账号（用于 SCF 部署）
- Steam 账号（需开启手机令牌）

### 本地运行

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/steam-automation-hub.git
cd steam-automation-hub

# 安装依赖
pip install -r requirements.txt

# 配置
cp config/config.example.yaml config/config.yaml
# 编辑 config/config.yaml 填入你的 Steam 凭证

# 运行
python -m src
```

### 云端部署

```bash
# 一键部署到腾讯云 SCF
cd cloud
pip install -r ../requirements.txt -t .
python scf_deploy.py
```

## 📁 项目结构

```
steam-automation-hub/
├── src/                    # 核心源码
│   ├── __init__.py         # 包入口
│   ├── steam_client.py     # Steam API 客户端
│   ├── message_monitor.py  # 消息监控模块
│   ├── inventory_manager.py # 库存管理模块
│   ├── trade_bot.py        # 交易机器人
│   ├── wishlist_tracker.py # 愿望单追踪
│   └── utils.py            # 工具函数
├── cloud/                  # 云端部署
│   ├── scf_handler.py      # SCF 入口函数
│   └── serverless.yml      # SCF 配置模板
├── config/                 # 配置文件
│   └── config.example.yaml # 示例配置
├── docs/                   # 文档
├── requirements.txt        # Python 依赖
└── README.md
```

## ⚙️ 配置说明

```yaml
steam:
  username: "your_steam_username"
  password: "your_steam_password"
  shared_secret: "your_2fa_shared_secret"  # 手机令牌密钥
  identity_secret: "your_identity_secret"

tencent_cloud:
  secret_id: "your_secret_id"
  secret_key: "your_secret_key"
  region: "ap-guangzhou"

notifications:
  webhook_url: ""  # 消息推送 Webhook（支持企业微信/钉钉/Discord）
  email: ""
```

## 📝 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

---

<p align="center">
  <b>从零搭建 · 云端运行 · 永久在线</b><br>
  Made with ❤️ by 沐晴
</p>
