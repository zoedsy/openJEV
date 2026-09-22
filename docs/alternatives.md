# 已有开源方案调查

调查日期：2026-09-20。优先阅读项目自己的源码、模型卡和运行说明；下表是工程选型判断，不是统一硬件上的实测排名。

| 项目 | 开源内容 | 与 Jev 风格的关系 | 在 OpenJev 中的定位 |
|---|---|---|---|
| [Kev](https://github.com/jaredpalmer/kev) | Apache-2.0 代码；LoRA / readout 权重；训练与评测脚本 | 已有 Choice / Score / Noul API；共享 state、隔离问题分支、单次 prefill、pointer readout | 最直接的完整后端候选；已提供本地 HTTP 适配器 |
| [SemIf](https://github.com/TheoLeeCJ/SemIf) | MIT 代码、评分与基准工具；使用上游开放权重 | 直接读取选项分数，有 shared-state 路线及 Apple Silicon MLX 支持；原名 OpenJev | 适合研究 Mac 上的共享前缀推理；本项目未集成 |
| [NanoJev](https://github.com/TianyuCodings/NanoJev) | MIT 代码、0.6B 权重、数据与端到端训练流程 | Qwen3-0.6B 加决策头；Choice / Boolean / Score；展示集中于迷宫和 Snake | 适合研究如何训练决策头，不把游戏结果当通用语义能力 |
| [GLiClass](https://github.com/Knowledgator/GLiClass) | Apache-2.0 代码、权重和训练入口 | 零样本 / 少样本分类，多标签可一起打分；不是原生 Jev API | 通用分类底座候选；需自行映射三种原语与校准 |
| [multilingual MiniLM NLI](https://huggingface.co/MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli) | MIT 权重、模型卡、标准 NLI 推理 / ONNX 转换 | 小型自然语言推断模型；可派生分类 / 评分 / 命题支持程度 | 轻量默认后端，不需要聊天模型服务 |

## 选择理由

**在普通笔记本上试玩**：选择 MiniLM。模型较小，CPU 可运行，中英文模型卡齐全，标准推理依赖，使用固定版本的 INT8 ONNX 转换版（约 107 MB），不执行远程模型代码。

**更完整地研究 Jev 风格模型**：优先 Kev。它已经实现了最关键的模型结构和接口形状，可直接接入 OpenJev。它的作者也公开了 out-of-domain 能力差距、选项顺序敏感性、校准边界及未达标的发布门槛，这些比只展示几个成功样例更有参考价值。Kev 0.5B 便于在普通笔记本尝试；更大模型需要按其文档确认内存与运行环境，本仓库没有验证这些权重。

**更接近开源训练路线**：NanoJev 提供了决策头、动态候选、完整问题分布损失、CE/Brier 对照及配套数据；Kev 则提供 LoRA + pointer head 和冻结评测套件。两者都是独立复现，不能称作 TypeSafe 的原始训练方法。

**多语言分类优化**：GLiClass 的 [multilang 系列](https://docs.knowledgator.com/docs/models/text-classification/gliclass/) 有中文训练数据和跨语言分类支持。目前 main 依赖 Transformers 5，而默认 NLI 后端使用 Transformers 4，直接合并环境需要先做兼容性验证。

## 关于名称与实际效果

社区已有使用过 OpenJev 名称的其他项目，尤其是后来更名为 SemIf 的项目。本仓库 `zoedsy/openJEV` 是独立实验，不是它们的官方分支，也不暗示拥有 Jev 的原始模型。

软最大值归一化、类型安全、输出 schema 正确，均不能单独证明概率经过校准。上游自报 benchmark 也不是本项目的实测。后续若训练：

1. 固定目标任务与标注规则，按来源划分训练 / 校准 / 测试数据。
2. 基于现有开放骨干训练分类或 pointer head，先验证监督式 CE / Brier 基线。
3. 检查问题隔离、选项顺序、域外样本、置信错误和分布偏移。
4. 单独做温度或其他校准，报告 accuracy、NLL、Brier、ECE 和拒答覆盖率。
5. 测试集只用于最终评估，不用于挑参数。

## 直接参考的上游文件

- [Kev README、训练方法及限制](https://github.com/jaredpalmer/kev/blob/main/README.md)
- [Kev API 映射](https://github.com/jaredpalmer/kev/blob/main/kev/api.py)
- [Kev 本地服务](https://github.com/jaredpalmer/kev/blob/main/kev/serve.py)
- [Kev 权重](https://huggingface.co/jaredpalmer/kev-0.5b)
- [SemIf 源码和 MLX 说明](https://github.com/TheoLeeCJ/SemIf)
- [NanoJev 源码、数据与训练说明](https://github.com/TianyuCodings/NanoJev)
- [GLiClass 官方仓库](https://github.com/Knowledgator/GLiClass)
- [GLiClass 多语言 mini 模型卡](https://huggingface.co/knowledgator/gliclass-multilang-mini)

本轮没有复制上述项目源码；Kev 通过文档化 HTTP API 连接。模型和依赖通过各自官方分发渠道下载。
