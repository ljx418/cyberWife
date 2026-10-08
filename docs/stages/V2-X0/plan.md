# V2-X0 合同与证据基线开发计划

**入口**：V2-X-D1 PASS；开放P0/P1=0  
**目标**：在不改变V1运行行为的前提下，建立后续V2-X能力所需的安全开关、manifest领域合同、原子存储和可重复证据基线。

## 开发顺序

1. 在默认配置增加`v2x`独立feature flag表，只有`contracts=true`，其余全部false。
2. 新增`SourcePackManifest`领域验证器，锁定schema v1、UUID、SHA-256、相对路径、引用完整性和单活动角色边界。
3. 新增`ExperienceManifestRepository` port及`JsonManifestRepository`，支持load/stage/commit/rollback和revision CAS。
4. 新增`SourcePackService`，负责首次创建、幂等V1资产映射和提交；API/UI留待X1接入。
5. 新增隐私安全的X0证据采集器，只报告schema、revision、哈希、flag和资源数字。
6. 用合成素材和临时私有根执行正常、重复、冲突、损坏、路径穿越、失败恢复和回滚测试。

## 不做

- 不开放多素材UI或API，不迁移真实私人素材，不切换active人物。
- 不更改实时音频/视频/对话链，不启动重型模型。
- 不修改`0001_init.sql`。

## 回滚

删除/关闭`v2x`配置读取即可恢复V1；X0没有活动运行态切换。manifest测试只写临时目录。生产仓储即使创建数据，也不被V1读取。
