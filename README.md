# LLM Field Archive

**研习档案 · LLM-assisted study terminal**

一个放在本地的题目与学习记录空间。你来思考，AI 帮你讲解和整理，这里留住每一次尝试。

<p align="center">
  <a href="https://github.com/user-attachments/assets/d4d06461-1b93-481f-9884-c5cc38d8da24"><img src="https://github.com/user-attachments/assets/d4d06461-1b93-481f-9884-c5cc38d8da24" width="31%" alt="界面预览 1" /></a>
  <a href="https://github.com/user-attachments/assets/1179dafc-34c0-4531-ba89-d8abb10bbc88"><img src="https://github.com/user-attachments/assets/1179dafc-34c0-4531-ba89-d8abb10bbc88" width="31%" alt="界面预览 2" /></a>
  <a href="https://github.com/user-attachments/assets/e260e029-5af0-49a6-8d3e-f330e188c6b9"><img src="https://github.com/user-attachments/assets/e260e029-5af0-49a6-8d3e-f330e188c6b9" width="31%" alt="界面预览 3" /></a>
</p>
<p align="center"><sub>点击截图查看原图</sub></p>


## 这是什么

它是一副通用的学习载体。数学、英语、计算机，或你正在学的其他科目，都可以按章节放进来。题目来自你自己的文件，程序只负责展示与记录。

界面采用浅灰、石墨色和少量黄铜色。细线、编号、档案标签组成一个安静的科研终端。答案默认收起，记录放在旁边，打开页面就能开始看题。

- 按章节、小节浏览；搜索题干，筛选题型与做题状态。
- Markdown、数学公式、表格、代码块，以及可放大的题目配图。
- 未做过 / 做错了 / 做对了，由你或教学 AI 判断。
- 每次提交独立保存文字、图片和所选选项。历史记录随时点开。
- 图片可以上传，也可以直接粘贴到笔记框。
- AI 可以通过 CLI 或本地 API 记笔记，不必改网页或碰数据库。
- SQLite 保存正式记录，浏览器保留未提交草稿；支持记录 ZIP 导出与数据库备份。

**无需模型 API Key。** 这里没有内置聊天模型，也不自动批改题目。你使用的 AI 在外部教学，通过本地接口添加记录。

## 开始使用

需要 **Python 3.10 或更新版本**。前端资源随项目提供，没有 Node.js 构建步骤，也不依赖在线 CDN。

```sh
git clone https://github.com/shioshimo/llm-field-archive.git
cd llm-field-archive
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe server.py
```

macOS / Linux：

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

打开 **http://127.0.0.1:8770/**。首次运行会载入六道原创演示题，展示数学、程序设计和英语三种内容。

Windows 安装依赖后，也可以双击 `启动.cmd`。它会在后台启动服务，再打开浏览器。以后使用不需要回到任何聊天窗口。

## 放入自己的题库

复制 `config.example.json` 为 `config.local.json`，把 `source` 改成你的题库目录。配置里的相对路径以配置文件所在目录为起点。

```json
{
  "source": "private/my-subject",
  "data": "data",
  "port": 8770
}
```

重启后读取新目录。运行时增加或更新题目，在“题目档案”底部点 **同步题库**。已有做题记录保留。

每个实例读取一个题库。同一个题库可以含不同学科；独立题库也可以使用不同的 `data` 目录和端口分别运行。

### 题目文件

推荐一题一个 `question.json`，也支持固定标题结构的 `question.md` / `题目与答案.md`。原始文件始终只读。

```text
my-subject/
├── archive.json
└── 数学语言/
    └── 向量与矩阵/
        └── 01-dot-product/
            ├── question.json
            └── diagram.png
```

```json
{
  "id": "math-dot-product-001",
  "number": 1,
  "type": "单项选择题",
  "title": "点积",
  "stem": "向量 $(1,2)$ 与 $(3,4)$ 的点积是多少？",
  "options": [
    {"label": "A", "markdown": "$7$"},
    {"label": "B", "markdown": "$11$"}
  ],
  "answer": "B",
  "explanation": "$1\\times3+2\\times4=11$。"
}
```

没有选项的题省略 `options`，或填空数组。`type` 可以自定义，筛选器会自动列出。选项标签支持 A–Z；当前一次记录保存一个所选标签，多选题可在笔记里记下完整选择。

章节、小节默认由两层目录名确定，也可以在 JSON 中明确填写 `chapter`、`section`。配图按相对路径引用，例如 `![图示](diagram.png)`。详细格式见 [题库格式](docs/archive-format.md)。

**建议始终填写唯一 `id`。** 修改题干、移动目录后，记录仍能跟着同一道题。省略 ID 时会按题库标识与文件相对路径生成；此时重命名题目目录会被识别为新题。

### 科目与章节顺序

题库根目录的 `archive.json` 决定显示名称、编号和章节顺序。没有这个文件时，根据目录自动分组。

```json
{
  "id": "my-math-archive",
  "subject": "线性代数",
  "code": "MATH",
  "chapters": [
    {"name": "数学语言", "number": 1, "shortName": "数学", "sections": ["向量与矩阵", "微积分"]}
  ]
}
```

## 与 AI 一起使用

把 [AI接口.md](AI接口.md) 交给教学 AI。它可以查题目 ID、读源文件、追加本轮笔记和图片。网页会定期同步外部提交。

```sh
python record.py --list --section 1.1
python record.py --question demo-math-dot-product --state 做错了 --note-file note.md --request-id attempt-001
python record.py --question demo-math-dot-product --history
```

复用同一个 `request-id` 重试同一份提交，不会多出一轮记录。新一轮做题使用新的 ID。

## 本地数据

| 位置 | 内容 |
| --- | --- |
| `config.local.json` | 你自己的题库路径和配置 |
| `data/catalog.json` | 题目索引、源文件位置与导入提示 |
| `data/archive.sqlite3` | 题目快照和每轮提交 |
| `data/media/` | 笔记图片 |
| `data/backups/` | 每日数据库快照 |

“备份记录”导出 ZIP，包含提交、笔记图片与索引。完整迁移建议停止服务后复制整个 `data/` 和自己的题库。数据库快照只包含数据库，不包含图片；恢复时需保留对应 `media/`。当前没有 ZIP 一键导入界面。

公开仓库仅包含程序、原创演示题与界面截图。**不附带商业教材、扫描页、私人题库或学习记录。** 本地配置、数据目录和私人题库目录均在 `.gitignore` 中。

## 开发

Python 标准库 HTTP 服务 + SQLite，Pillow 校验上传图片。前端为原生 HTML / CSS / JavaScript；Marked、DOMPurify 和 KaTeX 随仓库提供。

```sh
python -m unittest discover -s tests -v
```

服务监听本机 `127.0.0.1`，用于个人学习。目前没有账户体系或公网服务方案。

导入校验文件结构、选项切分与图片引用。它不会重新判题，也不会凭猜测纠正来源内容。无法导入的文件会列在索引的 `issues` 中。

## 致谢

视觉方向参考了 [RhineLabUI](https://github.com/LBEILC/RhineLabUI) 的科研档案与终端表达。这里采用二维界面，没有使用它的 3D 模型或游戏素材。

第三方库及许可证见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。项目程序与原创演示内容采用 [MIT License](LICENSE)。
