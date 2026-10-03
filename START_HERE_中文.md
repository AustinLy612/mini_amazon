# 你的 Milestone 2：先看这里

已从你给的 GitHub 克隆实际 skeleton，在本地 `carts-milestone2` 分支开始工作。没有推送 GitHub。

## 现在要交什么
Milestone 2 的评分重点是全组数据库设计（5 分）和网站设计（5 分），不是完整购物车实现。你负责 Cart / Order：购物车行、订单头/明细、数量和价格约束、结账事务、页面交互，以及与 Users / Products / Sellers 的接口。每个人还需要亲自跑通 skeleton、完成 TUTORIAL.md。

- `docs/milestone2/CARTS_DESIGN.md`：可编辑英文设计，可合并进组报告。
- `docs/milestone2/Cart_Order_Milestone2.pdf`：你负责部分的报告；不是整组可直接提交的完整 REPORT.pdf。
- `docs/milestone2/README.template.txt`：整组 README 模板，需要真实姓名、分工和进展。
- `db/carts_schema.sql`：待队友确认的增量 schema，不自动修改原 create.sql/load.sql。
- `app/models/cart.py`、`app/carts.py`、`app/templates/cart.html`：提前搭好的只读购物车查询，供 milestone 3 继续。

## 设计怎么理解
CartItems 一行由 buyer + seller + product 唯一确定。购物车不保存价格，显示 Products 当前价格；同一商品不同卖家是两行。Orders 保存买家、日期和收货信息快照；OrderItems 保存数量、成交单价和履约时间。库存和余额在结账那一刻一起更新；任何一步失败都回滚。整单是否履约由所有订单行是否履约推导。原 Purchases 只作 skeleton 示例，之后由 Users 同学改为查询 Orders/OrderItems。

## 在你的 Mac / VS Code 课程环境运行
已经由你在课程容器中初始化成功，并确认网页登录和 Cart 正常。项目在 Mac 的 `Desktop/CS_316/mini_amazon`，在容器中是 `~/shared/mini_amazon`。独立数据库为 `mini_amazon_carts_dev`。

以后正常启动只需打开 Docker、连接课程容器，在容器终端运行：

```sh
cd ~/shared/mini_amazon
poetry run flask run
```

打开 http://localhost:8080。示例账号 icecream@tastes.good / test123；购物车两种商品各两件，总额 $11.96。不要重复初始化；不要运行原 install.sh 或 db/setup.sh，它们含有重建数据库流程。

## 本地检查与下一步
测试：`python -m unittest discover -s tests -v`（在已安装项目依赖的 Python 环境）。测试使用独立内存 SQLite 验证只读 SQL、登录隔离和 HTML/JSON；不能替代 PostgreSQL migration 和结账并发测试。

先与三位队友确认 Users.balance/address、Products.price、Inventory(seller_id, product_id) 和 OrderItems.fulfilled_at。数据库迁移和登录查询已由你验证；原 tutorial 的 wishlist 练习是否完成仍待确认。不要把未完成的 tutorial 或未验证的数据库功能写成已完成。最终由团队把每人的报告合成 REPORT.pdf，并填写 README.txt。
