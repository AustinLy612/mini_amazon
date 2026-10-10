# Sellers 运行与交接

## 当前代码与完成范围

这份 Sellers 实现基于小组仓库的 `ziyi-carts-milestone2` 分支
（`a80a10f6f9142e5af2c74ee5e794ba38baf3abc8`）。截至 2026-10-10，
`main` 仍是 skeleton；实际的 Cart/Wishlist 代码在这个队友分支。
Sellers 使用它已有的表和登录流程，保留队友的实现。

| 页面 | 已实现的功能 |
|---|---|
| `/seller` | 销售额、销量、库存、缺货、待履约统计；最近 30 天销售图和畅销商品 |
| `/seller/inventory` | 只管理自己的库存；搜索、排序、分页；改数量、下架；零库存状态 |
| `/seller/inventory/add` | 从共享商品目录选择商品并上架；同一卖家不能重复上架同一商品 |
| `/seller/orders` | 最新订单优先；按订单、买家、地址、自己的商品搜索；按履约状态过滤 |
| `/seller/orders/<id>` | 买家姓名、邮箱、下单时地址；只显示自己的商品、数量、小计和履约时间 |

所有写操作需要登录和 CSRF token，身份取自登录 session。
库存更新和下架会检查打开页面时的数量，避免覆盖期间发生的扣库存。
履约只改自己的 `OrderItems.fulfilled_at`；重复点击保留原时间。
销售额使用下单快照价格，日期按 UTC 显示。

## 在课程 PostgreSQL 环境运行

### 新建独立开发数据库

先切到 Sellers 分支并安装已有依赖：

```bash
git fetch origin
git switch codex/sellers-inventory-fulfillment
poetry install --no-root
```

准备 PostgreSQL 连接配置。脚本读取当前 `.flaskenv` 中的
`DB_HOST / DB_PORT / DB_USER / DB_PASSWORD`，也支持课程提供的
`PGHOST / PGPORT / PGUSER / PGPASSWORD` 环境变量。
连接用户需要创建新数据库的权限。

```bash
poetry run python tools/setup_sellers.py --database mini_amazon_sellers_dev --demo
```

该命令创建全新的数据库，加载 skeleton 小数据、共享 Carts schema、
Sellers 索引和可选演示数据。如果同名数据库已存在，会退出且不修改任何数据；
换一个新名字即可。初始化失败时 schema 事务回滚，新建数据库留作检查。

没有 `.flaskenv` 时，脚本会生成本地配置和随机 `SECRET_KEY`；已有配置会保留。
已有配置时，把其中 `DB_NAME` 改为刚创建的数据库名，再启动：

```bash
poetry run flask run --host 0.0.0.0 --port 8080
```

打开 `http://localhost:8080/login`，登录后点击 **Seller center**。
课程 OIT 容器使用其已有的网站访问地址或 VSCode 的 8080 端口转发。

### 使用已经有数据的小组数据库

确认 `Inventory / Orders / OrderItems` 已与
[共享数据约定](INTEGRATION.md)一致，然后只应用 Sellers 的增量迁移：

```bash
psql -v ON_ERROR_STOP=1 -d YOUR_SHARED_DATABASE -f db/sellers_schema.sql
```

请把 `YOUR_SHARED_DATABASE` 换为网站实际的 `DB_NAME`，并使用对应服务器和用户。
这个迁移检查必要列并添加两个索引，可以重复执行，不替换表和数据。
旧版 Carts schema 的迁移仍按队友说明评审处理。

`install.sh` 和 `db/setup.sh` 会重建 skeleton 数据库，已有小组数据时不要用它们
来更新 Sellers。`.flaskenv`、数据库密码、`.venv` 和 `.validation` 都不会提交。

## 演示与验收

只有使用 `--demo` 创建的开发库才有以下合成账号：

| 角色 | 邮箱 | 密码 |
|---|---|---|
| 卖家一 | `seller.one@example.com` | `SellerDemo2026!` |
| 卖家二 | `seller.two@example.com` | `SellerDemo2026!` |
| 买家 | `buyer.demo@example.com` | `SellerDemo2026!` |

演示订单是初始化脚本生成的合成数据，不能当作已完成的结账功能。
数据库只保存账号密码的 hash。演示账号仅用于开发和课程演示。

建议按下面顺序演示你的模块：

1. 卖家一登录，打开 Overview，解释销售额和待履约统计。
2. 上架一个商品，修改数量，再把数量设为 0，展示缺货状态和搜索。
3. 打开一个含两个卖家的订单，说明页面金额只包括自己卖出的商品。
4. 标记自己的商品履约：自己的状态改变，整个订单仍等待另一位卖家。
5. 切到卖家二履约，展示整个订单状态变为 Fulfilled。
6. 下架已有商品，再以买家身份查看 Cart：条目保留，显示不可购买。

执行自动化检查：

```bash
poetry run python -m unittest discover -s tests -v
```

默认执行 31 项快速集成检查，另外 10 项真实 PostgreSQL 检查需要独立验证库。
完整命令与结果见 [VALIDATION.md](VALIDATION.md)。

## 队友需要接上的地方

| 模块负责人 | 与 Sellers 的接口 |
|---|---|
| Users | 保持 `current_user.id` 和登录流程；当前可兼任买家和卖家。未来加入 `is_seller` 时统一角色准入规则 |
| Products | 保持 `Products.id / name / price`；创建商品后它会出现在上架目录。商品详情可读取公开卖家接口 |
| Carts/Orders | 读取 `Inventory.quantity`；结账创建 `Orders` 和 `OrderItems` 快照；读取 `fulfilled_at` 给买家显示履约状态 |

公开接口 `GET /api/sellers/products/<product_id>` 返回这个商品的卖家及库存，
不含邮箱、地址、余额或订单。买家是否可购买应看实际库存，而非 skeleton
遗留的 `Products.available`。

结账需要在**一个事务**里校验库存和余额、扣库存、转余额、保存订单快照和清空购物车。
Sellers 履约不会再次扣库存或转钱。明细不能通过外键绑定当前 Inventory，
否则下架会破坏购物车和历史订单。这些约定及请求格式见 [INTEGRATION.md](INTEGRATION.md)。

当前队友的 Cart 仍是只读原型，完整结账和最终 Users/Products 模块还未上传到这份基础代码。
因此 Sellers 已可独立运行和验收；小组最终网站的真实购买流程需要那些模块合并后再联调。

合并时先让小组评审 Carts 分支，再评审 Sellers 的增量变更。
若 Carts 已合并到 `main`，可以把 Sellers PR 的目标分支改为 `main`；
如果 Carts 用 squash 合并，先整理分支基线，避免把 Carts 的历史重复带进 PR。
