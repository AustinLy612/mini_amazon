-- Optional fixture for the SMALL skeleton database only. No money is transferred.
-- Existing seller/cart rows are preserved. Re-running does not add quantities.
BEGIN;
INSERT INTO Users(email, password, firstname, lastname)
SELECT 'cart-seller@example.test', password, 'Demo', 'Seller'
FROM Users WHERE id = 0
ON CONFLICT (email) DO NOTHING;
INSERT INTO Inventory(seller_id, product_id, quantity)
SELECT u.id, p.id, 10 FROM Users u CROSS JOIN Products p
WHERE u.email = 'cart-seller@example.test' AND p.id IN (1, 2)
ON CONFLICT DO NOTHING;
INSERT INTO CartItems(buyer_id, seller_id, product_id, quantity)
SELECT 0, seller_id, product_id, 2 FROM Inventory
WHERE seller_id = (SELECT id FROM Users WHERE email = 'cart-seller@example.test')
AND product_id IN (1, 2) AND EXISTS (SELECT 1 FROM Users WHERE id = 0)
ON CONFLICT DO NOTHING;
COMMIT;
