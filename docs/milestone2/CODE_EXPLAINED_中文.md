# 从网页到数据库：你的 Milestone 2 代码讲解

## 1. 先分清这次交的东西

Milestone 2 主要考设计：你需要说明购物车和订单需要哪些数据、表之间如何关联、用户会看到哪些页面。完整的加购物车/付款功能不是本次必做代码。

另外，所有成员要做 Wishlist tutorial，目的是学会这个网站的开发方式。Wishlist 是收藏夹，不是购物车：收藏只说“感兴趣”；购物车要确定卖家和数量；订单才表示已按最终价格买下。

现在能操作的是 Wishlist；Cart 能查看但还不能编辑或结账。设计报告写了未来流程，不等于那些功能已实现。

## 2. 点击按钮后，究竟发生了什么

```text
浏览器首页的 Add to Wishlist 按钮
→ POST /wishlist/add/1
→ app/wishlist.py：确认登录、检查表单
→ app/models/wishlist.py：执行 INSERT SQL
→ PostgreSQL 的 Wishes 表新增一行
→ 路由让浏览器转到 /wishlist
→ SELECT 查询当前用户的记录
→ wishlist.html 把记录变成表格
```

分层的原因：HTML 管显示；路由管请求、登录身份和页面选择；model 管 SQL；数据库保存真实数据并检查约束。这样改页面外观不需要同时重写 SQL。

## 3. Tutorial 的每个文件

### db/wishlist_schema.sql 与 db/data/Wishes.csv

Wishes 的 id 是每条收藏的编号；uid 是收藏者；pid 是商品；time_added 是时间。uid/pid 是外键，必须对应真实用户/商品。不是把商品复制一份，而是存它的编号。

CSV 是固定示例数据。db/create.sql 包含建表脚本；db/load.sql 导入 CSV 并调整自动编号，避免新增记录和已有编号冲突。SQL 文件是创建结构的说明，不是数据库本身；修改文件不会自动修改已经存在的数据库。

### app/models/wishlist.py

`WishlistItem` 用一个 Python 对象表示一条查询结果。`__init__` 给对象装入四个字段。`@staticmethod` 表示可以直接调用类上的操作，无须先手动创建某条收藏对象。

`get_all_by_uid(uid)`：WHERE uid=:uid 限定一个用户，ORDER BY time_added DESC, id DESC 让最新记录在前；时间一样时用 id 排序。

`[WishlistItem(*row) for row in rows]` 把每行四个值展开，变成一个 WishlistItem 对象。

`add(uid, pid)`：INSERT ... SELECT 从真实 Products 行生成收藏；不存在的商品不插入，返回 None，路由响应 404。RETURNING id 把数据库分配的新编号交还 Python。`:uid`、`:pid` 是参数绑定，不能改成字符串拼接 SQL。

之前错误的原因：add 被缩进到 get_all_by_uid 里面，类上没有可正常调用的 add；查询又过早返回 rows[0][0]，不再返回收藏对象列表，空列表还会报错。现在两个方法是同级，各自有自己的 return。

按原 tutorial 的简化规则，同一商品可以多次收藏。本次没有额外加唯一约束；这个行为有测试记录。实际产品未来可改成一人一商品一条。

### app/wishlist.py

`Blueprint` 是一组网址的集合。app/__init__.py 的 register_blueprint 把它接入 Flask；写了函数却不注册，浏览器找不到网址。

`@login_required`：未登录先去登录。`current_user.id`：从已验证的登录会话取身份，不信任表单里用户自行填写的 uid。否则别人改一个数字就能替你操作。

`GET /wishlist`：查询后 render_template 输出 HTML。`GET /api/wishlist`：同样数据返回 JSON，便于调试。JSON 是结构化数据，不是漂亮网页。

`POST /wishlist/add/<int:product_id>`：只让 POST 修改数据，URL 中的数字交给函数。WishlistForm 使用已有 Flask-WTF 的 CSRF token，阻止外部网站诱使已登录用户偷偷提交表单。失败返回 400，不存在的商品返回 404。

成功后 redirect 到列表。这样刷新列表不会自动重做上一次 POST；但这不是防止双击重复添加的完整机制，教程仍允许重复收藏。

`humanize_time` 把 UTC 时间转换为“几分钟前”。旧 Wishes 表存 UTC-naive 时间，因此先明确赋予 UTC，再与当前 UTC 比较，避免把纽约本地时间错当 UTC。humanize 依赖记在 pyproject.toml，队友通过 Poetry 安装。

### app/index.py 与三个模板

index.py 给首页提供 WishlistForm。index.html 为每个商品生成一个 POST form，action 带该商品编号；hidden_tag() 输出 CSRF 隐藏字段。只有登录用户看到按钮。

wishlist.html 继承 base.html；for 循环输出每条收藏；空列表有明确提示。base.html 增加 Wishlist 导航，所有继承它的页面一起获得导航。

Jinja 的 `{{ ... }}` 默认转义 HTML，避免商品名中的尖括号被当成代码执行。不要随意加 `|safe`。

## 4. Carts 数据库设计：为什么需要三张表

以“买家 0 向卖家 8 买 2 件商品 1”为例：

