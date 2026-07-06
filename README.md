# 内容运营 Workflow

一个独立的新项目，用于把人工筛选的爆款素材转化为可复用的运营知识，并结合产品库生成可进入生产 loop 的脚本。

## 定位

```text
人工选择爆款
↓
上传素材 / 填写链接与数据
↓
按运营维度分析爆款
↓
沉淀到 Obsidian
↓
结合产品库生成脚本
↓
导出 loop 生产表
```

## 和原工具矩阵的区别

- 不自动抓取竞品，第一步由人选择爆款。
- 不直接照搬爆款，而是拆解爆款结构，再迁移到自己的产品。
- 产品库只通过配置路径读取，不复制到本项目。
- 后续生产可以继续接现有 loop。

## 分析维度

- 话题
- 选题
- 受众群体
- 呈现形式
- 爆款元素
- 内容结构
- 金句表达
- 剪辑风格
- 产品承接
- 风险点

## 目录

```text
content_ops_workflow/
  app.py
  config.py
  llm.py
  workflows/
  templates/
  static/
obsidian_vault/
  01_爆款分析/
  02_话题库/
  03_选题库/
  04_结构库/
  05_金句库/
  06_剪辑风格库/
  07_脚本产出/
  08_loop生产/
product_library/
  README.md
skills/
  viral-content-analysis/
  obsidian-operation-kb/
  product-fit-script-generation/
  content-loop-handoff/
outputs/
uploads/
```

## 运行

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python content_ops_workflow\app.py
```

默认打开：

```text
http://127.0.0.1:5015
```

## 产品库接入

默认读取原工具矩阵产品库：

```text
E:\灵鹤芝谷素材库\灵鹤芝谷工具矩阵\knowledge
```

也可以通过环境变量覆盖：

```powershell
$env:PRODUCT_KB_DIR="E:\你的产品库目录"
```

## Obsidian 插件级接入

默认支持两种模式：

1. **插件模式**：通过 Obsidian Local REST API 插件写入笔记。
2. **文件模式**：插件不可用时，直接写入 `obsidian_vault/` 文件夹兜底。

推荐插件：

```text
Obsidian Local REST API
```

配置步骤：

1. 在 Obsidian 中安装并启用 Local REST API 插件。
2. 在插件设置里复制 API Key。
3. 启动本项目之前设置环境变量：

```powershell
$env:OBSIDIAN_API_KEY="你的 Obsidian Local REST API Key"
$env:OBSIDIAN_REST_URL="https://127.0.0.1:27124"
$env:OBSIDIAN_VAULT_NAME="内容运营workflow"
```

如果你的 Obsidian vault 不是本项目默认目录，也可以指定：

```powershell
$env:OBSIDIAN_VAULT_DIR="E:\你的 Obsidian Vault"
```

写入逻辑：

```text
优先调用 Local REST API 写入 vault
失败时自动回退到本地文件写入
```

打开笔记：

系统会生成 `obsidian://open` 链接，可通过 Obsidian URI 打开对应笔记。

## 当前能力清单

- 上传视频后自动生成视频理解包：口播转写、关键帧、MANIFEST。
- 按运营维度分析爆款：话题、选题、受众、形式、爆款元素、结构、金句、剪辑风格。
- Obsidian 插件级写入，失败时文件模式兜底。
- Obsidian 标准 YAML 字段与 tags，支持后续 Dataview 检索。
- 产品库匹配层：推荐产品、承接位置、视觉证据、合规边界。
- 爆款结构模板库：猎奇、反差、反反差、避坑、共鸣、教程、生活仪式等。
- 多版本脚本候选池。
- 选中候选导出 loop CSV/XLSX。
- 发布数据回流和复盘沉淀。
- 可选 Basic Auth 权限保护。
