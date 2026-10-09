# V2-X8.0-R1 实施结果

## 结论

**PASS / ACTIVE。** 项目所有者选择B后，MuseTalk 1.5已成为本机默认Avatar引擎；四个批准场景均有独立250帧完整场景派生物。Wav2Lip工件、绑定与选择器保留为串行回退，不与MuseTalk双常驻。

## 实施内容

- RuntimeLauncher支持`auto|wav2lip|musetalk`，`auto`读取本机bootstrap选择；按引擎选择隔离venv、模型根和启动参数。
- ScenePresetService从受校验binding/manifest报告真实engine，不再把场景说话态写死为Wav2Lip。
- 新增四场景MuseTalk安装器和原子引擎选择器；选择时同步rendition目录、活动binding和bootstrap，防止“模型进程已切换但资产仍属旧引擎”。
- MuseTalk派生manifest保留原场景的来源SHA、构图、坐标、时序重采样、循环与低幅动作信息，并明确`blend_profile=jaw`。
- V2-A领域目标新增角色级`AvatarModelPolicy`：用户未来可选择已安装且有兼容rendition的引擎；串行停旧启新、失败保持旧ActiveContext、禁止双常驻。

## 四场景真实音频结果

同一8秒CosyVoice输入SHA=`5cba0620d4ecd5ada91425eb64b8e27d3244927e859774b63602e5f0109b0340`。

| 场景 | inferfps | finalfps | 首个视频包 | 口型相关 | 黑帧/缺口 | 最大连续近冻结对 | 结论 |
|---|---:|---:|---:|---:|---:|---:|---|
| 清晨卧室 | 58.847 | 25.656 | 555.782ms | 0.470460 | 0/0 | 2 | PASS |
| 花园阳光房 | 57.682 | 25.519 | 467.857ms | 0.603099 | 0/0 | 2 | PASS |
| 雨夜书房 | 59.606 | 25.461 | 472.605ms | 0.465293 | 0/0 | 2 | PASS |
| 蓝调客厅首次 | 59.449 | 25.471 | 441.817ms | 0.555815 | 0/0 | 3 | FAIL，未冒充通过 |
| 蓝调客厅复测 | 56.263 | 25.478 | 478.100ms | 0.563375 | 0/0 | 2 | PASS |
| 蓝调客厅重启确认 | 49.326 | 26.371 | 2419.978ms | 0.430108 | 0/0 | 0 | PASS |

蓝调首次出现约120ms连续近冻结，因此返回验证并补做两轮；随后两轮均通过，重启确认首帧仍低于已批准7秒上限。自动分析只签署响应、连续性与黑帧门，不替代项目所有者已经完成的B路线自然度判断。

## 资源与回滚

- 真实组合峰值观测：VRAM 16.44/23.99GiB，余量约7.55GiB；WSL RAM 13.72/15.53GiB，未超过约16GiB预算。
- 稳态复核：VRAM约10.06GiB；Windows空闲内存约16.9GiB。
- WSL内只有一个`python app.py --model musetalk`实例监听8010/8011；Windows看到的两个`wsl.exe`为父子relay，对应同一个Linux模型进程，不是双模型常驻。
- 已真实执行MuseTalk→Wav2Lip→MuseTalk往返。两端健康、活动engine和场景绑定一致，最终恢复MuseTalk全绿。

## 回归

- 根目录：62 passed。
- 后端：410 passed，7 skipped。
- Avatar：18 passed。
- 前端生产构建：PASS。
- Playwright/Chrome：51 passed。

首次后端全量命令从`backend/`目录使用错误`PYTHONPATH=.`导致6个仓库级包收集失败；按项目合同从仓库根以`PYTHONPATH=backend:.`重跑后410项通过。收集失败未冒充产品通过。
