# V1FINAL-AC09 外部视角审查

**结论**：PASS FOR LIVE/INDEPENDENT EXECUTION；V1仍未签署。

审查一：总门不只读取三个`result`。发布门逐文件复算SHA/size；现场门和干净机门重新检查原始结构化计数、布尔和阈值，降低手工编辑顶层PASS的风险。

审查二：现场报告此前缺少代码版本归属，现已由PowerShell从干净跟踪工作树取得HEAD并传入Chrome取证器；AC06R原本已有workspace revision。跨提交报告必定FAIL。

审查三：freeze此前漏掉Workers/Migrations/现场核心且可能扫描Git忽略本机配置，现已改为Git跟踪文件集合并补齐运行源码根，避免旧Avatar/Speech/数据库代码或私有配置混入。

审查三-B：`prototype/dist`此前被Git忽略，真正干净clone会触发安装器`npm ci`，与offline-only冲突。现将约1.9MiB验收后静态工件纳入Git；源码修改后仍由build/Playwright/冻结SHA共同约束。

审查四：当前机器没有第二个真实Ubuntu发行版；现有`docker-desktop`不符合无Docker架构和独立WSL要求。多个Windows沙箱账号不能改变当前WSL machine-id，也没有被用来绕过双身份门。

剩余不确定性只来自两次必须发生的外部交互：用户现场感知/物理麦克风、独立新Windows+WSL安装。额外静态ClaudeCode CLI审计不能替代这两项，因此不列为出门前置。
