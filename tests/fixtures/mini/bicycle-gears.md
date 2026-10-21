---
title: 自行车变速：齿比的算法
published: "2026-01-02 08:00:00 +08:00"
tags:
  - 自行车
  - 机械
category: Notes
---

# 自行车变速：齿比的算法

齿比等于前齿盘齿数除以飞轮齿数。

## 一个例子

前齿盘 50 齿，飞轮 25 齿，齿比是 2。
踏频 90 转时，车轮转速是 180 转每分钟。

| 前盘 | 飞轮 | 齿比 |
| --- | --- | --- |
| 34 | 28 | 1.21 |
| 50 | 25 | 2.00 |
| 50 | 11 | 4.55 |

```python
def ratio(front: int, rear: int) -> float:
    return front / rear


print(ratio(50, 25))
```

参考资料：[Sheldon Brown](https://example.com/sheldon)。

爬坡时选小齿比，下坡时选大齿比。
链条越斜，磨损越快，所以尽量避免大盘配大飞轮。
这是自行车保养里最容易被忽略的一条。
