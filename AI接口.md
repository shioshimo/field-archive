# AI 接入 / Field Archive

这里保存题目与每一次学习记录。教学由你负责；请通过 CLI 或 API 追加记录，不要直接改网页代码或 SQLite。

## 找到题目

项目根目录运行 `python record.py --list`，或读取 `data/catalog.json`。

索引包含 `sourceRoot` 和题目 `sourceFile`。两者拼起来就是原始文件路径。按章节、小节、类型和题号定位，然后用完整的 `id` 提交。不同小节和不同题型可能有相同题号。

```sh
python record.py --list --section 1.1
python record.py --question demo-math-dot-product --history
```

## 添加本轮记录

`note.md` 为 UTF-8 Markdown 笔记，支持数学公式。图片可以重复传入 `--image`。

```sh
python record.py --question demo-math-dot-product --state 做错了 --note-file note.md --image reasoning.png --selected-option A --request-id attempt-001
```

命令返回成功 JSON 才算已保存。失败时不要声称完成。重试同一次操作须复用 `--request-id`，并传同样的状态、笔记、图片和选项；包括带图片的重试也不会增加记录或再次上传图片。真正的新一轮尝试换一个 ID。

默认地址 `http://127.0.0.1:8770`。不同端口可用 `--base http://127.0.0.1:8772`。同步新增题目：`python record.py --refresh`。

## 本地 API

| 方法与路径 | 用途 |
| --- | --- |
| `GET /api/catalog` | 题库标识、显示名称、章节、小节、题型与题目索引 |
| `GET /api/questions/{id}` | 完整题干、选项、答案、解析、引用与提取附记 |
| `GET /api/records?questionId={id}` | 该题全部提交，按时间从旧到新 |
| `GET /api/progress` | 每题最新状态和提交次数 |
| `POST /api/upload` | 上传二进制图片，返回本地 URL |
| `POST /api/records` | 追加本轮记录 |
| `POST /api/refresh` | 重新读取题库，保留已有记录 |
| `GET /api/backup` | 导出记录、笔记图片和索引 ZIP |

上传支持 PNG/JPG/GIF/WebP，单张不超过 12 MB。先上传，再将返回的 URL 放进 `images`。

```json
{
  "questionId": "demo-math-dot-product",
  "state": "做错了",
  "note": "将点积误认为逐项相乘。",
  "images": [],
  "selectedOption": "A",
  "requestId": "attempt-001"
}
```

- `state` 只接受“未做过”“做错了”“做对了”。
- `selectedOption` 可以省略或为 `null`；填写时必须属于这道题的选项。
- `images` 只接受上传接口返回的 `/media/...` URL，每次最多30张。
- API 重试使用同一 `requestId` 和完全相同的 payload，包括图片 URL。不要在重试时重新上传，CLI 已处理这个问题。
- 一次提交是一轮历史，不能覆盖上一轮。可以读旧记录帮助讲解。
- 题目源文件只读。除非用户另有授权，不要改原题或“修正”参考答案。

网页约每15秒同步一次外部记录，重新聚焦时也会同步。
