# V2-X3.1 验收标准

| ID | 操作 | 硬门 |
|---|---|---|
| X3.1-AC01 | 首次读取场景目录 | 返回4项；UUID、label、真实SHA、焦点、安全区、预览URL完整 |
| X3.1-AC02 | 重复读取与服务重启 | UUID与SHA不变；manifest revision不发生无意义增长 |
| X3.1-AC03 | 修改测试背景字节后登记 | SHA随真实文件变化；以CAS提交新revision，不产生半写状态 |
| X3.1-AC04 | 缺失背景或CAS冲突 | 请求失败；旧manifest保持可读且revision不变 |
| X3.1-AC05 | 浏览器打开设置页 | 展示4个场景及“动态素材待准备”；没有可点击的虚假激活入口 |
| X3.1-AC06 | feature flag关闭 | 正式目录API/UI关闭；原背景选择仍可用 |
| X3.1-AC07 | 隐私与回归 | API不暴露私有路径；全量构建、Playwright与后端测试无新增失败 |

