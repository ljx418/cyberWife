# V2-X1 开发前审计

**结论**：PASS；Critical/P0/P1=0，可以进入实现。

- X0已提供严格schema、稳定UUID、安全相对路径、文件锁、staged SHA、revision CAS、fsync/replace与rollback，X1无需另建存储体系。
- 双权威风险通过“source-pack仅管理输入源；V1 active portrait继续驱动实时Avatar”关闭。上传X1素材不调用`activate_asset`或Avatar build。
- 隐私风险通过服务端生成文件名、source_id读取、写真授权复检、no-store/private和绝对路径不出API关闭。
- 文件/manifest跨介质原子性无法由单一rename完成；采用先写源图、后CAS manifest、失败删除新图的补偿事务。旧manifest始终有效。
- 重复内容用pack_id+SHA稳定source UUID幂等；标签变化不静默改写已有事实，需使用新文件或未来编辑合同。
- 单文件20MiB、串行上传和无模型推理满足本机内存/显存边界。
- X1不实现删除，避免在尚无完整派生引用图前造成悬挂；删除传播留给有明确引用检查的后续阶段。
