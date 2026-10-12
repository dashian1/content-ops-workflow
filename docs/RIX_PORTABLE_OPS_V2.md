# RIX 多账号运营工作台 V2
## 可迁移工作区、信息源采集、账号监控与知识库回填｜WorkBuddy 开发任务书

状态：开发规格，尚非已实现功能。日期：2026-10-12。
目标仓库：`dashian1/content-ops-workflow`。
已检查代码基线：`c6195182f1e5a69417261577975cf254bd1f230f`。实施时以实际分支为准，不强行回退。

> 本文完整替代旧版“只做账号和表格、不开发采集”的范围约束。目标是一个能够跨电脑迁移的个人多账号运营项目，不是新的 SaaS，也不是只展示假数据的管理后台。
>
> 核心设计：GitHub 管程序，工作区管数据，本机管凭证。先打通“采集/导入 → 归属与去重 → 监控事件 → 知识回填 → 打包 → 换目录恢复”。

本文中的字段、接口、阈值和阶段均为本项目设计要求，不是平台官方标准。引用 [R] 对应已有代码，[W] 对应官方技术资料，详见末尾。未做目标账号在线验证的连接器必须标注“未验证”。

## 0. 给 WorkBuddy 的执行指令

请在现有仓库上增量开发本任务，不要另起项目，不要只输出建议。
先读实际代码、Git 状态、项目说明和本文；保护未提交内容。使用独立实现分支，不能直接改写 main、强制推送或合并 PR。

本次范围包含：多账号档案与作品台账、参考账号监控、信息源采集、指标历史、知识回填、便携工作区、导出恢复和 GitHub 项目化。抖音、小红书、B站的账号档案均要支持，同平台允许多个账号；真实连接能力按适配器逐项展示，不把建档等同授权。

