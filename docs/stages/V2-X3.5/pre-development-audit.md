# V2-X3.5 开发前审计

**结论：PASS，可进入实现。** X3.3红衣四场景、X3.4第二外观三场景及R2口播收尾均已完成机器门和人工门。当前阻断不是素材质量，而是运行态数据合同仍只能表达每场景一个外观。

| 风险 | 等级 | 闭环方式 | 状态 |
|---|---|---|---|
| 覆盖v1绑定导致红衣资产丢失 | P1 | 新建v2组合绑定，保留v1文件与manifest历史 | CLOSED FOR ENTRY |
| 同一scene下rendition选择歧义 | P1 | 绑定以appearance+scene唯一键，并以精确rendition SHA/ID验证 | CLOSED FOR ENTRY |
| 只切外观或只切场景产生混搭 | P1 | 单一CAS提交两个active ID；active Avatar/Idle共同按组合解析 | CLOSED FOR ENTRY |
| 前端先显示新画面、后端切换失败 | P1 | 后端成功后再更新UI；失败重读权威目录 | CLOSED FOR ENTRY |
| 旧客户端/测试失效 | P2 | 保留原scene激活语义；appearance参数可选，v1绑定继续兼容 | CLOSED FOR ENTRY |
| 借组合预设偷跑多角色 | P1 | appearance只属于当前source-pack；无character_id、voice/memory切换 | CLOSED FOR ENTRY |
| 第二外观候选未经批准被激活 | P0 | 安装器要求X3.4人工批准状态并显式提升visual_approved | CLOSED FOR ENTRY |

审计未发现新增致命或重大规格偏差。允许修改source-pack服务、场景服务、REST合同、设置页和受控安装器；禁止改变TurnPipeline、TTS、LLM或记忆权威边界。
