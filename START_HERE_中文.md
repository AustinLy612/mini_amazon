# Mini-Amazon M2 — Ziyi Shen / Carts

个人交付：完整 Wishlist tutorial 代码、Carts 只读原型、数据库与页面设计。完整购物车编辑、结账和订单详情属于后续实现。

## 先看这些文件

- docs/milestone2/CARTS_DESIGN.md：与团队 USER/PRODUCT 最新设计对齐的英文报告源。
- docs/milestone2/Cart_Order_Milestone2.pdf：个人章节，不是全组完整 REPORT.pdf。
- docs/milestone2/交给队友_中文.md：字段约定、运行和数据库迁移说明。
- docs/milestone2/CODE_EXPLAINED_中文.md：代码作用及设计原因。
- docs/milestone2/VALIDATION.md：实际测试记录。

课程容器中运行 poetry install --no-root，然后 poetry run python -m unittest discover -s tests -v。

本次新建验证库 mini_amazon_m2_verify_aligned_20261008；旧版开发库没有自动迁移。新环境与旧库升级需要不同 SQL 脚本，请先读交接说明，勿重复建表。

全组最终提交 README.txt 和 REPORT.pdf；共同表只定义一次，其余模块引用它们。Sellers 尚需确认库存/履约接口。
