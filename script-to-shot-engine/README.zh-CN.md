<div align="center">

# 🎬 Script-to-Shot Engine

**[English](README.md) | 中文**

**把剧本变成可直接投喂万相 3.0（Wan 3.0）的逐镜头视频提示词**

![Version](https://img.shields.io/badge/version-5.0.1-blue)
![Model](https://img.shields.io/badge/Wan_3.0-支持-blueviolet)
![Type](https://img.shields.io/badge/Skill-black)
![Lang](https://img.shields.io/badge/提示词-中文-green)

打戏 · 对峙文戏 · 连续拆段 · 全局风格锁定 · 资产连续性

**🧠 推荐模型：Kimi K3 · ChatGPT 5.6 Terra 及以上 · Claude Opus 4.6 及以上**

</div>

---

## 这是什么

一个Skill：读取你**已有的美术资产**（人物 / 场景 / 武器 / 道具）和剧本，内部设计动作因果链，输出**逐镜头、带时间戳、可直接投喂视频模型**的提示词——你只负责复制粘贴。

```text
镜头五（4.8-5.8秒）：光圈 f/2.8（浅景深，背景明显虚化），景别 特写，货柜木板特写（close-up detail）固定拍摄（static shot）；
球棍"砰"地砸进木板，木屑飞溅，棍身短暂卡住。
```

## 🎯 两种场景模式

| | 动作模式 | 对峙模式 |
|---|---|---|
| **适用** | 打斗、追逐、枪战、玄幻、Boss 战 | 谈判、审问、摊牌、决裂等台词戏 |
| **因果链** | 发起 → 防守 → 命中 → 受力 → 恢复 | 施压 → 承受 → 泄露/反制 → 新平衡 |
| **镜头密度** | 15 秒 ≥10 镜，单镜 1–2 秒 | 15 秒 5–8 镜，单镜 2–4 秒 |
| **台词** | 点缀 | 剧本原句完整入镜；默认一句一镜，音画分离时按音频桥跨镜 |

混合场景（先文后武）可**逐段切换**两种模式。

## 📦 输出结构

```markdown
## 美术资产对照卡        ← @资产名 + 短锚点，纯剧本推断外观自动标注
## 全局风格锁定          ← 六槽位风格锁定词，全场仅一次
## 台词逐句回勾表        ← 一行一句：完整原句 + 落点 + 状态；落点为空即为漏句
## 视频生成提示词        ← 每单元：锚点清单＋人物初始位置 → 逐镜头（时长计算）→ 总计
## 生成前提醒            ← 最多三条，只写真正会翻车的事
```

- ⏱ **时间戳闭环**：每镜含起止秒、光圈 `f/2.8`（附景深描述）、**景别**——**不写焦距**（`CAM-01`：尺寸词和 mm 同时写，模型会取松的那个），视听术语中英双语
- 🔗 **连续拆段**：长戏按动作/张力结果处拆分，段间承接人物、武器、座位、血迹状态
- 🎭 **特殊风格化**：回忆、监控、幻觉等局部段落可叠加特殊风格，不污染全片锁定
- 🧷 **资产连续性**：武器持握手、倒地者位置、熄灭的光源，跨段严格追踪

## 🧪 规则分级与门禁（v3.0.0 新增）

每条规则都登记在 [`references/rule-tiers.md`](references/rule-tiers.md)，分四级并绑定判定者：

| 级别 | 判定者 | 能否阻断交付 |
|---|---|---|
| `structural_invariant` | **脚本** | ✅ 能 |
| `reviewed_invariant` | 审查者引用证据 | 需证据 |
| `craft_default` | 创作者，**说明理由即可覆盖** | ❌ |
| `taste_option` | 创作者 | ❌ **不得单独阻断** |

确定性检查是**脚本，不是散文**：

```bash
python scripts/check_units.py     --delivery 交付物.md      # 时长算式 · 装箱 · 单元格式
python scripts/check_dialogue.py --script 剧本.md --delivery 交付物.md --ledger 台账.md
python scripts/check_cast.py      --delivery 交付物.md      # 出场人物 · 锚点 · 同人声明
```

[`evaluations/gate.py`](evaluations/gate.py) 回放 `evaluations/cases/` 里的夹具，守卫不再咬人或开始误报就红。[`evaluations/selfcheck.py`](evaluations/selfcheck.py) 让技能**对照自己**体检。**脚本红了不得交付。**

> **`FMT-01` 格式守卫**：交付物既不是「单元 N」也不是旧的「### Clip NN」时，检查器**直接报错，不静默通过**。教训：旧的 timeline 检查器曾在真实交付上读到 0 个分镜，把一份漏了 6 秒的提示词判成通过——**"读不到"绝不能长得像"没问题"**。

为什么：散文清单分不清「我检查过了」和「我真的核对了」——漏掉的半句和完整的句子，看上去一模一样。

## 🚀 安装

把整个文件夹放进 skills 目录，新会话自动生效：

```bash
# Kimi Desktop
git clone https://github.com/jiayushi1-ux/script-to-shot-engine.git \
  "<daimon-share>/daimon/skills/script-to-shot-engine"

# 通用
git clone https://github.com/jiayushi1-ux/script-to-shot-engine.git \
  ~/.config/agents/skills/script-to-shot-engine
```

或直接下载 ZIP 解压到 skills 目录。使用时说「**用 script-to-shot-engine 处理这个剧本**」即可。

## 🗂 目录结构

```
├── SKILL.md              # 主入口：规则分级 · 路由 · 输出协议 · 三层门禁
├── references/           # 按需加载的规则；rule-tiers.md 登记每条规则的级别
├── scripts/              # 确定性校验器（台词覆盖、时间戳）
├── evaluations/          # gate.py + cases/ —— 回归基准（判定"没有退步"）
├── examples/             # 打戏与对峙完整示例（15s / 30s / 90s）
└── .agents/notes/        # 决策笔记（implemented / rejected / simplification）
```

---

<div align="center">
当前版本 <b>v5.0.1</b> · 只做万相 3.0 —— 一套渲染器、一套规则
</div>
