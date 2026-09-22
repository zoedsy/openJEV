'use strict';
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const paths = {
  sliders: '<path d="M4 7h16M4 17h16M9 4v6M15 14v6"/>',
  history: '<path d="M3 10a9 9 0 1 1 2 8M3 4v6h6m3-3v5l3 2"/>',
  book: '<path d="M12 5v15M3 4c4-1 7-1 9 1 2-2 5-2 9-1v15c-4-1-7-1-9 1-2-2-5-2-9-1z"/>',
  github: '<path d="M9 19c-4 1-4-2-6-2m12 5v-4c0-1-.3-2-1-2 4-.5 7-2 7-6 0-2-1-3-2-4 .3-1 .3-3 0-4-2 0-3 1-4 2a14 14 0 0 0-6 0C8 3 7 2 5 2c-.3 1-.3 3 0 4-1 1-2 2-2 4 0 4 3 5.5 7 6-.7 0-1 1-1 2v4"/>',
  code: '<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v2"/>',
  cpu: '<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 1v4m6-4v4M9 19v4m6-4v4M1 9h4m-4 6h4M19 9h4m-4 6h4"/><rect x="9" y="9" width="6" height="6" rx="1"/>',
  play: '<path d="m8 5 11 7-11 7z"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/>',
  copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
  edit: '<path d="m15 4 5 5M4 20l5-1L21 7l-5-5L4 14z"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
  ticket: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 10h10M7 14h6"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c5 6 5 12 0 18-5-6-5-12 0-18"/>',
  star: '<path d="m12 3 3 6 6 1-4 5 1 6-6-3-6 3 1-6-4-5 6-1z"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  branches: '<circle cx="5" cy="12" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><path d="M7 12h3c4 0 0-7 7-7m-7 7c4 0 0 7 7 7"/>',
  chart: '<path d="M5 20V10m7 10V4m7 16v-6"/>',
};
const icon = (name) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.info}</svg>`;
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const serialize = (value) => typeof value === 'string' ? value : JSON.stringify(value, null, 2);
const clone = (value) => JSON.parse(JSON.stringify(value));
const clamp = (n) => Math.max(0, Math.min(1, Number(n) || 0));
const percent = (n) => `${(clamp(n) * 100).toFixed(1)}%`;
const latency = (ms) => ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`;
// Interface text is translated separately from input and model output.
const TRANSLATIONS = {
  "openJEV — A local, open-source decision playground. Choice, Score, Noul.": "openJEV — 本地运行的开源 AI 决策实验室。Choice、Score、Noul。",
  "openJEV home": "openJEV 首页",
  "Local workspace": "本地工作空间",
  "Main navigation": "主导航",
  "Ticket triage": "工单分流",
  "Run history": "运行记录",
  "Guide": "使用指南",
  "Let code manage the workflow,": "让代码掌控流程，",
  "let models answer specific questions.": "让模型回答具体问题。",
  "Loading model": "模型加载中",
  "Checking inference location": "正在确认推理位置",
  "GitHub repository": "GitHub 仓库",
  "Give the model context and get decisions your code can use directly.": "给模型一份上下文，让每一个判断都成为代码能直接使用的答案。",
  "Get code": "获取代码",
  "Start with an example": "从一个场景开始",
  "or edit the inputs below": "或自由编辑下方内容",
  "Context": "上下文",
  "Enter context": "输入上下文",
  "Paste text or describe what you want to evaluate…": "粘贴一段文本，或描述你想评估的内容…",
  "Processed locally": "仅在本机处理",
  "Define questions": "定义问题",
  "Add question": "添加问题",
  "Run evaluation": "运行评估",
  "Questions are evaluated independently and batched in one request.": "所有问题独立评估，同一请求内批量推理。",
  "Decisions": "判断结果",
  "Download result JSON": "下载结果 JSON",
  "Visual": "可视化",
  "JSON response": "JSON 响应",
  "Copy result": "复制结果",
  "Copy": "复制",
  "Uncalibrated estimates from an open NLI model. Confidence measures concentration, not accuracy.": "开源 NLI 模型的未校准估计。Confidence 表示分布集中程度，不等于正确率。",
  "How it works ↗": "了解计算方式 ↗",
  "Every experiment, saved.": "每一次尝试，都有记录。",
  "The latest 20 runs stay in this browser. Select one to reopen it.": "最近 20 次运行保存在当前浏览器中，点击即可重新打开。",
  "Clear history": "清空记录",
  "Make decisions a building block.": "让判断，成为一种基本能力。",
  "openJEV is an independent local decision tool inspired by Jev’s public interface.": "openJEV 是独立实现的本地决策工具，灵感来自 Jev 的公开接口。",
  "Choose from a finite set": "从有限选项里做选择",
  "Describe each option clearly. MiniLM scores how the context supports each description; DiffusionGemma reads answer-label probabilities. The highest-probability option is returned.": "把每个选项写成明确描述。MiniLM 判断上下文对每个描述的支持程度；DiffusionGemma 直接读取答案标签的概率。返回概率最高的选项。",
  "Score against your own scale": "在你定义的尺度上评分",
  "Define 2–10 ordered levels, indexed from zero. The result is a probability-weighted mean: a three-level scale ranges from 0 to 2 and can return decimals.": "定义 2–10 个有顺序的档位，从 0 开始编号。返回概率加权平均，所以三档评分的范围是 0–2，可以出现小数。",
  "Measure support for a statement": "衡量一个命题的支持程度",
  "Use a statement such as “The customer requests a refund.” Support approaches 1 and contradiction approaches 0. MiniLM assigns half of neutral probability to support; DiffusionGemma’s 0.5 means the two label probabilities are similar. Optional true / false criteria can define the alternatives.": "最好写成陈述句，例如「客户要求退款」。支持接近 1，矛盾接近 0，MiniLM 的中立判断会向 0.5 分配；DiffusionGemma 的 0.5 表示两种标签概率接近。也可在 JSON 中提供 true / false 描述。",
  "See how concentrated the answer is": "知道模型有多犹豫",
  "For Choice and Score, normalized entropy measures concentration. A uniform distribution gives 0; all probability on one option gives 1. This is openJEV’s published formula.": "只用于 Choice 和 Score。用归一化熵衡量分布的集中程度；均匀分布为 0，单点分布为 1。这是 openJEV 的公开公式。",
  "What works, and what remains": "能复现什么，以及还差什么",
  "Supports three primitives, structured state, questions and criteria, batched typed decisions, and": "支持三种原语、结构化上下文、结构化问题与 criteria、批量类型化评估，以及",
  ". The default backend is MIT-licensed MiniLM NLI. DiffusionGemma uses open weights and can run on your GPU server. The page identifies the active model and inference location.": "。默认后端是 MIT 授权的 MiniLM NLI；DiffusionGemma 使用开放权重，可以部署到自己的 GPU 服务器。页面会标明当前模型及处理位置。",
  "This is not TypeSafe’s official Jev and does not include its weights or training recipe. Classifiers suit short-text semantic judgments; complex reasoning, precise counting, and cross-field calculations remain limitations. Probabilities are not calibrated to your task, and more questions still add work.": "这不是 TypeSafe 官方 Jev，也不包含它的权重或训练配方。分类器适合短文本的语义判断，不擅长复杂推理、精确计数或跨字段计算。概率未经业务数据校准；增加问题仍会增加计算量。",
  "MiniLM allows 512 tokens per state/question/option pair. DiffusionGemma has an 8192-token service window, including its template. Oversized inputs fail explicitly instead of being silently truncated. A request allows 32 questions and 256 candidates; DiffusionGemma allows 128 options per Choice. Its questions share an answer canvas and may affect one another. Run history is stored in this browser and can be cleared.": "MiniLM 每个「上下文 + 问题 + 单个选项」最多 512 tokens。DiffusionGemma 的服务窗口为 8192 tokens（含内部提示模板）。超限会明确报错，不会悄悄截断。一次最多 32 个问题、256 个候选；DiffusionGemma 每个 Choice 最多 128 项，问题共享答案画布，可能相互影响。运行记录存在浏览器 localStorage，可随时清空。",
  "TypeSafe API docs ↗": "TypeSafe API 文档 ↗",
  "Open model and model card ↗": "开源模型与模型卡 ↗",
  "Edit question": "编辑问题",
  "Close": "关闭",
  "Question ID": "问题 ID",
  "e.g. department": "例如 department",
  "Question type": "问题类型",
  "Choice · Pick an option": "Choice · 选择一个选项",
  "Score · Rate on a scale": "Score · 在尺度上评分",
  "Noul · Evaluate a statement": "Noul · 判断一个命题",
  "Question / statement": "问题 / 命题",
  "Make the question specific, independent, and easy to judge": "让问题具体、独立且容易判断",
  "Option definitions": "选项定义",
  "Cancel": "取消",
  "Save question": "保存问题",
  "Use this decision in your code.": "把这次判断，接进你的代码。",
  "Copy code": "复制代码",
  "Requests go to your local service. The Python example uses only the standard library.": "请求发送到本地服务。Python 示例只使用标准库。",
  "Personal workspace": "个人工作空间",
  "WORKSPACE": "工作空间",
  "Workspace": "工作空间",
  "Playground": "实验台",
  "Open models.": "开放模型。",
  "Real decisions.": "真实判断。",
  "Inspired by TypeSafe": "灵感来自 TypeSafe",
  "MIT licensed": "MIT 授权",
  "THE LOCAL DECISION LAB": "本地决策实验室",
  "Small questions.": "具体问题，",
  "Clear decisions.": "清晰判断。",
  "Text": "文本",
  "Results": "结果",
  "LOCAL BY DEFAULT. OPEN BY DESIGN.": "本地优先，开放设计。",
  "YOUR EXPERIMENTS": "你的实验记录",
  "UNDER THE HOOD": "工作原理",
  "BUILD A QUESTION": "定义问题",
  "FROM PLAYGROUND TO CODE": "从实验台接入代码",
  "Language": "语言",
  "Enter some context before running.": "请先输入要评估的上下文。",
  "The context is not valid JSON. Check quotes, commas, and brackets.": "上下文不是有效的 JSON，请检查引号、逗号和括号。",
  "State must be a string, object, or array.": "State 必须是字符串、对象或数组。",
  "Add at least one question before running.": "至少添加一个问题后再运行。",
  "{count} characters": "{count} 个字符",
  "Edit {id}": "编辑 {id}",
  "Delete {id}": "删除 {id}",
  "Delete question": "删除问题",
  "Turn a question into a usable decision.": "让问题成为可直接使用的判断。",
  "Enter context and define what you want to know.": "输入上下文，定义你关心的问题。",
  "Run to see decisions and full probability distributions here.": "运行后，在这里查看判断与完整概率分布。",
  "Click Run evaluation, or press": "点击「运行评估」，或按",
  "The model is evaluating your questions…": "模型正在评估每一个问题…",
  "The first request may take a few seconds.": "第一次推理可能需要几秒钟。",
  "Inputs changed. These are the previous results; run again to update them.": "输入已修改 · 下方为上一次运行结果，请重新评估。",
  "Model service {time} · total time": "模型服务 {time} · 总耗时",
  "Request time": "请求耗时",
  "Typed questions": "类型化问题",
  "Input tokens (including repetition)": "输入 tokens（含重复）",
  "Concentration, not accuracy": "分布集中程度，不等于准确率",
  "confidence": "置信度",
  "Statement support": "命题支持程度",
  "0 · Unsupported": "0 · 不支持",
  "0.5 · Uncertain": "0.5 · 不确定",
  "Supported · 1": "支持 · 1",
  "selected": "已选择",
  "{count} questions scored": "已评估 {count} 个问题",
  "{count} candidate evaluations": "{count} 次候选评估",
  "no text generation": "不生成文本",
  "Request failed. Check the input and local service.": "请求失败，请检查输入和本地服务。",
  "The model is not ready. Wait for download or loading to finish.": "模型尚未就绪，请等待下载或加载完成。",
  "Evaluating": "评估中",
  "Browser storage is full. This result was not saved to history.": "浏览器存储已满，本次结果未保存到运行记录。",
  "Waited 120 seconds and stopped waiting. The server may still be processing. Retry manually later.": "等待已超过 120 秒，已停止等待；服务器可能仍在处理。请稍后手动重试。",
  "Cannot connect to the local service. Check that openJEV is running.": "连接本地服务失败，请确认 openJEV 正在运行。",
  "Describe when option A applies": "描述选项 A 对应的情况",
  "Describe when option B applies": "描述选项 B 对应的情况",
  "Describe the low level": "描述低档位的情况",
  "Describe the high level": "描述高档位的情况",
  "Evidence supporting the statement": "支持该命题的情况",
  "Evidence contradicting the statement": "不支持该命题的情况",
  "Ordered levels": "有序档位",
  "Criteria (optional)": "判断标准（可选）",
  "Enter a JSON object with 2–255 options. Keys are return values; values describe each option. null uses the key alone.": "填写 JSON 对象，2–255 个选项。键是返回值，值是选项描述；null 表示只使用键名。",
  "Enter a JSON array with 2–10 levels, ordered low to high and indexed from 0.": "填写 JSON 数组，从低到高定义 2–10 个档位，编号从 0 开始。",
  "Leave blank to judge the statement directly, or provide a JSON object containing true and false. Statements generally suit NLI models.": "留空即可直接判断命题；或填写包含 true、false 的 JSON 对象。陈述句通常更适合 NLI 模型。",
  "Add a question": "添加一个问题",
  "Enter a question or statement.": "请填写问题或命题。",
  "The structured question is not valid JSON.": "结构化问题不是有效 JSON。",
  "Enter a question ID.": "请填写问题 ID。",
  "That question ID already exists. Choose another name.": "这个问题 ID 已存在，请使用不同的名称。",
  "Options or levels are not valid JSON.": "选项或档位不是有效的 JSON。",
  "Choice needs a JSON object with 2–255 options.": "Choice 需要包含 2–255 个选项的 JSON 对象。",
  "Score needs a JSON array with 2–10 levels.": "Score 需要包含 2–10 个档位的 JSON 数组。",
  "Noul criteria need both true and false. Leave blank if criteria are unnecessary.": "Noul 标准需要同时包含 true 和 false；不需要标准时请留空。",
  "{count} questions": "{count} 个问题",
  "No runs yet. Start your first evaluation in the Playground.": "还没有运行记录。去实验台开始第一次评估吧。",
  "Copied to clipboard.": "已复制到剪贴板。",
  "Clipboard access was blocked. Select and copy the text manually.": "浏览器不允许复制，请手动选择内容。",
  "Result JSON downloaded.": "结果 JSON 已下载。",
  "Clear all run history saved by this app in this browser?": "清空此应用在当前浏览器保存的所有运行记录？",
  "Run history cleared.": "运行记录已清空。",
  "Fix the JSON before switching to text.": "请先修正 JSON，再切换为文本。",
  "The API key stays in this page’s memory only.": "API key 仅保存在当前页面内存中。",
  "Could not load examples. Start the service and refresh this page.": "无法加载示例，请确认服务已启动后刷新页面。",
  "Previous-version local demo history was cleared for this update.": "本次更新已清理旧版本的本地演示运行记录。",
  "The browser blocked old-history cleanup. Previous-version records are not loaded.": "浏览器阻止了旧记录清理；此版本不会加载旧演示记录。",
  "Processed on a remote GPU": "在远程 GPU 上处理",
  "GPU service via a local connection": "通过本机连接访问 GPU 服务",
  "Remote GPU · authenticated connection": "远程 GPU · 已认证连接",
  "GPU service · local connection / SSH tunnel": "GPU 服务 · 本机连接 / SSH 隧道",
  "Inference stays on this machine": "推理在本机完成 · 数据不上传",
  "Questions share context and return structured decisions. Questions may affect one another.": "多个问题共享上下文，一次返回结构化判断。问题之间可能相互影响。",
  "DiffusionGemma label probabilities. Confidence measures concentration, not correctness; probabilities are not task-calibrated.": "DiffusionGemma 的标签概率。Confidence 表示分布集中程度，不等于正确率；概率未经业务数据校准。",
  "Results come from local Kev. Confidence uses its formula; calibration outside its training distribution is not established.": "结果来自本机 Kev。Confidence 使用 Kev 的公式；它的概率在训练分布以外不保证经过校准。",
  "GPU model ready": "GPU 模型已就绪",
  "Local model ready": "本地模型已就绪",
  "Downloading / loading model": "模型下载或加载中",
  "Model loading failed": "模型加载失败",
  "Connecting to service": "服务连接中",
  "Downloading / loading the open model (about 107 MB on first use). You can edit inputs while waiting.": "正在下载或加载开源模型，首次需要约 107 MB 权重；等待时可以编辑输入。",
  "Connecting to the remote GPU service. You can edit inputs while waiting.": "正在连接远程 GPU 模型服务，等待时可以编辑输入。",
  "Connecting to the local model service. You can edit inputs while waiting.": "正在连接本机模型服务，等待时可以编辑输入。",
  "See the server log.": "请查看服务端日志。",
  "Check that the GPU service is ready.": "请检查 GPU 服务是否就绪。",
  "This service requires an API key": "此服务需要 API key",
  "Local API key": "本地 API key",
  "Connect": "连接",
  "Service offline": "服务未连接",
  "Cannot reach the local service. Start python -m openjev serve from the project directory. This page will reconnect automatically.": "无法连接本地服务。请在项目目录运行 python -m openjev serve，页面会自动重连。",
  "Examples": "案例画廊",
  "Browse all examples": "浏览全部案例",
  "EVERYDAY DECISIONS": "日常场景，具体判断",
  "Find a scenario.": "挑选一个场景，",
  "Make it yours.": "改成你的需求。",
  "Explore everyday tasks in English and Chinese. Load an example, review its questions, and run it when you are ready.": "用中文或英文体验日常任务。载入案例、查看问题，再按需运行。",
  "Back to Playground": "返回实验台",
  "Every example includes both languages. Your language selection controls the inputs and questions you load.": "每个案例都提供中英两种语言，载入的上下文与问题会使用你当前选择的语言。",
  "Search examples": "搜索案例",
  "Search in English or Chinese": "用英文或中文搜索",
  "Category": "分类",
  "All categories": "全部分类",
  "Clear filters": "清除筛选",
  "Fictional examples · ready to edit": "虚构场景 · 可自由编辑",
  "No examples match this search.": "没有符合条件的案例。",
  "Try another keyword or clear the filters.": "换一个关键词，或清除筛选条件。",
  "{count} of {total} examples": "共 {total} 个案例，显示 {count} 个",
  "Explore": "练习重点",
  "Load example": "载入案例",
  "Load {name}": "载入 {name}",
  "Loaded": "已载入",
  "Other": "其他",
  "Example loaded. Review the inputs, then run when ready.": "案例已载入。请查看上下文与问题，再按需运行。"
};
let locale = 'en';
try { locale = localStorage.getItem('openjev.locale') === 'zh' ? 'zh' : 'en'; } catch {}
const t = (text, values={}) => (locale === 'zh' ? TRANSLATIONS[text] || text : text).replace(/\{(\w+)\}/g, (_,key) => String(values[key] ?? `{${key}}`));
const canonicalText = text => Object.entries(TRANSLATIONS).find(([,zh]) => zh === text)?.[0] || text;
const staticText = [], staticAttributes = [];
const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
while (walker.nextNode()) {
  const node = walker.currentNode, text = node.textContent.trim();
  if (!node.parentElement.closest('script,style,textarea') && Object.hasOwn(TRANSLATIONS,text)) staticText.push({node,text,prefix:node.textContent.match(/^\s*/)[0],suffix:node.textContent.match(/\s*$/)[0]});
}
$$('[aria-label],[title],[placeholder],meta[name="description"]').forEach(element => {
  for (const attr of ['aria-label','title','placeholder','content']) {
    const text=element.getAttribute(attr); if (text && Object.hasOwn(TRANSLATIONS,text)) staticAttributes.push({element,attr,text});
  }
});
let examples = [], questions = {}, stateMode = 'text', activePreset = null, activeView = 'playground';
let exampleSearch = '', exampleCategory = '';
const QUICK_EXAMPLES = ['support','chinese','review','facts','product_quality'];
let result = null, resultRequest = null, pending = false, outputMode = 'visual';
let status = null, statusFailed = false, editingId = null, codeMode = 'curl', apiKey = '';
let runs = [], toastTimer, lastError = '', lastToast = '', legacyHistoryCleared = false, legacyCleanupFailed = false;
const HISTORY_KEY = 'openjev.runs.v2';
try {
  legacyHistoryCleared = localStorage.getItem('openjev.runs.v1') !== null;
  localStorage.removeItem('openjev.runs.v1');
} catch { legacyCleanupFailed = true; }
try { const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); runs = Array.isArray(saved) ? saved.filter(r => r.request && r.result?.answers).slice(0,20) : []; } catch { runs = []; }