| 表 | 保存什么 | 为什么 |
|---|---|---|
| CartItems | buyer_id=0, seller_id=8, product_id=1, quantity=2 | 下次登录仍能找回；同商品不同卖家分开 |
| Orders | 订单编号、买家、下单时间、收货姓名/地址 | 一次结账是一张订单，有共同信息 |
| OrderItems | 订单编号、卖家、商品、数量、成交单价、商品名、履约时间 | 一个订单可含多个商品/卖家；每行分别履约 |

CartItems 复合主键 (buyer_id,seller_id,product_id)：这三个编号一起才能唯一确定一行。若只用 product_id，所有用户买同商品会冲突；若少了 seller_id，两个卖家会混在一起。空购物车等于零行，不需要每人额外建一个空表或空记录。

Orders/OrderItems 分开：否则每条商品都重复订单时间和地址，容易出现同一订单的地址不一致。

购物车不存成交价格，显示 Products.price；因为下单前价格可能变化。OrderItems.unit_price 存最终单价，商品后来涨价不会改变历史订单。商品名、收货信息也保存快照。

字段名与队友一致：buyer_name_snapshot、shipping_address_snapshot、product_name_snapshot；OrderItems 采用 id 主键，加 UNIQUE(order_id,product_id,seller_id)。

fulfilled_at 为 NULL 表示待履约，非 NULL 表示履约时间。订单总价 = 每行 quantity×unit_price 相加；整单完成 = 至少一行且所有行已履约。推导结果无需重复保存，避免两个地方不一致。

quantity>0 是 CHECK；余额和库存>=0 是 CHECK。外键保证存在对应用户/商品/库存。库存够不够属于涉及其他表的业务检查，不能简单写成跨表 CHECK；需要结账事务重新判断。

Inventory、Users.balance/address 和 Products 的价格约束是共享设计，必须与对应组员统一后合并。db/carts_schema.sql 是一次性增量草案，不是每次启动都执行的程序。

## 5. 已实现的购物车查询

### app/models/cart.py

Cart.get_items(buyer_id) 的 SQL JOIN 连接 CartItems、Products、Users 和 Inventory：分别取得数量、商品名/实时单价、卖家姓名、库存和上架状态。WHERE 只查指定买家。

Products、Users 使用 INNER JOIN；Inventory 使用 LEFT JOIN。按照组员最新设计，库存记录可以删除，购物车没有指向 Inventory 的外键，缺失库存显示数量 0 且不可购买。查询不依赖 active 或 Products.available。

每行 subtotal = Decimal 单价 × 数量；Cart.total 把小计相加。使用 Decimal 是为了避免浮点数金额误差。JSON 把金额输出为两位小数字符串，客户端不会把精确金额误当浮点。

### app/carts.py 与 cart.html

/cart 返回 HTML，/api/cart 返回 JSON；身份来自 current_user.id。用户即使加 ?buyer_id=其他人 也不能查询别人购物车。

cart.html 循环显示商品、卖家、数量、单价、小计、库存状态和总价。停售或缺货行仍保留，让用户知道发生了什么；当前总价包含这些购物车行，属于展示估计，未来结账会拒绝无效库存。

页面明确写了 read-only prototype，所以现在没有修改数量、删除、结账按钮。不能把测试通过说成完整购物车付款功能已完成。

## 6. 为什么结账必须是一个事务（目前是设计）

例子：一共 20 元，买家扣 20，卖家加 20，库存扣 2，生成订单，清空购物车。这些必须全部成功，或全部不发生。否则可能扣钱了却没有订单。

未来实现用同一个 `with app.db.engine.begin() as conn:`；不能调用五次 app.db.execute，因为每次会分别提交，无法整体回滚。

锁和重新检查用于防止两人同时买最后一件商品。全部相关模块采用一致锁顺序，以减少死锁。遇到 SERIALIZABLE 冲突时重试完整事务；价格变了则让买家重新确认。下单后库存已扣，卖家发货时只能更新履约状态，不能再扣一次。

## 7. 测试告诉我们什么

- test_cart.py 的七项：访客、用户隔离/金额、HTML 转义/缺货、空车、重新登录、SQL 参数绑定、库存删除后购物车仍可见。
- test_wishlist.py 的四项：真实登录添加查看退出、CSRF/错误商品/HTTP 方法、访客限制、重复添加和排序。
- postgres_smoke.py：在独立 PostgreSQL 验证库中跑同样主流程，检查真实建表与约束、重新创建应用后仍能读取数据。

SQLite 测试快且独立，但不能证明 PostgreSQL 的锁和事务并发行为。PostgreSQL smoke 也没有验证未来尚未实现的结账，报告明确了这个边界。

## 8. 你向老师解释时可以这样说

“我负责购物车和订单。M2 我设计了 CartItems、Orders、OrderItems。购物车保存用户选的卖家/商品/数量，价格实时读取；订单保存成交价格和收货信息快照，避免以后修改影响历史。结账设计成一个事务。页面流是商品详情 → 购物车 → 确认 → 订单详情。我也完成了 tutorial 的收藏夹读写流程，并实现了只读购物车原型。”

接着自己指出一条 SQL、一个路由和一个 HTML 循环，解释它们如何连接。若尚未理解事务，不要背一句“用了事务就安全”；用扣款/库存/订单必须同时成功的例子讲清楚。
