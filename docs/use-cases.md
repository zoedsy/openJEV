# Example gallery / 示例画廊

[English](#english) · [简体中文](#zh-cn) · [Project README](../README.md) · [项目说明](../README.zh-CN.md)

<a id="english"></a>

## English

openJEV is useful when you can define a small set of outcomes, an ordered rubric, or a proposition to check against supplied text. The output is a reviewable category, score or signal. A model response does not establish facts missing from its input.

Start the local service, then open the **[example gallery](http://127.0.0.1:8766/?view=examples)**. Each card displays both English and Chinese titles. Descriptions, categories and usage notes follow the **English / 简体中文** selector. Choose a card to load its context and questions into the playground, inspect them, then run the model. The first five examples also appear as main-page shortcuts.

The gallery contains 12 entirely fictional, general-purpose examples: five existing scenarios plus seven additions. They contain no real customer records or personal work content, and no prefilled model answers. Changing the interface language does not overwrite custom input or a completed result. These are workflow demonstrations, not a model-quality benchmark.

### Twelve examples you can load

The links below open your locally running playground on port 8766. The visible refund example retains the stable ID `chinese`.

| Example / 示例 | What it asks | What stays unknown |
| --- | --- | --- |
| [Support ticket / 客户工单](http://127.0.0.1:8766/?example=support) | Route a stated problem, score expressed frustration, and flag a stated urgent deadline. | It cannot verify a real outage, find its cause, or promise a repair time. |
| [Refund request / 退款申请](http://127.0.0.1:8766/?example=chinese) | Identify refund intent, expressed satisfaction and a reported product fault. | A reported fault is not an inspected defect. Eligibility requires the applicable policy and evidence; no refund is approved. |
| [Product review / 产品评价](http://127.0.0.1:8766/?example=review) | Classify the review's sentiment, score satisfaction and detect an explicit recommendation. | One comment does not establish general product quality or other buyers' preferences. |
| [Order facts / 订单事实](http://127.0.0.1:8766/?example=facts) | Check what an order record says about delivery and location, and whether a preference is explicitly recorded. | An unrecorded preference remains unknown. Lack of evidence that someone likes a color does not prove dislike. |
| [Product listing / 商品信息检查](http://127.0.0.1:8766/?example=product_quality) | Compare conflicting capacity descriptions and check which required listing details are supplied. | The text does not reveal the true physical capacity or missing care instructions. Use ordinary code for exact counts and unit arithmetic when possible. |
| [Feedback triage / 反馈分类](http://127.0.0.1:8766/?example=feedback) | Distinguish a feature request from a bug or usage question, score the stated workflow impact, and check whether checkout is explicitly working. | It cannot infer how many users are affected, actual usage, or business priority beyond the supplied evidence. |
| [Content routing / 内容分类](http://127.0.0.1:8766/?example=content) | Classify a notice, promotion or question; check action/location/timing completeness and whether an alternative kitchen is named. | It does not verify the text's claims, identify a real author, or publish or remove content. |
| [Request completeness / 请求材料检查](http://127.0.0.1:8766/?example=intake) | Check whether an assembly request supplies a task, location and chosen time slot; distinguish concrete details from an undecided field. | An undecided time slot is not a booking. The model cannot supply the missing appointment time or verify staff availability. |
| [Service desk routing / 服务团队分流](http://127.0.0.1:8766/?example=service) | Route a step-free-access enquiry to a defined team, score the explicit reply deadline, and identify the stated accessibility request. | The message does not establish which real entrance is suitable. Routing does not verify accessibility or assign a real team. |
| [Meeting follow-up / 会议行动跟进](http://127.0.0.1:8766/?example=meeting) | Identify the owner, completeness and explicit deadline of the first agreed action, separately from a later suggestion. | An unstated owner or due date stays unknown; an action mentioned in notes is not necessarily completed. |
| [Delivery exception / 配送异常](http://127.0.0.1:8766/?example=delivery) | Classify reported damage, score the stated partial loss, and flag the missing order reference required by the supplied checklist. | It cannot infer hidden damage, verify the shipment or decide a replacement value. It does not contact a carrier. |
| [Policy evidence / 政策证据检查](http://127.0.0.1:8766/?example=policy) | Compare a fictional request with the policy text supplied alongside it; include `insufficient_information` when evidence is missing. | Whether the item was used remains unknown. Missing facts are not proof of eligibility or ineligibility, and no refund is approved. |

These are editable presets for the same typed-decision API, not twelve separate applications or external integrations. The [ticket workspace](http://127.0.0.1:8766/tickets) is a separate batch interface: it imports CSV/JSON messages, assesses scope/category/explicit urgency, and provides pause/resume and complete exports. Its five fictional demo tickets are separate from these twelve presets. See the [workspace guide](tickets.md).

### Read the result against the evidence

- **Choice** selects from supplied options. Include an unclear or insufficient-information option when a decision may lack evidence.
- **Score** is a probability-weighted mean of your numbered levels, not a proof that a requirement was met. Separate urgency, sentiment and completeness into distinct questions.
- **Noul** is a model signal about a proposition. A value near 0 or 1 is not a verified fact, and a value near 0.5 is not a guaranteed missing-information detector.
- **Confidence** describes distribution concentration, not accuracy. Keep the original input and actual rubric next to the result for review.

Ask observable questions such as “Does the message explicitly request a refund?” rather than predicting a person's unstated intentions. Use deterministic validation for exact fields, counts, dates and arithmetic. If evidence must come from another system, obtain it through an appropriately authorized workflow before asking the model to assess it.

The examples do not send replies, approve refunds, publish content, modify orders or contact external services. Open-ended drafting uses the separate text-generation endpoint when that backend supports it; a generated explanation still does not prove a separate typed result is correct.

For evidence about performance, create representative human-labeled test cases and keep them separate from prompt development and calibration data. See the [evaluation guide](evaluation.md) and [improvement recipe](recipe.md). Neither a successful demo nor a valid response format establishes accuracy or Jev parity.

<a id="zh-cn"></a>

## 简体中文

当结果可以写成有限选项、明确的评分档位，或一个可用原文核对的命题时，可以用 openJEV 把文本转成便于复核的判断。模型返回的类别或概率不能补全输入中缺失的事实。

启动本地服务后，打开[示例画廊](http://127.0.0.1:8766/?view=examples)。每张卡片始终同时显示中英文标题；说明、分类与使用提示按 **English / 简体中文** 选择器显示。点击卡片将上下文和问题载入 Playground，检查后再运行模型。前 5 个示例也保留为主页面快捷入口。

画廊共有 **12 个纯虚构的通用场景**，包括原有 5 个和新增 7 个，不含真实客户记录或个人工作内容，也不预先填入模型答案。切换界面语言不会覆盖你自行填写的内容或已经完成的结果。它们用于体验流程，不构成模型质量评测。

### 12 个可直接载入的例子

以下链接打开运行在本机 8766 端口的 Playground。退款申请继续使用稳定 ID `chinese`。

| 示例 / Example | 可以提出的问题 | 仍需保留的未知信息 |
| --- | --- | --- |
| [客户工单 / Support ticket](http://127.0.0.1:8766/?example=support) | 根据消息分类问题、评估表达出的不满程度，识别明确的紧急时限。 | 不能证实真实故障、定位原因或承诺修复时间。 |
| [退款申请 / Refund request](http://127.0.0.1:8766/?example=chinese) | 识别退款诉求、表达出的满意度及顾客报告的商品故障。 | 报告故障不等于完成检测；退款资格还需适用规则和证据，示例不批准退款。 |
| [产品评价 / Product review](http://127.0.0.1:8766/?example=review) | 判断评价情绪、满意程度及是否明确推荐。 | 一条评价不能证明商品总体质量，也不能代表其他买家的偏好。 |
| [订单事实 / Order facts](http://127.0.0.1:8766/?example=facts) | 核对记录写明的送达状态、城市，以及是否明确记载某项偏好。 | 没有记载的偏好仍然未知；未记录喜欢某颜色不代表不喜欢。 |
| [商品信息检查 / Product listing](http://127.0.0.1:8766/?example=product_quality) | 比较容量描述是否矛盾，检查指定的商品信息是否提供。 | 不能得知真实容量，也不能编造保养说明；精确计数和单位换算优先使用普通代码。 |
| [反馈分类 / Feedback triage](http://127.0.0.1:8766/?example=feedback) | 区分功能建议、故障报告或使用提问，评估已说明的流程影响，并检查是否明确说结账正常。 | 不能推断实际使用量、受影响人数或证据之外的业务优先级。 |
| [内容分类 / Content routing](http://127.0.0.1:8766/?example=content) | 区分通知、推广或提问，检查行动、地点和适用时间是否完整，以及是否指明替代厨房。 | 不核验内容真实性、识别真实作者，也不发布或删除内容。 |
| [请求材料检查 / Request completeness](http://127.0.0.1:8766/?example=intake) | 检查安装请求中的任务、地点和时段，将具体信息与“尚未选择”的字段区分。 | 未选择的时段不等于已预约；不能补造上门时间，也不能核验人员空闲情况。 |
| [服务团队分流 / Service desk routing](http://127.0.0.1:8766/?example=service) | 按指定团队类别分流无台阶入口咨询，评估明确的回复时限，识别所述无障碍需求。 | 消息未提供真实入口的适用情况；分流不等于核验无障碍条件，也不会分配真实团队。 |
| [会议行动跟进 / Meeting follow-up](http://127.0.0.1:8766/?example=meeting) | 检查第一项已约定行动的负责人、完整度和明确时限，将其与后续建议区分。 | 没有写明的负责人或日期保持未知；提到某项行动不代表它已经完成。 |
| [配送异常 / Delivery exception](http://127.0.0.1:8766/?example=delivery) | 分类报告的损坏，评估已说明的部分损失，指出给定清单要求但尚未提供的订单编号。 | 不能推断隐藏损坏、核验货件或决定赔换金额，也不会联系承运方。 |
| [政策证据检查 / Policy evidence](http://127.0.0.1:8766/?example=policy) | 将虚构请求与一同给出的规则比较，信息缺失时保留 `insufficient_information` 选项。 | 商品是否使用仍然未知；缺失事实不能证明符合或不符合条件，也不批准退款。 |

这些都是同一类型化判断接口的可编辑预设，不是 12 个独立产品或外部集成。[客服工作台](http://127.0.0.1:8766/tickets)提供另一种批量界面：导入 CSV/JSON，判断服务范围、问题类别与明确时限，并支持暂停续跑和完整导出。它内置的 5 条虚构工单与画廊的 12 个预设相互独立。详见[工作台指南](tickets.md)。

### 对照原文理解结果

- **Choice** 从给定选项中选择。证据可能不足时，加入“不明确”或“信息不足”的类别。
- **Score** 是已编号档位的概率加权均值，不证明某个条件已经满足。紧急程度、情绪和完整度应分别提问。
- **Noul** 是模型对一个命题的信号。接近 0 或 1 不等于事实已经核实，接近 0.5 也不保证识别出了信息缺失。
- **Confidence** 表示分布集中程度，不是正确率。复核时同时查看原始输入和实际评分标准。

优先问“消息是否明确要求退款”这类能对照原文的问题，不猜测未表达的意图。精确字段、计数、日期和算术适合先用普通程序校验。若需要外部系统的事实，应先通过得到授权的流程取到证据，再交给模型判断。

示例不会发送回复、批准退款、发布内容、修改订单或联系外部服务。需要生成文字时，可使用支持该能力的后端所提供的独立文本生成接口；生成一段解释仍不能证明另一个类型化判断正确。

要评价效果，需要有代表性、人工标注的测试数据，并与提示词开发及概率校准数据分开。参见[评测指南](evaluation.md)和[改进 recipe](recipe.md)。一次成功演示或合法的响应格式都不证明准确率，也不证明达到 Jev 的效果。