沿用 Flask，复用现有分析、Obsidian、飞书和 Loop 入口。新增 /workspace 和 /api/workspace/*，使用 SQLite 与本地文件作为核心持久化。不要引入 n8n、Redis、强依赖服务器或新的前端大框架作为启动前提。不配置模型和云端服务，也必须能管理、采集公共信息源、保存知识、导出和恢复。

最先实现“建立工作区 → 管理账号 → 导入/采集 → 保存并关联 → 打包 → 在不同根目录恢复”，之后完善监控、知识回填和平台适配。用户选择其他电脑后，不应重新整理账号、监控列表、知识库和模板；仅重新安装依赖、配置必要凭证。

对不能访问的平台、权限不足、登录失效、限流和解析失败分别报告，不得伪造成功或用示例数据代替实测。需要人工授权时暂停对应任务，不阻塞其他模块。任务交付须含代码、测试、启动脚本、迁移说明、已实现/未验证清单与未覆盖项。

## 1. 产品范围与使用方式

### 1.1 两类账号必须分开

- 自有账号 owned：自己实际运营的账号，关联栏目、原创内容、发布记录、平台导出数据和可用授权。
- 观察账号 watched：参考创作者或信息发布者，关联公开内容、更新时间和可获得的公开指标，不视为已授权账号。

同一个平台身份可以同时具有两种角色，但角色、连接权限和统计范围必须独立。参考账号的播放、粉丝、作品不能进入自有运营数据总览。

平台支持矩阵逐项显示：账号建档、手工导入、读取新作品、读取公开指标、读取自有后台指标、最近实测时间、所需授权、当前错误。没有权限的项目为“不支持/需授权”，不是 0，也不是已接通。

### 1.2 需要的完整工作流

```text
自有账号文件/获授权接口       公开信息源/参考账号
             \             /
              统一采集与导入
                    ↓
       去重、归属、原始证据、历史快照
                    ↓
         自有数据看板 / 监控事件收件箱
                    ↓
        选题卡 / 案例卡 / 可复用知识候选
                    ↓
             用户确认与版本化保存
                    ↓
        本地知识库 + 可选 Obsidian/飞书回填
                    ↓
       后续给提示词/素材生产/Loop提供上下文
```

本轮不开发自动发布、自动评论私信、账号买卖、会员支付、全自动生图/视频或跨设备实时数据库同步。保留它们需要的引用接口即可。

## 2. 现有项目怎么改，而不是推倒重来

| 现有位置 | 核查到的情况 | 本轮增量处理 |
|---|---|---|
| app.py / config.py | Flask 入口，配置上传、输出、Obsidian 和 Loop 目录；默认本机访问。[R1][R2] | 新增 workspace Blueprint、工作区路径服务，不覆盖旧首页 |
| engines/import_engine.py | 链接/表格导入、抖音关键词搜索代码；部分缺失指标转为 0；浏览器配置在 .runtime/douyin_profile。[R3] | 引入统一 adapter/run/source 模型；缺失保留 null；浏览器会话移至设备层 |
| workflows/content_ops.py | 分析、脚本、文件交接与反馈保存；反馈调用模型。[R4] | 数据持久化不依赖模型；模型失败不回填正式知识 |
| agents/runtime.py | 创建与更新任务图、运行记录，不能据此宣称依赖自动执行已完成。[R5] | 新调度器独立实现，复用展示思路，不把节点状态当执行器 |
| engines/loop_engine.py | 创建交接文件与记录结果，不是生成平台执行端。[R6] | 兼容旧交接；新增记录使用稳定业务 ID 与工作区相对路径 |
| obsidian.py | 插件写入，失败回退到本地文件。[R7] | 本地知识先落盘，再投递外部服务，外部失败独立重试 |
| .gitignore | 已忽略部分运行目录、配置、日志。[R8] | 核查 .runtime、工作区、备份、浏览器状态是否遗漏；不能假设历史已清理 |

旧目录迁移采用“用户选择 → dry-run 清单 → 映射 → 复制/索引 → 校验”，禁止自动扫描整盘或自动引入相邻产品库。旧目录保持原状，可回退。

公共仓库只提交通用代码、迁移脚本、说明、空配置与合成测试样例。真实账号列表、监控对象、素材、工作区、知识内容和凭证不提交 GitHub。只迁移用户有权迁移的资料；不同所有权/项目的数据分别建工作区，不自动混打包。

## 3. 第一优先级：代码、数据、设备三层分离

### 3.1 推荐布局

```text
<任意开发目录>/content-ops-workflow/       # GitHub 项目
  content_ops_workflow/
  docs/
  scripts/
  tests/fixtures/                         # 仅合成数据
  requirements.txt / requirements.lock
  workspace.example.json

<用户选择目录>/rix-personal/              # 可携带工作区，不属于 Git
  workspace.json
  db/ops.sqlite3
  assets/                                # 导入/下载并校验过的文件
  imports/                               # 原始导入文件与映射报告
  evidence/                              # 最小必要且脱敏的证据
  knowledge/                             # Markdown / JSON，稳定ID
  templates/                             # 栏目规则、提示词和封面模板
  exports/                               # 导出结果，不递归打包自身

<本机私有配置目录>/RIX/device/            # 不迁移、不提交
  device.json
  secrets/                               # 或系统凭证存储
  browser_profiles/<connection_id>/
  logs/                                  # 脱敏、轮转
  cache/
```

用户可选择新磁盘、新用户名、新目录；不把盘符、Windows 用户名、绝对路径写入可迁移业务数据。`RIX_WORKSPACE_DIR` 或启动参数只负责定位根目录；所有资产引用通过资源 ID/根目录相对路径解析。设备层保存工具安装位置、浏览器路径、代理和凭证引用等本机配置。

工作区身份用 workspace_id；同一次迁移保留该 ID。新设备生成新的 instance_id。模板创建新工作区必须生成新 workspace_id。业务记录主键用 UUID；平台账号和作品 ID 一律 TEXT。

数据库是账号/来源/规则/指标的权威记录，JSON 导出是交换格式，不能让同一份规则在数据库和多个配置文件中各自修改而无同步规则。

### 3.2 启动和维护

- 新工作区不要求 API Key；未绑定凭证的连接器不能启动认证请求。
- 提供创建、选择、关闭、导入工作区；切换前停止旧工作区调度和任务，关闭其数据库，不在同一进程混用全局 SETTINGS。
- UI 默认监听 127.0.0.1；不擅自开放局域网、公网端口或安装开机常驻服务。
- UI 退出不等于后台结束：界面应明确显示 Worker 是否运行；提供“停止全部任务并退出”。
- 第一版支持同一工作区同一时刻一个主动执行实例。跨电脑同步冲突不在本轮解决；迁移后用户需停止旧实例再启用新实例，不能声称本地锁能阻止两份离线副本并行。
- SQLite 工作库放本机正常磁盘，不以 SMB/共享盘或云同步文件夹中的活跃数据库充当多机数据库。[W3]

## 4. 数据包、模板包与换电脑恢复

### 4.1 两种导出

| 类型 | 包含 | 明确不包含 |
|---|---|---|
| 私有工作区包 | 账号档案、作品与指标、信息源与观察名单、监控规则/检查进度、选题与知识、模板、必要附件和已脱敏证据 | 密钥、Cookie、浏览器配置、系统日志、代码仓库和虚拟环境 |
| 可复用模板包 | 用户选择的通用栏目规则、字段映射、采集配置模板、监控条件、经过确认可分享的知识卡 | 真实账号/监控目标、历史数据、原始导入、凭证、个人路径和私有附件 |

私有包也可以选择“只带文字与元数据”或“包含附件”。未打包的附件明确列出名称、大小、缺失原因；不能显示为完整离线包。模板模式使用字段白名单，不是把数据库删几张表后当模板。

文件格式第一版可用标准 ZIP，内部包括：

```text
manifest.json
workspace.json
db/ops.sqlite3
exchange/                             # 可读JSON/CSV，便于其他工具复用
knowledge/
templates/
assets/                               # 用户选择时包含
imports/                              # 用户选择时包含
README_RESTORE.md
```

普通 ZIP 不加密，导出前明确提示，并预览将携带的数据；不得将“脱敏/压缩/有校验和”宣传为加密。使用受信介质保存，不自动上传。加密封装可后续接成熟工具，不能自行发明算法或在未实现时显示“已加密”。

### 4.2 manifest 合同

至少包含 format=rix-workspace、format_version、workspace_id、export_id、exported_at、app_version、source_commit、schema_version、min_reader_version、导出模式、各类实体数量、文件清单、sha256、bytes、被排除项、需重新授权的连接清单、附件缺失列表。

敏感 URL 中的访问令牌、签名和认证查询参数不得写入 manifest；仅保留脱敏目标和凭证别名。哈希用于完整性校验，不是来源真实性证明。不得在包内带执行脚本并在恢复时自动运行。

### 4.3 一致性导出算法

1. 取得工作区导出锁，暂停调度，阻止新业务写入；等运行中的写任务完成，或明确失败退出，不假装成功。
2. 通过 SQLite Backup API / Python Connection.backup 生成临时数据库快照，不直接复制正在使用的 db 文件。[W1][W2]
3. 对旧数据/自由文本做敏感信息检测，按白名单导出配置；不能只删除 .env，却让原始请求头、私有链接、日志或数据库备注泄漏凭证。
4. 在同一冻结边界复制知识与已引用附件；校验无缺失，计算哈希和实体数量。数据库备份本身不保证外部文件一致，必须显式处理。
5. 执行 integrity_check 和外键检查；写 manifest 后打包到临时文件，成功后原子命名为正式导出文件。
6. 解锁并按导出前状态恢复本机任务。清理临时文件；失败不留下可被误认成功的最终包。

UI 的“一键导出”必须调用此过程，而不是在前端下载一个空壳 ZIP。

### 4.4 安全恢复算法

默认“导入为新目录”，不覆盖正在使用的工作区，不做跨包自动合并。

检查包体/文件数/解压总量上限、格式版本、哈希、相对路径；拒绝绝对路径、..、符号链接、Windows 盘符/UNC/ADS 和目录穿越。所有 SQLite 文件按不可信输入验证，禁止加载扩展或执行包内任意 SQL/代码。

恢复到暂存目录，核查数据库和外键、资源引用、数量及唯一键。新程序可执行仓库自带的已测试迁移，迁移前保留原始备份；新格式不能被旧程序静默改写。全部通过后再切换成新工作区，原工作区不动。

恢复后：保留知识、来源游标、历史事件和业务 ID；清除运行锁、租约和设备路径；未完成任务标为 interrupted，定时任务默认 paused，认证连接显示 needs_reauth。用户查看差异和来源列表后再启用调度，不能一导入就联网全量抓取。

### 4.5 可搬数据不等于可搬运行环境

Python 虚拟环境不作为迁移物，应在目标目录重建。[W5] 交付 Windows 的 setup.ps1、start.ps1、stop.ps1、doctor.ps1 和依赖锁定说明。不得依赖旧电脑已安装但未记录的浏览器、CLI 或系统路径。

本轮目标：有兼容 Python 的新 Windows 环境可按说明安装并恢复；“无需安装的 EXE”和完全离线安装包是后续交付，不冒充已经支持。

## 5. 多账号与数据管理

新增账号时选择 owned / watched、平台、昵称、主页、可选平台 ID、栏目、定位、标签与运营状态。账号状态与连接状态分开。

原创内容 content 与各平台发布记录 publication 是一对多：一期内容可以在多个账号发布，每个 publication 单独绑定账号、平台作品 ID、发布时间及指标历史。不同标题不自动判断为同一期；用户显式关联。

自有账号数据优先导入平台导出 CSV/XLSX，或使用真正获授权的官方接口。观察账号仅获取被允许的公开字段。浏览器已登录不代表拥有所有数据权限。

### 5.1 指标与快照

- 区分 published_at、observed_at、imported_at；默认显示 UTC+08:00，存 UTC，保留原始时间与精度。
- 缺失为 null，真实 0 为 0；单位如 1.2万可转换并记录 approximate=true，未知或解析失败不能静默写 0。
- views、impressions、likes、comments、saves、shares、followers、完播率等各自存储并保留定义，不混为同一个字段。
- 区分累计 cumulative 与区间 interval；累计快照取最新值，不把多次快照求和。区间值必须保存起止，不合并重叠窗口。
- 粉丝增长只有存在可比观测点才计算；没有采集到不能解释成降为 0。跨账号粉丝之和不是去重人数。
- 每次修订保留来源与审计；采集窗口内未找到旧作品，只能标记“本次未观察到”，不能判断已删除。

### 5.2 导入

上传 → 选账号/数据集 → 选表头和工作表 → 字段映射 → 确认口径与数据时间 → 预览 → 校验 → 入库 → 报告。

保留原文件、哈希、映射版本、行号、原始值和修订记录。import_key 包含文件哈希、账号、映射与观测口径；重复提交返回原结果。冲突进入待确认，不覆盖人工修正。ID 已在 Excel 中丢精度时报警，不猜测修复。

CSV/XLSX 不执行宏或公式；导出处理公式注入。只读用户选中的文件，不扫描其他目录。每批只绑定一个账号，先不做无法校验的跨账号自动分发。

## 6. 信息源、爬虫和适配器

### 6.1 必须实际开发的接入层

| 接入 | 要做的事 | 验收口径 |
|---|---|---|
| RSS/Atom | 原生订阅源采集、去重、增量更新、来源跳转 | 真实端点测试 + 离线夹具；实现 ETag/Last-Modified/304。[W7] |
| GitHub Releases | 用户指定公开仓库的发布信息监控，支持分页 | 使用官方 REST，release ID 去重，不把 tag 或提交时间当发布时刻。[W6] |
| 允许采集的公开网页 | 限定站点、配置化列表/详情解析、内容变更监控 | 每站一套测试样例；未配置站点明确不支持 |
| 既有抖音采集 | 重构为可选适配器，接统一结果和任务记录 | 先验证关键词搜索；主页账号监控须独立实现和验收，不能拿搜索替代 |
| 小红书/B站等 | 支持账号建档、链接/文件导入；预留站点连接器 | 按真实权限、规则和样例补接，不宣传全平台可爬 |

[uncertain] 抖音、小红书和B站的实际可采集字段、页面稳定性及目标账号权限尚未做本机验证。国内平台至少选择一个账号完成真实“首次建基线 → 再次检查 → 去重”验证后，才能标为已接通；受阻则交付明确报告，不能以 RSS 演示冒充完成该平台。

RSSHub 可以作为可选 RSS 输入，但不是强依赖；采用具体路由前核查其可用性、部署需求、许可和认证要求。GitHub 采集代码只使用 REST 官方接口，不爬 GitHub 网页热榜冒充官方榜单。

### 6.2 统一接口

```text
probe(source, device_binding) -> capabilities + status + verification
fetch(source, cursor, limits) -> items + observations + next_cursor + coverage
normalize(item) -> 标准化记录及字段来源
```

source 至少保存：id、kind、platform、target_url、target_account_id、scope、adapter_id/version、enabled、cadence、keywords/include/exclude、公开非敏感配置、credential_alias、最近检查/成功时间、cursor、错误原因。

每条 item 保存：稳定平台 ID 或 feed GUID、来源 URL、规范 URL、标题、作者、发布时间、首次见到时间、内容哈希、摘要/允许保存的正文、来源标识及采集任务 ID。无可靠 ID 时使用规范 URL；标题不能作为唯一键。只去除已知追踪参数，保留决定内容身份的参数。去重保留多来源关联，不丢证据。

抓取结果 coverage 明确 complete / partial / unknown；分页未走完不得推进到遗漏内容的游标。游标只有在对应数据落盘事务成功后才更新；对相同请求重试不重复产生日志事件或业务记录。

### 6.3 请求与权限边界

遵循来源规则、授权和请求限制，优先官方 API/原生订阅；不实现验证码破解、账号池轮换、反检测强化或绕过付费/访问控制。遇登录和验证码时暂停该来源，交给用户处理。不要把仓库现有 stealth 逻辑当作保证可用性的基础。

数据请求设超时、响应大小上限、每域名并发上限和有界重试；尊重 Retry-After 和平台限流信息。[W8] 不无限重试。公开 URL 采集阻止 SSRF：检查协议、域名、DNS/IP及重定向目标，拒绝内网/回环地址；受控的本地 Obsidian 连接走单独配置与白名单，不能借网页采集通道访问。

只存必要字段，不默认下载所有视频、不保存私有评论/私信。原始证据去除认证头、Cookie、Token和签名下载URL，证据不足就明确标记。

## 7. 账号监控与执行器

监控项至少支持：新内容发布、可比指标达到阈值、来源停止更新提醒、连接失效/连续采集失败。关键词过滤、排除词、按账号启停、立即检查和定时间隔均可配置。

首次导入建立 baseline，历史作品进入资料库但不一口气报成“今日新作品”；后续新增才生成事件。以首次观察时间和原发布时间同时展示，无法判断真实发布日期的不得声称刚发布。

指标变化示例：两次观测点赞 1000 → 1500，可展示观测间新增 500，并写明窗口；不能从累计值直接推断每小时增长。告警从未达到变为达到时触发一次，event_key 去重，已读状态可迁移。

独立 Worker 负责领取 SQLite 任务，不在 Flask debug reloader 下重复注册定时器。任务状态：queued / running / waiting_user / succeeded / partial / failed / cancelled / interrupted。领取时用事务与租约，记录尝试次数、错误类型、adapter版本、分页进度；崩溃后可恢复。

默认按需或较低频率检查，实际下限由来源规则决定；产品初始建议每小时一次，但不是适用于所有平台的授权。重新开机不追发关机期间所有定时任务，可合并为一次检查并记录覆盖缺口。没有常驻运行实例就不能持续监控；GitHub 存放代码不等于代替电脑执行。

第一版通知中心在工作台内。飞书/Webhook 为可选出口，重复事件不得重复推送，外部通知失败不能回滚本地事件。Webhook 地址视为凭证放设备层。

## 8. 知识库回填：从存笔记到可复用知识

分清三层：

1. evidence：来源和客观观察，带时间、链接、指标口径。
2. draft：用户或模型形成的选题、结构和经验候选。
3. approved：用户确认可复用的规则、案例、提示词经验。

自动采集可以入库；未经审核的模型推断不能直接写成“已验证运营规律”。每条知识包含 knowledge_id、类型、标题、正文、source_item_ids、account/series范围、证据时间、来源URL、生成方式、模型/提示词版本（使用时）、状态、revision、人工备注。资料文本是待分析数据，不得作为系统指令执行。

### 8.1 回填过程

选来源/作品/监控事件 → 创建知识卡 → 关联原始证据 → 本地保存 → 用户批准 → outbox生成外部投递任务。

本地知识以稳定ID文件保存，如 `knowledge/cases/<id>.md`，数据库保存索引、版本和哈希。Markdown带YAML元数据，可单独带走并用普通编辑器打开。全文检索至少支持关键词、标签、账号、栏目和来源过滤；第一版不要求向量数据库或付费嵌入。

不要每次回填都用时间戳生成新笔记。相同ID更新受管区域；只更新程序负责的字段，保留人工备注。发现文件已被外部编辑，按哈希进入冲突处理，不静默覆盖。

本地写入与索引用临时文件+原子替换+可恢复日志保证最终一致，崩溃后可校验/重建索引。外部 Obsidian/飞书用 `(knowledge_id, revision, destination)` 唯一键投递，可重试，不让外部服务变成唯一数据存储。

数据回流依靠 publication_id、knowledge_id 和来源关系，不能靠标题猜测。账号整体涨粉不能直接归因单条作品；少量表现好的作品只形成“待验证假设”，不是因果结论。

## 9. 核心数据表与约束

可分批建表，但以下语义不能省略；所有表受工作区边界约束。

| 实体 | 核心字段/关系 |
|---|---|
| accounts / account_roles | platform、platform_user_id、规范主页、昵称；角色 owned/watched；身份去重 |
| series / contents / publications | 栏目 → 内容 → 各平台发布；publication绑定账号和作品ID |
| account_snapshots / publication_snapshots | entity、observed_at、scope、窗口、metrics、source_kind、source_ref；可空指标 |
| sources / source_accounts | 适配器配置、监控目标、cursor、coverage、verification、最近成功/错误 |
| source_items / item_sources | 内容去重实体与多来源关系；first_seen、published_at、content_hash |
| observations | 来源读取的公开指标和观测时间，与自有指标权限清晰区分 |
| monitor_rules / monitor_events | 条件、基线、事件唯一键、ack状态、数据证据 |
| import_batches / import_rows | 原文件、映射、行号、原始值、冲突、import_key |
| knowledge_items / knowledge_revisions / knowledge_links | 稳定ID、审核状态、证据关系、版本与本地相对路径 |
| jobs / job_attempts / outbox | 执行状态、租约、重试、游标和外部投递幂等 |
| assets / audit_events | 相对路径、哈希、类型、所属对象；修改前后与来源 |

数据库开启外键；同账号/同作品/同观测窗口的重复数据不能新增一份累计统计。连接的凭证只在设备层按别名解析，业务数据库不存明文Token或登录态。

## 10. 页面与接口

### 10.1 中文工作台

```text
总览
账号管理（我的账号 / 观察账号）
信息源（订阅 / 网页 / 仓库 / 账号来源）
监控收件箱
作品与数据
知识库（证据 / 草稿 / 已确认）
任务与错误
设置与迁移（工作区 / 打包 / 恢复 / 模板复用）
```

数据更新时间、来源、连接能力和监控状态必须可见。空白页有明确操作入口，不用随机数填图表。账号多选、平台/栏目筛选、搜索、归档/恢复、批量暂停和导出要真实可用。

### 10.2 新接口前缀 /api/workspace

| 接口组 | 必须覆盖 |
|---|---|
| accounts、contents、publications | 列表/详情/增改/归档、显式关联 |
| imports | 上传、映射预览、校验、提交、报告、受控撤销 |
| sources | 创建、probe、run、启停、测试结果与能力 |
| monitors、events | 规则、基线、事件列表、确认已读 |
| knowledge | 草稿、审核、修订、冲突、来源、投递状态 |
| jobs | 状态、详情、取消、有限重试 |
| packages | 导出预览、导出任务、校验、恢复预览、恢复到新目录 |
| health、doctor | 工作区/schema/依赖/权限状态；不泄露密钥 |

写接口服务端验证、事务、幂等与统一错误码。长任务返回 job_id，通过状态接口查询；HTTP 200 不等于业务成功。数据导入、知识保存和导出不强制调用模型。更新/归档用版本号避免旧页面覆盖新数据。

## 11. GitHub 项目化与安全边界

建议新增 workspace/routes.py、services、repositories、adapters、worker、migrations、portable、tests 和 scripts；只在需要时拆文件，避免单个 app.py 持续膨胀。

实现分支示例 `feat/portable-ops-workspace`。小步提交，建议顺序：工作区/迁移 → 账号/导入 → 来源/任务 → 监控 → 知识回填 → 打包恢复 → 测试/说明。

.gitignore 至少检查工作区目录、*.sqlite3及-wal/-shm、.runtime、browser_profiles、playwright/.auth、secrets、.env、runtime_config.json、导出包与日志。样例配置显式允许提交，不提交真实配置。已有被Git跟踪的敏感文件不会因新增ignore自动消失；先报告，凭证泄漏要失效/轮换，不擅自重写远程历史。[W4][W9]

提交前查看实际暂存文件白名单，不能盲目 git add .。CI只跑合成夹具、数据库和恢复测试，不接真实账号，不使用个人工作区作为artifact，不自动在GitHub Actions跑登录态爬虫。

在新分支提交已检查的代码是项目化的一部分；远程推送和开PR需要遵循用户授权。禁止自动合并main、强制推送、覆盖未知本地修改。资料和凭证只随受控迁移包移动，不随代码发布。

## 12. 实施顺序与退出标准

| 阶段 | 交付 | 退出标准 |
|---|---|---|
| A：便携底座 | 工作区路径、SQLite迁移、启停/doctor、最小导出恢复 | 新根目录恢复后不依赖旧路径 |
| B：账号与数据 | owned/watched、内容发布、CSV/XLSX、快照 | 重复导入不重复计数，账号不串数据 |
| C：信息采集 | RSS、GitHub、受控网页、已有抖音适配层 | 真实/夹具结果分开，增量与错误可复现 |
| D：监控执行 | Worker、基线、规则、事件、暂停/恢复 | 不重复告警、不把失败当无更新 |
| E：知识回填 | 证据/草稿/审核、稳定ID、可选外部投递 | 断网仍可保存，重试不重复笔记 |
| F：迁移复用验收 | 完整包/模板包、文档、测试、启动脚本 | 跨目录恢复与泄密/损坏测试通过 |

不得以完成B阶段宣称整个多账号监控项目完成。国内平台真实接入受阻时，继续交付A/B及公开来源闭环，并列明未通过的适配器。

## 13. 必须执行的验收测试

T01 无API Key创建工作区、账号和知识卡，重启仍存在。
T02 同平台两个自有账号、一个观察账号，数据与筛选不混用。
T03 一期内容有两个发布记录，各自指标历史独立。
T04 同文件重复导入、重复点击提交均不重复计数。
T05 缺失、真实0、单位缩写、超长ID和解析错误正确区分。
T06 累计快照100与150不统计成250，时间窗口和指标定义可追溯。
T07 RSS首次建基线，第二次新增才产生事件；304不是采集失败。
T08 GitHub发布翻页、ID去重、发布/创建时间和预发布标识正确。
T09 网页解析失败、鉴权错误、403/429、超时分别记录，不清空历史。
T10 单来源分页部分成功时保留coverage和可重试位置，不漏过游标。
T11 重复任务与worker重启不造成重复事件；取消/失效租约可恢复。
T12 首次监控不把历史作品全报为新内容；变化未越阈不重复告警。
T13 观察指标与自有后台指标清楚隔离；未知不当下降到0。
T14 知识保留来源和审核状态，未经批准的模型内容不写正式规则。
T15 相同知识回填两次不生成重复笔记，外部人工编辑不被覆盖。
T16 Obsidian/飞书不可达时，本地保存成功，投递失败可单独重试。
T17 SQLite启用WAL且有最近提交时，导出恢复仍包含这些数据。
T18 打包期间并发写入被阻止或受控完成，数据库/知识/附件一致。
T19 人工植入的测试Token、Cookie、凭证查询参数不进入工作区包或Git。
T20 损坏包、路径穿越、符号链接、超限解压和不兼容版本被拒绝，原数据不动。
T21 从 `C:\demo one\workspace` 恢复到 `D:\新目录\工作区`，路径与附件均可用；测试环境无D盘时使用两个不同临时根目录并标注覆盖范围。
T22 恢复后规则/游标/历史/知识保持，凭证需重新绑定、任务默认暂停。
T23 新设备重新授权并启用后，从正确进度继续，不把历史全量当新事件。
T24 模板包创建新工作区，复用规则与模板，不带真实账号、名单、历史和秘密。
T25 干净Windows按锁定依赖启动；未实测Windows时明确未验证，不能拿Linux测试替代。
T26 不配置外部Loop或旧产品库，新模块照常使用；原路由兼容性测试通过。
T27 至少一个国内平台目标账号按“基线/二次检查/身份归属”单独实测；受阻时标记未通过，不伪造。

迁移不要求两台电脑同时在线；测试可先用两个隔离目录模拟。但模拟跨目录不能证明所有操作系统、权限和浏览器环境已兼容，交付报告必须区分。

## 14. 最终交付清单

可运行增量代码、schema迁移、所有依赖说明、Windows启停/doctor、完整包与模板包导入导出、合成fixture、自动化测试报告、真实连接验证清单、页面截图、docs/PORTABILITY.md、docs/CONNECTORS.md、docs/ACCEPTANCE.md，以及无密钥的示例配置。

报告必须逐项写：已实现且通过、已实现未实测、未实现、受外部权限阻塞。不要写“支持所有平台”“一键全自动运营”或“迁移后无需授权”，除非对应测试真的成立。

## 15. 资料与核查依据

以下是选型与已有代码依据，不代表已经运行验证整个系统。引用只支持相关事实；其余为本项目设计。

[R1] Flask入口：https://github.com/dashian1/content-ops-workflow/blob/c6195182f1e5a69417261577975cf254bd1f230f/content_ops_workflow/app.py
[R2] 路径与配置：https://github.com/dashian1/content-ops-workflow/blob/c6195182f1e5a69417261577975cf254bd1f230f/content_ops_workflow/config.py
[R3] 现有导入与抖音采集：https://github.com/dashian1/content-ops-workflow/blob/c6195182f1e5a69417261577975cf254bd1f230f/content_ops_workflow/engines/import_engine.py
[R4] 脚本与反馈：https://github.com/dashian1/content-ops-workflow/blob/c6195182f1e5a69417261577975cf254bd1f230f/content_ops_workflow/workflows/content_ops.py
[R5] 任务图状态：https://github.com/dashian1/content-ops-workflow/blob/c6195182f1e5a69417261577975cf254bd1f230f/content_ops_workflow/agents/runtime.py
[R6] Loop交接：https://github.com/dashian1/content-ops-workflow/blob/c6195182f1e5a69417261577975cf254bd1f230f/content_ops_workflow/engines/loop_engine.py
[R7] Obsidian写入：https://github.com/dashian1/content-ops-workflow/blob/c6195182f1e5a69417261577975cf254bd1f230f/content_ops_workflow/obsidian.py
[R8] Git忽略配置：https://github.com/dashian1/content-ops-workflow/blob/c6195182f1e5a69417261577975cf254bd1f230f/.gitignore
[W1] SQLite在线备份：https://sqlite.org/backup.html
[W2] Python SQLite接口与backup：https://docs.python.org/3/library/sqlite3.html
[W3] SQLite WAL及共享内存限制：https://sqlite.org/wal.html
[W4] GitHub忽略文件及已跟踪文件：https://docs.github.com/en/get-started/git-basics/ignoring-files
[W5] Python虚拟环境迁移限制：https://docs.python.org/3/library/venv.html
[W6] GitHub Releases REST：https://docs.github.com/en/rest/releases/releases
[W7] Feedparser条件请求：https://feedparser.readthedocs.io/en/stable/http-etag.html
[W8] GitHub API最佳实践与限流处理：https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
[W9] Playwright认证状态敏感性：https://playwright.dev/python/docs/auth
