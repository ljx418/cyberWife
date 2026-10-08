# V2-X0 自动化验收报告

**日期**：2026-10-08  
**结论**：X0-AC01～07 PASS  
**数据性质**：真实本机配置解析、真实文件系统写入/fsync/原子替换、合成非私人manifest、明确故障注入；无模型或用户体验主张。

| 验收 | 证据 | 结果 |
|---|---|---|
| X0-AC01 flag | 14键；仅`contracts`启用；非法类型/未知键测试 | PASS |
| X0-AC02 schema | UUID/SHA/路径/嵌套字段/时区/重复/悬空引用正反例 | PASS |
| X0-AC03 提交回滚 | stage→commit→load→r2→rollback r1；恢复字节等价 | PASS |
| X0-AC04 幂等bootstrap | 同一legacy asset重复两次，manifest和UUID完全相同，revision仍为1 | PASS |
| X0-AC05 故障/并发 | 注入`os.replace`失败保留旧active；交叉writer staged token拒绝误提交 | PASS |
| X0-AC06 隐私摘要 | 断言场景标签、外观标签、相对路径和consent id均不在JSON证据 | PASS |
| X0-AC07 回归 | X0相关集合76 passed；全后端392 passed/7 skipped | PASS |

## 命令与失败披露

1. `PYTHONPATH=backend pytest ...`：X0及相邻单元测试76 passed。
2. 首次全回归只设置`PYTHONPATH=backend`，因历史测试需仓库根而在收集阶段报`workers/ops`不可导入；改为项目真实双路径后继续。
3. 双路径全回归第一次为385 passed、7 skipped、4 failed、3 errors；全部失败来自当前系统Python缺少仓库已锁定的`opencc-python-reimplemented==0.1.7`。
4. 安装该已声明的精确依赖到用户Python后重跑：392 passed、7 skipped。没有修改产品代码来掩盖环境问题。
5. `compileall`、TOML解析、Draw.io/D1前置门和`git diff --check`通过。

7个skip为既有专用GPU/真实模型条件测试；X0没有新增skip。X0未启动模型，不用这些skip签功能体验门。
