# 跟踪一次循环

## 题目描述

下面程序最终输出什么？写出 `total` 每一轮的变化。

```python
total = 0
for value in [2, 3, 5]:
    total += value
print(total)
```

## 参考答案

输出 `10`。

## 详细解析

| 轮次 | value | total |
| --- | --- | --- |
| 初始 | — | 0 |
| 1 | 2 | 2 |
| 2 | 3 | 5 |
| 3 | 5 | 10 |

这是原创演示题，也展示了 Markdown 的代码块与表格。
