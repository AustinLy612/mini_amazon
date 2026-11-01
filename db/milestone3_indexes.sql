-- Additive and repeatable. Apply after the existing Carts/Sellers schema.
CREATE INDEX IF NOT EXISTS products_price_id_idx ON Products(price DESC, id ASC);
CREATE INDEX IF NOT EXISTS orderitems_order_idx ON OrderItems(order_id);
