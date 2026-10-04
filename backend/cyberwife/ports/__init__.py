"""Ports 包：6 个抽象接口。

按 target-architecture §3 / §5 与 implementation-contracts §18。

依赖规则：api → application → domain + ports；adapters → ports。
Domain 不得导入 ports（避免循环依赖）。
"""
