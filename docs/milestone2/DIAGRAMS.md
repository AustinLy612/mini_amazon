# Cart / Order diagrams (proposed design)

## Relationships
```mermaid
erDiagram
    Users ||--o{ Orders : places
    Users ||--o{ Inventory : sells
    Products ||--o{ Inventory : lists
    Users ||--o{ CartItems : owns
    Inventory ||--o{ CartItems : references
    Orders ||--|{ OrderItems : contains
    Users ||--o{ OrderItems : fulfills
    Products ||--o{ OrderItems : identifies
```
Every order contains at least one item by checkout application logic, not by an ordinary foreign key alone. Inventory uses (seller_id, product_id); CartItems uses (buyer_id, seller_id, product_id); OrderItems uses (order_id, seller_id, product_id). Empty carts have no rows. OrderItems does not depend on live Inventory. All nullable/required fields and checks are specified in CARTS_DESIGN.md and db/carts_schema.sql.

## Planned navigation
```mermaid
flowchart TD
    P[Product detail: select seller and quantity] --> C[Cart: review, update, remove]
    C --> R[Checkout confirmation: price, balance, address]
    R --> T{Transaction succeeds?}
    T -->|yes| O[Order detail: fixed prices and fulfillment]
    T -->|no| R
    H[Purchase history] --> O
    S[Seller orders: fulfill owned lines] --> O
```
The seller link above indicates that fulfillment updates the buyer's status; sellers do not enter the buyer-only detail page. Guests must log in before cart/checkout; all mutations are authenticated POSTs with CSRF checks. Only the cart read page is implemented today.
