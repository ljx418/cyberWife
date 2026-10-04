# INST1 详细开发计划：干净机安装可复现性

**日期**：2026-10-05

## 目标

消除运行入口对`Administrator`用户和既有目录的隐式绑定，提供可审计的安装前检、配置生成和安装后验证，使新Windows用户/干净WSL可按明确的本地工件清单完成部署。

## 实施内容

1. RuntimeLauncher运行时解析WSL `$HOME`，派生数据根、Cosy/Avatar venv、NVIDIA库与Avatar数据目录；所有值仍允许显式覆盖。
2. Gateway默认数据根使用当前Linux用户home；CosyVoice源码目录从环境/运行配置读取。
3. 新增`Install-CyberWife.ps1`：`audit/prepare/verify`三态，检查Windows/WSL/GPU/模型/venv/前端构建，生成不含用户名硬编码的本机runtime配置；不静默下载模型、不修改全局防火墙。
4. 增加PowerShell合同测试和隔离临时目录dry-run；当前目标机执行verify。
5. 输出安装、备份、卸载和数据清除边界文档。

## INST1.1 闭环修正（2026-10-05）

目标机复核发现，上述`prepare`只生成目录与配置，并未准备Python依赖；Speech进程还使用系统`python3`。这不足以支撑“新WSL用户可复现安装”，原结论降级为局部完成。

修正顺序：

1. 将已真实运行的Core/Speech/Cosy与Avatar顶层依赖固定为两份Python 3.12运行时锁文件，不继承系统site-packages。
2. `prepare`支持显式`wheelhouse`或`online`模式创建隔离venv；默认`none`仍不联网。`online`必须同时显式给出`-AllowNetworkInstall`。
3. 运行器增加`SpeechPythonWsl`，默认指向受控Core/Cosy venv，不再调用系统Python。
4. 依赖准备后执行pip一致性、关键模块import、前端生产构建与原有verify；任一失败都不签就绪。
5. 模型、CosyVoice源码与授权素材继续只接受本机已有工件，不由安装器暗中下载。
6. 完整生命周期复核时若发现“HTTP 200但JSON仍为loading”，必须修正启动器功能健康语义并重跑；不得以端口存活签ready。

## INST1.2 隔离环境依赖复现（2026-10-05）

在不改动当前生产venv的前提下，使用临时私有根目录创建两个不继承system-site-packages的Python 3.12 venv，按仓库运行时requirements执行真实解析和安装。验证顺序：

1. `pip check`必须无0冲突，`pyvenv.cfg`必须明确`include-system-site-packages = false`。
2. Core venv导入Gateway/Speech/Cosy关键模块；Avatar venv导入LiveTalking/Wav2Lip关键模块。
3. Core venv实际加载本机CosyVoice源码、ASR、VAD与Embedding适配器；Avatar venv执行上游启动导入检查。
4. 不复制模型和授权资产；只验证依赖可复现性。完成后仅删除本轮`mktemp`生成且已校验前缀的临时目录。
5. 该证据可关闭“WSL Python依赖从零安装”风险，但不能替代全新Windows用户、WSL发行版、GPU驱动和模型工件组合的AC06外部门。

## INST1.3 离线wheelhouse复现（2026-10-05）

目标是把已经通过在线解析的两套Python运行时固化为可校验的离线工件，使目标机后续安装不依赖PyPI或PyTorch索引。执行顺序：

1. 使用Python 3.12分别构建`core/`与`avatar/` wheelhouse，禁止平铺混合两个运行时的不同Transformers/Numpy版本；联网构建必须显式授权。
2. 生成不含私有绝对路径的JSON清单，记录每个wheel文件的相对路径、大小和SHA256；重复验证不得修改工件。
3. 安装器在wheelhouse根目录存在`core/`与`avatar/`时按组件选择子目录，并在安装前强制验证清单；旧的单目录入口仅保留兼容性。
4. 从两个新的、不继承system packages的Python 3.12 venv执行`--no-index --find-links`真实安装；网络索引不可参与。
5. 执行INST1.2同一套10项依赖/源码导入检查，只有全通过才签INST1-AC11。wheelhouse与临时venv均位于WSL ext4，不占用C盘；临时venv验收后移入回收站。

## 停止条件

脚本不得结束外部进程、不得覆盖已有私有配置/数据、不得把模型文件纳入Git。没有第二台干净Windows/WSL时，只能签“安装器合同/目标机verify”，不能冒充干净机端到端PASS。
