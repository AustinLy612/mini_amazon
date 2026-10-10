-- Additive, repeatable Sellers migration for the shared Carts contract.
-- Run after carts_schema.sql (fresh DB) or the reviewed Carts contract migration.
-- No tables, data, balances, prices or snapshots are replaced.
BEGIN;
DO $$
DECLARE
    missing_columns TEXT;
BEGIN
    SELECT string_agg(required.table_name || '.' || required.column_name, ', ')
      INTO missing_columns
      FROM (VALUES
        ('users', 'id'), ('users', 'email'), ('users', 'firstname'), ('users', 'lastname'),
        ('products', 'id'), ('products', 'name'), ('products', 'price'),
        ('inventory', 'seller_id'), ('inventory', 'product_id'), ('inventory', 'quantity'),
        ('orders', 'id'), ('orders', 'buyer_id'), ('orders', 'placed_at'),
        ('orders', 'buyer_name_snapshot'), ('orders', 'shipping_address_snapshot'),
        ('orderitems', 'id'), ('orderitems', 'order_id'), ('orderitems', 'seller_id'),
        ('orderitems', 'product_id'), ('orderitems', 'product_name_snapshot'),
        ('orderitems', 'quantity'), ('orderitems', 'unit_price'), ('orderitems', 'fulfilled_at')
      ) AS required(table_name, column_name)
      WHERE NOT EXISTS (
        SELECT 1 FROM information_schema.columns c
        WHERE c.table_schema = current_schema()
          AND c.table_name = required.table_name AND c.column_name = required.column_name
      );
    IF missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Shared Sellers schema is missing %. Apply/review the Carts contract first.', missing_columns;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS inventory_product_stock_idx
    ON Inventory(product_id, quantity DESC, seller_id);
CREATE INDEX IF NOT EXISTS orderitems_seller_pending_idx
    ON OrderItems(seller_id, order_id, id) WHERE fulfilled_at IS NULL;
COMMIT;
