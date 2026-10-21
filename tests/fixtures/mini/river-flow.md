---
title: 河流的流量与水位
published: "2026-01-04 08:00:00 +08:00"
tags:
  - 河流
  - 水文
category: Notes
---

# 河流的流量与水位

流量等于截面积乘以平均流速，单位是立方米每秒。

## 观测方法

测站在固定断面上测量水位，再用水位流量关系曲线换算流量。

| 月份 | 水位 (m) | 流量 (m3/s) |
| --- | --- | --- |
| 一月 | 1.2 | 40 |
| 七月 | 3.8 | 310 |

```python
def discharge(area: float, speed: float) -> float:
    return area * speed
```

数据来自 [水文年鉴](https://example.com/river)。

洪水期的曲线会偏离平时，因为水面比降变大。
所以长期观测要不断校正曲线。
河流的季节变化是水文学最基本的主题。
