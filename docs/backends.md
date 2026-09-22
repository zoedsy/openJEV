# 后端配置

## 默认：MiniLM NLI

```bash
python -m openjev download
OPENJEV_OFFLINE=1 python -m openjev serve
```

环境变量：

| 变量 | 默认值 | 含义 |
|---|---|---|
| `OPENJEV_BACKEND` | `nli` | `nli`、`kev` 或 `diffusiongemma` |
| `OPENJEV_DEVICE` | `cpu` | 当前 INT8 ONNX 后端仅支持 CPU |
| `OPENJEV_CACHE_DIR` | `.models` | 权重缓存 |
| `OPENJEV_OFFLINE` | `0` | `1` 时仅从缓存加载 NLI 权重 |
| `OPENJEV_API_KEY` | 未设置 | 若设置，`/v1` 请求必须带 bearer token |
| `OPENJEV_MODEL` | 见 README | 兼容的三类 NLI ONNX 仓库 ID（需 onnx/model_quantized.onnx） |
| `OPENJEV_REVISION` | 默认 MiniLM 的固定 SHA | 更换模型时必须一并指定对应 revision |
| `OPENJEV_KEV_URL` | `http://127.0.0.1:8009` | 已启动的本地 Kev origin |

`.env.example` 是参考，不会自动加载。不要把真实密钥提交到 Git。

更换 NLI 模型时，配置必须提供明确的 `entailment` / `neutral` / `contradiction` 标签。当前上限仍为 512 tokens，不自动继承模型卡声称的更长窗口。

## 可选：复用开源 Kev

Kev 有自己的模型和依赖，建议使用单独的虚拟环境。以下为依据上游源码整理的启动方法；本轮仅测试了本地 HTTP 适配契约，**没有下载或运行 Kev 权重**。

在另一个目录 / 终端准备 [Kev](https://github.com/jaredpalmer/kev)：

```bash
git clone https://github.com/jaredpalmer/kev.git
cd kev
git checkout 20fa6268c8ceb226530be2fb5266ab2c36b37724
# Kev 需要 Python 3.12+。使用它的独立环境。
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[serve]'
python -m kev.serve --run jaredpalmer/kev-0.5b --port 8009
```

上游会下载适配器和 Qwen 底座。请以具体模型卡的许可证、资源需求及局限为准。

然后在 openJEV 目录启动：

```bash
OPENJEV_BACKEND=kev ./run.sh
```

适配器只允许 loopback HTTP 地址，不会把文本发给外部模型服务。openJEV 将请求的 model 映射为 `kev-latest`，保留上游答案和 usage，并添加本地耗时、来源等 metadata。

注意：

- Kev 的 Noul / Confidence 计算来自它自己的实现，不是默认 NLI 后端的公式。
- 上游会将概率四舍五入到两位小数，和可能略偏离 1；openJEV 不篡改这些值。
- 当前 Kev 适配会在 openJEV 启动时检查服务；若启动顺序颠倒，先启动 Kev，再重启 openJEV。
- openJEV 的 32 问题 / 256 候选 / 256 KiB 请求限制仍然有效。
- 不使用错误时回退到其他模型的机制；连接失败会明确报错。

## GLiClass / SemIf / NanoJev

已调查，但尚未实现对应后端。模型与训练路线的比较见 [alternatives.md](alternatives.md)。

## DiffusionGemma / GPU

使用 [通用 GPU recipe](diffusiongemma.md) 启动服务后，运行 `./run-gpu.sh`。模型服务与本地页面可以位于不同机器，通过 SSH 隧道连接。

| 变量 | 含义 |
|---|---|
| `OPENJEV_BACKEND=diffusiongemma` | 使用 DiffusionGemma typed reads |
| `OPENJEV_DIFFUSION_MAX_TOKENS` | 与部署一致的服务窗口，默认 8192 |
| `OPENJEV_DIFFUSION_URL` | loopback origin，默认 `http://127.0.0.1:8008`，也可由 SSH 转发 |
| `OPENJEV_RELAY_COMMAND` | 可选的 JSON 参数数组，启动能执行远端命令的持久 stdio 通道 |
| `OPENJEV_RELAY_IDENTITY_FILE` | 可选 stdio 通道读取的远端模型身份文件 |

HTTP 模式检查服务 API，模型版本由部署 recipe 固定；持久 stdio 模式另外核对 ready 状态和身份文件。不会自动回退到 MiniLM。持久通道将单个请求失败明确返回，后续新请求可重新连接，不会重放状态未知的请求。
