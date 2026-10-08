# V2-X1 实现后审计

**结论**：自动化实现门PASS；Critical/P0/P1=0；同一真人四图的一致性待V2X-AC01人工验收。

- `SourcePackService.add_source`以pack_id+SHA生成稳定source UUID；同内容幂等且不静默改写用户标签。
- 首次读取时若存在V1活动写真，按原asset id/哈希/路径/授权稳定迁移为revision 1；活动写真指针不改变。
- 新上传先写服务端生成名称的私有文件，再以revision CAS提交manifest；校验或提交失败删除新文件，旧manifest字节保持不变。
- 仅接受JPEG/PNG magic且扩展名白名单，单文件20MiB；修复了`AssetStore`此前未按portrait/voice约束MIME类别的问题。
- API只返回source_id、哈希、角度、用户标签、授权ID、来源、时间和受控内容URL；绝对/相对文件路径均不出响应。
- 内容读取按source_id和当前写真授权复检，返回`no-store, private`；PWA白名单不会缓存该API。
- 设置页支持多选、逐张角度/穿着标注、串行上传与真实私有缩略图；导入路径不调用activate或Avatar build。
- feature flag关闭时API 404、素材tab隐藏，V1人物tab和链路保留。
