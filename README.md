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