function toast(message) { lastToast=canonicalText(message); $('#toast').textContent=t(lastToast); $('#toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>{$('#toast').hidden=true;},4000); }
function setView(view) {
  activeView=view; $$('.page-view').forEach(el=>{el.hidden=el.id!==`${view}-view`;});
  $$('.nav-item').forEach(el=>el.classList.toggle('active',el.dataset.view===view));
  $('#breadcrumb-view').textContent=t({playground:'Playground',examples:'Examples',history:'Run history',guide:'Guide'}[view]);
  if (view==='history') renderHistory();
  if (view==='examples') renderExampleGallery();
  const url=new URL(location.href);if(view==='playground')url.searchParams.delete('view');else url.searchParams.set('view',view);window.history.replaceState(null,'',url);
  window.scrollTo({top:0,behavior:'smooth'});
}
function getRequest() {
  const text=$('#state-input').value; if(!text.trim()) throw new Error(t('Enter some context before running.'));
  let state=text;
  if(stateMode==='json') { try{state=JSON.parse(text);}catch{throw new Error(t('The context is not valid JSON. Check quotes, commas, and brackets.'));} if(state===null||!['string','object'].includes(typeof state)) throw new Error(t('State must be a string, object, or array.')); }
  if(!Object.keys(questions).length) throw new Error(t('Add at least one question before running.'));
  return {state,model:'openjev-local',questions:clone(questions)};
}
function isStale(){if(!resultRequest)return false;try{return JSON.stringify(getRequest())!==JSON.stringify(resultRequest);}catch{return true;}}
function countChars(){$('#char-count').textContent=t('{count} characters',{count:[...$('#state-input').value].length.toLocaleString(locale==='zh'?'zh-CN':'en-US')});}
function markEdited(){activePreset=null;renderPresets();countChars();renderOutput();}
function setState(value){stateMode=typeof value==='string'?'text':'json';$('#state-input').value=serialize(value);renderStateMode();countChars();}
function renderStateMode(){$$('#state-modes button').forEach(b=>b.classList.toggle('selected',b.dataset.mode===stateMode));$('#state-input').classList.toggle('json',stateMode==='json');}
const exampleValue=(example,key)=>locale==='zh'?(example[`${key}_zh`]??example[key]):example[key];
function loadExample(id){const sample=examples.find(e=>e.id===id);if(!sample)return;questions=clone(exampleValue(sample,'questions'));setState(exampleValue(sample,'state'));activePreset=id;renderQuestions();renderPresets();renderExampleGallery();renderOutput();hideError();}
function renderPresets(){
  const quick=QUICK_EXAMPLES.map(id=>examples.find(example=>example.id===id)).filter(Boolean);
  $('#presets').innerHTML=quick.map(e=>`<button class="preset ${e.id===activePreset?'active':''}" data-preset="${esc(e.id)}" title="${esc(exampleValue(e,'description'))}">${icon(e.icon||'ticket')}${esc(exampleValue(e,'name'))}</button>`).join('');
  $('#example-total').textContent=examples.length;
}
function renderExampleGallery(){
  const categories=new Map();for(const example of examples)categories.set(example.category||'Other',exampleValue(example,'category')||t('Other'));
  if(exampleCategory&&!categories.has(exampleCategory))exampleCategory='';
  $('#example-category').innerHTML=`<option value="">${t('All categories')}</option>`+[...categories].map(([value,label])=>`<option value="${esc(value)}">${esc(label)}</option>`).join('');
  $('#example-category').value=exampleCategory;
  const query=exampleSearch.trim().toLocaleLowerCase();
  const filtered=examples.filter(example=>{
    if(exampleCategory&&(example.category||'Other')!==exampleCategory)return false;
    return !query||['name','name_zh','description','description_zh','category','category_zh','learning','learning_zh'].map(key=>example[key]||'').join(' ').toLocaleLowerCase().includes(query);
  });
  $('#example-count').textContent=t('{count} of {total} examples',{count:filtered.length,total:examples.length});
  $('#clear-example-filters').disabled=!exampleSearch&&!exampleCategory;
  $('#example-empty').hidden=filtered.length!==0;
  $('#example-gallery').innerHTML=filtered.map(example=>{
    const primary=locale==='zh'?example.name_zh||example.name:example.name;
    const secondary=locale==='zh'?example.name:example.name_zh||example.name;
    const types=[...new Set(Object.values(example.questions).map(question=>question.type))];
    const selected=example.id===activePreset;
    return `<article class="example-card ${selected?'example-card-loaded':''}" role="listitem" data-example-id="${esc(example.id)}"><div class="example-card-top"><span class="example-card-icon">${icon(example.icon||'ticket')}</span><span class="example-category-chip">${esc(exampleValue(example,'category')||t('Other'))}</span>${selected?`<span class="example-loaded">${t('Loaded')}</span>`:''}</div><h2 class="example-card-title"><span lang="${locale==='zh'?'zh-CN':'en'}">${esc(primary)}</span><span class="example-title-secondary" lang="${locale==='zh'?'en':'zh-CN'}">${esc(secondary)}</span></h2><p class="example-description">${esc(exampleValue(example,'description'))}</p><div class="example-learning"><strong>${t('Explore')}</strong><p>${esc(exampleValue(example,'learning')||exampleValue(example,'description'))}</p></div><div class="example-card-bottom"><div class="example-types">${types.map(type=>`<span class="type-badge ${esc(type)}">${esc(type[0].toUpperCase()+type.slice(1))}</span>`).join('')}</div><button class="example-load" data-load-example="${esc(example.id)}" aria-label="${esc(t('Load {name}',{name:primary}))}">${t('Load example')}<span aria-hidden="true">↗</span></button></div></article>`;
  }).join('');
}
function selectExample(id){
  if(!examples.some(example=>example.id===id))return;
  loadExample(id);setView('playground');const url=new URL(location.href);url.searchParams.set('example',id);window.history.replaceState(null,'',url);
  toast(t('Example loaded. Review the inputs, then run when ready.'));
}

function renderQuestions(){
  const entries=Object.entries(questions);$('#question-count').textContent=entries.length;
  $('#questions').innerHTML=entries.map(([key,q])=>{
    let chips='';if(q.type==='choice')chips=Object.entries(q.criteria).map(([k,v])=>`<span class="option-chip" title="${esc(serialize(v))}">${esc(k)}</span>`).join('');
    if(q.type==='score')chips=q.criteria.map((v,i)=>`<span class="option-chip score-chip" title="${esc(serialize(v))}">${i} · ${esc(serialize(v))}</span>`).join('');
    return `<article class="question-card ${q.type==='noul'?'noul-card':''}"><div class="question-top"><span class="type-badge ${q.type}">${q.type[0].toUpperCase()+q.type.slice(1)}</span><span class="question-id">${esc(key)}</span><div class="question-actions"><button class="icon-button" data-edit="${esc(key)}" aria-label="${esc(t('Edit {id}',{id:key}))}" title="${esc(t('Edit question'))}">${icon('edit')}</button><button class="icon-button" data-delete="${esc(key)}" aria-label="${esc(t('Delete {id}',{id:key}))}" title="${esc(t('Delete question'))}">${icon('trash')}</button></div></div><p class="question-instruction" title="${esc(serialize(q.instructions))}">${esc(serialize(q.instructions))}</p>${chips?`<div class="question-options">${chips}</div>`:''}</article>`;
  }).join('');$('#add-question').disabled=entries.length>=32;
}
function emptyOutput(){return `<div class="empty-output"><div class="empty-art"><div class="empty-grid"></div><div class="empty-node one">${icon('branches')}<span>Choice</span><span class="type-badge choice">A</span></div><div class="empty-node two">${icon('chart')}<span>Score</span><span class="type-badge score">1.8</span></div><div class="empty-node three">${icon('check')}<span>Noul</span><span class="type-badge noul">0.9</span></div></div><h3>${t('Turn a question into a usable decision.')}</h3><p>${t('Enter context and define what you want to know.')}<br>${t('Run to see decisions and full probability distributions here.')}</p><div class="key-hint">${t('Click Run evaluation, or press')} <kbd>⌘ ↵</kbd></div></div>`;}
function renderOutput(){
  $('#result-live').hidden=!result||pending||isStale();$('#copy-result').disabled=!result||pending;$('#download-result').disabled=!result||pending;
  if(pending){$('#output-content').innerHTML=`<div class="loading-output"><span class="spinner"></span><span>${t('The model is evaluating your questions…')}</span><small>${t('The first request may take a few seconds.')}</small></div>`;return;}
  if(!result){$('#output-content').innerHTML=emptyOutput();return;}
  const stale=isStale()?`<div class="stale-banner">${t('Inputs changed. These are the previous results; run again to update them.')}</div>`:'';
  if(outputMode==='json'){$('#output-content').innerHTML=`${stale}<pre class="raw-json">${esc(JSON.stringify(result,null,2))}</pre>`;return;}
  const meta=result.meta||{},timingLabel=Number.isFinite(meta.inference_ms)?t('Model service {time} · total time',{time:latency(meta.inference_ms)}):t('Request time');
  const summary=`<div class="result-summary"><div><strong>${esc(latency(meta.latency_ms||0))}</strong><small>${esc(timingLabel)}</small></div><div><strong>${Object.keys(result.answers).length}</strong><small>${t('Typed questions')}</small></div><div><strong>${Number(result.usage?.input_tokens||0).toLocaleString()}</strong><small>${t('Input tokens (including repetition)')}</small></div></div>`;
  const cards=Object.entries(result.answers).map(([key,a])=>{
    const title=`<div class="result-card-header"><span class="type-badge ${esc(a.type)}">${esc(a.type[0].toUpperCase()+a.type.slice(1))}</span><strong title="${esc(key)}">${esc(key)}</strong>${a.type!=='noul'?`<span class="result-confidence" title="${t('Concentration, not accuracy')}">${percent(a.confidence)} ${t('confidence')}</span>`:''}</div>`;
    if(a.type==='noul')return `<article class="result-card">${title}<div class="answer-value noul-value">${Number(a.noul).toFixed(3)}<span>${t('Statement support')}</span></div><div class="noul-track"><span class="noul-marker" style="left:${clamp(a.noul)*100}%"></span></div><div class="noul-legend"><span>${t('0 · Unsupported')}</span><span>${t('0.5 · Uncertain')}</span><span>${t('Supported · 1')}</span></div></article>`;
    const probs=Object.entries(a.probabilities||{}),peak=Math.max(...probs.map(([,p])=>p));
    const bars=probs.map(([option,p])=>{const description=a.type==='score'?`${option} · ${serialize(a.legend?.[option]||'')}`:option;return `<div class="probability-row ${p===peak?'winner':''}"><div class="probability-label"><span title="${esc(description)}">${esc(description)}</span><span class="prob-number">${percent(p)}</span></div><div class="bar-track"><div class="bar-fill" style="width:${clamp(p)*100}%"></div></div></div>`;}).join('');
    const value=a.type==='score'?`${Number(a.score).toFixed(2)}<span>/ ${probs.length-1}</span>`:`${esc(a.choice)}<span>${t('selected')}</span>`;
    return `<article class="result-card ${a.type==='score'?'score-result':''}">${title}<div class="answer-value ${a.type==='score'?'score-value':''}">${value}</div>${bars}</article>`;
  }).join('');
  $('#output-content').innerHTML=stale+summary+cards+`<div class="run-meta">${esc(meta.engine||'local-nli')} · ${esc(meta.engine==='diffusiongemma-vllm'?t('{count} questions scored',{count:Number(meta.questions||0)}):t('{count} candidate evaluations',{count:Number(meta.evaluations||0)}))} · ${t('no text generation')}</div>`;
}
function hideError(){lastError='';$('#error-message').hidden=true;}
function showError(message){lastError=canonicalText(message);$('#error-message').textContent=t(lastError);$('#error-message').hidden=false;}
function errorDetail(body){if(typeof body.detail==='string')return body.detail;if(Array.isArray(body.detail))return body.detail.map(e=>`${(e.loc||[]).slice(1).join('.')}: ${e.msg}`).join('\n');return t('Request failed. Check the input and local service.');}
async function run(){
  if(pending)return;let request;try{request=getRequest();}catch(e){showError(e.message);return;}
  if(status?.status!=='ready'){showError(t('The model is not ready. Wait for download or loading to finish.'));return;}
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),120000);
  hideError();pending=true;$('#run-button').disabled=true;$('#run-label').textContent=t('Evaluating');renderOutput();
  try{
    const headers={'Content-Type':'application/json'};if(apiKey)headers.Authorization=`Bearer ${apiKey}`;
    const response=await fetch('/v1/systemone',{method:'POST',headers,body:JSON.stringify(request),signal:controller.signal});
    const body=await response.json();if(!response.ok)throw new Error(errorDetail(body));
    result=body;resultRequest=request;runs.unshift({id:Date.now(),at:new Date().toISOString(),request:clone(request),result:clone(body)});runs=runs.slice(0,20);
    try{localStorage.setItem(HISTORY_KEY,JSON.stringify(runs));}catch{toast(t('Browser storage is full. This result was not saved to history.'));}$('#history-count').textContent=runs.length;
  }catch(e){showError(e.name==='AbortError'?t('Waited 120 seconds and stopped waiting. The server may still be processing. Retry manually later.'):e instanceof TypeError?t('Cannot connect to the local service. Check that openJEV is running.'):e.message);}
  finally{clearTimeout(timeout);pending=false;$('#run-button').disabled=status?.status!=='ready';$('#run-label').textContent=t('Run evaluation');renderOutput();}
}
function defaultCriteria(type){return type==='choice'?{option_a:t('Describe when option A applies'),option_b:t('Describe when option B applies')}:type==='score'?[t('Describe the low level'),t('Describe the high level')]:{true:t('Evidence supporting the statement'),false:t('Evidence contradicting the statement')};}
function updateCriteriaHelp(){const type=$('#edit-type').value;$('#criteria-label').firstChild.textContent=t(type==='choice'?'Option definitions':type==='score'?'Ordered levels':'Criteria (optional)')+' ';$('#criteria-help').textContent=t(type==='choice'?'Enter a JSON object with 2–255 options. Keys are return values; values describe each option. null uses the key alone.':type==='score'?'Enter a JSON array with 2–10 levels, ordered low to high and indexed from 0.':'Leave blank to judge the statement directly, or provide a JSON object containing true and false. Statements generally suit NLI models.');}
function editQuestion(id=null){editingId=id;const q=id?questions[id]:{type:'choice',instructions:'',criteria:defaultCriteria('choice')};$('#dialog-title').textContent=t(id?'Edit question':'Add a question');$('#edit-id').value=id||'';$('#edit-type').value=q.type;$('#edit-instructions').value=serialize(q.instructions);$('#edit-criteria').value=q.criteria?JSON.stringify(q.criteria,null,2):'';$('#form-error').textContent='';updateCriteriaHelp();$('#question-dialog').showModal();}
function descriptionValue(raw){const text=raw.trim();if(!text)throw new Error(t('Enter a question or statement.'));if(text.startsWith('{')||text.startsWith('[')){try{return JSON.parse(text);}catch{throw new Error(t('The structured question is not valid JSON.'));}}return text;}
function saveQuestion(event){event.preventDefault();try{
  const id=$('#edit-id').value.trim(),type=$('#edit-type').value;if(!id)throw new Error(t('Enter a question ID.'));if(Object.hasOwn(questions,id)&&id!==editingId)throw new Error(t('That question ID already exists. Choose another name.'));
  const q={type,instructions:descriptionValue($('#edit-instructions').value)},raw=$('#edit-criteria').value.trim();if(raw){try{q.criteria=JSON.parse(raw);}catch{throw new Error(t('Options or levels are not valid JSON.'));}}
  if(type==='choice'&&(!q.criteria||Array.isArray(q.criteria)||typeof q.criteria!=='object'||Object.keys(q.criteria).length<2||Object.keys(q.criteria).length>255))throw new Error(t('Choice needs a JSON object with 2–255 options.'));
  if(type==='score'&&(!Array.isArray(q.criteria)||q.criteria.length<2||q.criteria.length>10))throw new Error(t('Score needs a JSON array with 2–10 levels.'));
  if(type==='noul'&&raw&&(!q.criteria||Array.isArray(q.criteria)||typeof q.criteria!=='object'||Object.keys(q.criteria).sort().join(',')!=='false,true'))throw new Error(t('Noul criteria need both true and false. Leave blank if criteria are unnecessary.'));
  const entries=Object.entries(questions),index=entries.findIndex(([key])=>key===editingId);if(index>=0)entries[index]=[id,q];else entries.push([id,q]);questions=Object.fromEntries(entries);renderQuestions();markEdited();$('#question-dialog').close();
}catch(e){$('#form-error').textContent=e.message;}}
function renderHistory(){
  $('#history-count').textContent=runs.length;$('#clear-history').disabled=!runs.length;
  $('#history-list').innerHTML=runs.length?runs.map(r=>`<button class="history-row" data-run-id="${Number(r.id)}"><span class="model-icon">${icon('history')}</span><div class="history-preview"><strong>${esc(serialize(r.request.state).replace(/\n/g,' '))}</strong><small>${esc(new Date(r.at).toLocaleString(locale==='zh'?'zh-CN':'en-US'))} · ${t('{count} questions',{count:Object.keys(r.request.questions).length})} · ${esc(r.result.meta?.engine||'local-nli')}</small></div><span class="time-pill">${esc(latency(r.result.meta?.latency_ms||0))}</span><span>↗</span></button>`).join(''):`<div class="history-empty">${t('No runs yet. Start your first evaluation in the Playground.')}</div>`;
}
function codeFor(mode){
  const request=getRequest(),json=JSON.stringify(request,null,2),url=`${location.origin}/v1/systemone`,authCurl=status?.auth_required?" \\\n  -H 'Authorization: Bearer YOUR_LOCAL_API_KEY'":'';
  if(mode==='curl')return `curl '${url}' \\\n  -H 'Content-Type: application/json'${authCurl} \\\n  --data-binary '${json.replace(/'/g,"'\"'\"'")}'`;
  if(mode==='python')return `import json\nfrom urllib.request import Request, urlopen\n\npayload = json.loads(${JSON.stringify(json)})\nrequest = Request(\n    ${JSON.stringify(url)},\n    data=json.dumps(payload).encode(),\n    headers={"Content-Type": "application/json"${status?.auth_required?', "Authorization": "Bearer YOUR_LOCAL_API_KEY"':''}},\n)\nwith urlopen(request, timeout=120) as response:\n    result = json.load(response)\nprint(json.dumps(result["answers"], indent=2, ensure_ascii=False))`;
  return `const response = await fetch(${JSON.stringify(url)}, {\n  method: "POST",\n  headers: { "Content-Type": "application/json"${status?.auth_required?', "Authorization": "Bearer YOUR_LOCAL_API_KEY"':''} },\n  body: JSON.stringify(${json}),\n});\nconst result = await response.json();\nif (!response.ok) throw new Error(JSON.stringify(result));\nconsole.log(result.answers);`;
}
function renderCode(){try{$('#code-content').textContent=codeFor(codeMode);}catch(e){$('#code-content').textContent=e.message;}$$('#code-dialog [data-code]').forEach(b=>b.classList.toggle('selected',b.dataset.code===codeMode));}
async function copy(text){try{await navigator.clipboard.writeText(text);toast(t('Copied to clipboard.'));}catch{toast(t('Clipboard access was blocked. Select and copy the text manually.'));}}
function renderStatus(){
  const notice=$('#model-notice');
  if(!status){$('#status-label').textContent=t(statusFailed?'Service offline':'Connecting to service');$('.status-dot').className=`status-dot ${statusFailed?'error':'loading'}`;$('#run-button').disabled=true;if(statusFailed){notice.hidden=false;notice.className='notice error';notice.textContent=t('Cannot reach the local service. Start python -m openjev serve from the project directory. This page will reconnect automatically.');}return;}
  const remote=status.location==='remote',gpu=status.backend==='diffusiongemma';
  $('#processing-location').textContent=t(remote?'Processed on a remote GPU':gpu?'GPU service via a local connection':'Processed locally');
  $('#location-note').textContent=t(remote?'Remote GPU · authenticated connection':gpu?'GPU service · local connection / SSH tunnel':'Inference stays on this machine');
  $('.model-selector strong').textContent=gpu?'DiffusionGemma · 26B A4B · NVFP4':status.backend==='kev'?'Kev · Local server':'Multilingual MiniLM · INT8';
  $('.model-selector small').textContent=`${gpu?'vLLM · NVIDIA GPU':status.backend==='kev'?'Shared-state decisions':'Local NLI · '+String(status.device||'cpu').toUpperCase()} · ${status.max_tokens} tokens`;
  $('.input-caption').textContent=t(gpu?'Questions share context and return structured decisions. Questions may affect one another.':'Questions are evaluated independently and batched in one request.');
  $('.output-footnote p').textContent=t(gpu?'DiffusionGemma label probabilities. Confidence measures concentration, not correctness; probabilities are not task-calibrated.':status.backend==='kev'?'Results come from local Kev. Confidence uses its formula; calibration outside its training distribution is not established.':'Uncalibrated estimates from an open NLI model. Confidence measures concentration, not accuracy.');
  $('#status-label').textContent=t({ready:gpu?'GPU model ready':'Local model ready',loading:'Downloading / loading model',error:'Model loading failed'}[status.status]||'Connecting to service');$('.status-dot').className=`status-dot ${status.status==='ready'?'':status.status==='loading'?'loading':'error'}`;
  $('#run-button').disabled=pending||status.status!=='ready';
  if(status.status==='loading'){notice.hidden=false;notice.className='notice';notice.textContent=t(status.backend==='nli'?'Downloading / loading the open model (about 107 MB on first use). You can edit inputs while waiting.':remote?'Connecting to the remote GPU service. You can edit inputs while waiting.':'Connecting to the local model service. You can edit inputs while waiting.');}
  else if(status.status==='error'){notice.hidden=false;notice.className='notice error';notice.textContent=`${t('Model loading failed')}: ${status.error||t('See the server log.')} ${t(gpu?'Check that the GPU service is ready.':'See the server log.')}`;}
  else if(status.auth_required&&!apiKey){if(!notice.querySelector('input')||notice.dataset.locale!==locale){const value=notice.querySelector('input')?.value||'';notice.hidden=false;notice.className='notice';notice.innerHTML=`<div class="auth-row"><label for="local-key">${t('This service requires an API key')}</label><input id="local-key" type="password" autocomplete="off" placeholder="${t('Local API key')}"><button id="set-key">${t('Connect')}</button></div>`;notice.querySelector('input').value=value;notice.dataset.locale=locale;}}
  else notice.hidden=true;
}
async function checkStatus(){try{const response=await fetch('/api/status');if(!response.ok)throw new Error('offline');status=await response.json();statusFailed=false;}catch{status=null;statusFailed=true;}renderStatus();setTimeout(checkStatus,status?.status==='ready'?12000:2500);}
function applyLanguage(next,initial=false){
  locale=next==='zh'?'zh':'en';try{localStorage.setItem('openjev.locale',locale);}catch{}document.documentElement.lang=locale==='zh'?'zh-CN':'en';$('#language-select').value=locale;
  for(const item of staticText)if(item.node.isConnected)item.node.textContent=item.prefix+t(item.text)+item.suffix;
  for(const item of staticAttributes)item.element.setAttribute(item.attr,t(item.text));
  $('#breadcrumb-view').textContent=t({playground:'Playground',examples:'Examples',history:'Run history',guide:'Guide'}[activeView]);
  if(!initial&&activePreset)loadExample(activePreset);else{renderQuestions();renderPresets();renderOutput();countChars();}
  renderExampleGallery();renderHistory();renderStatus();$('#run-label').textContent=t(pending?'Evaluating':'Run evaluation');
  if($('#question-dialog').open){$('#dialog-title').textContent=t(editingId?'Edit question':'Add a question');$('#form-error').textContent=t(canonicalText($('#form-error').textContent));updateCriteriaHelp();}
  if($('#code-dialog').open)renderCode();if(lastError)$('#error-message').textContent=t(lastError);if(!$('#toast').hidden)$('#toast').textContent=t(lastToast);
}
$$('[data-icon]').forEach(el=>{el.innerHTML=icon(el.dataset.icon);});
document.addEventListener('click',event=>{
  const target=event.target.closest('button');if(!target)return;
  if(target.dataset.view)setView(target.dataset.view);if(target.dataset.preset)selectExample(target.dataset.preset);if(target.dataset.loadExample)selectExample(target.dataset.loadExample);if(target.hasAttribute('data-edit'))editQuestion(target.dataset.edit);
  if(target.hasAttribute('data-delete')){questions=Object.fromEntries(Object.entries(questions).filter(([key])=>key!==target.dataset.delete));renderQuestions();markEdited();}
  if(target.hasAttribute('data-close'))target.closest('dialog').close();
  if(target.dataset.output){outputMode=target.dataset.output;$$('.output-tabs [data-output]').forEach(b=>b.classList.toggle('selected',b.dataset.output===outputMode));renderOutput();}
  if(target.dataset.mode&&target.dataset.mode!==stateMode){if(target.dataset.mode==='json')$('#state-input').value=JSON.stringify($('#state-input').value,null,2);else{try{$('#state-input').value=serialize(JSON.parse($('#state-input').value));}catch{toast(t('Fix the JSON before switching to text.'));return;}}stateMode=target.dataset.mode;renderStateMode();markEdited();}
  if(target.dataset.runId){const saved=runs.find(r=>r.id===Number(target.dataset.runId));if(saved){questions=clone(saved.request.questions);setState(saved.request.state);result=clone(saved.result);resultRequest=clone(saved.request);activePreset=null;renderQuestions();renderPresets();renderOutput();hideError();setView('playground');}}
  if(target.dataset.code){codeMode=target.dataset.code;renderCode();}
  if(target.id==='set-key'){apiKey=$('#local-key').value.trim();if(apiKey){$('#model-notice').hidden=true;toast(t('The API key stays in this page’s memory only.'));}}
});
$('#language-select').addEventListener('change',event=>applyLanguage(event.target.value));
$('#example-search').addEventListener('input',event=>{exampleSearch=event.target.value;renderExampleGallery();});
$('#example-category').addEventListener('change',event=>{exampleCategory=event.target.value;renderExampleGallery();});
$('#clear-example-filters').addEventListener('click',()=>{exampleSearch='';exampleCategory='';$('#example-search').value='';renderExampleGallery();$('#example-search').focus();});
window.addEventListener('storage',event=>{if(event.key==='openjev.locale')applyLanguage(event.newValue);});
$('#state-input').addEventListener('input',markEdited);$('#run-button').addEventListener('click',run);$('#add-question').addEventListener('click',()=>editQuestion());$('#question-form').addEventListener('submit',saveQuestion);
$('#edit-type').addEventListener('change',()=>{const type=$('#edit-type').value;$('#edit-criteria').value=type==='noul'?'':JSON.stringify(defaultCriteria(type),null,2);updateCriteriaHelp();});
$('#code-button').addEventListener('click',()=>{try{getRequest();renderCode();$('#code-dialog').showModal();}catch(e){showError(e.message);}});$('#copy-code').addEventListener('click',()=>copy($('#code-content').textContent));$('#copy-result').addEventListener('click',()=>result&&copy(JSON.stringify(result,null,2)));
$('#download-result').addEventListener('click',()=>{if(!result)return;const url=URL.createObjectURL(new Blob([JSON.stringify({request:resultRequest,response:result},null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=`openjev-${Date.now()}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast(t('Result JSON downloaded.'));});
$('#clear-history').addEventListener('click',()=>{if(confirm(t('Clear all run history saved by this app in this browser?'))){runs=[];try{localStorage.removeItem(HISTORY_KEY);}catch{}renderHistory();toast(t('Run history cleared.'));}});
document.addEventListener('keydown',event=>{if((event.metaKey||event.ctrlKey)&&event.key==='Enter'&&!document.querySelector('dialog[open]')&&!$('#playground-view').hidden){event.preventDefault();run();}});
$$('dialog').forEach(dialog=>dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}}));
(async function init(){applyLanguage(locale,true);checkStatus();try{const response=await fetch('/api/examples');if(!response.ok)throw new Error();examples=await response.json();const requested=new URLSearchParams(location.search).get('example');loadExample(examples.some(e=>e.id===requested)?requested:examples[0].id);const requestedView=new URLSearchParams(location.search).get('view');if(['examples','history','guide'].includes(requestedView))setView(requestedView);}catch{showError(t('Could not load examples. Start the service and refresh this page.'));}if(legacyCleanupFailed)toast(t('The browser blocked old-history cleanup. Previous-version records are not loaded.'));else if(legacyHistoryCleared)toast(t('Previous-version local demo history was cleared for this update.'));})();
