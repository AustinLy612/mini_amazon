# Milestone 3 team video — 2 minutes 45 seconds

The course requires a video shorter than three minutes, with each responsible member narrating their endpoint. One person can control the browser. Record the actual running application and publish a viewable video link in README.txt before submitting. This script is a recording aid, not the video itself.

Use the seeded database from README.txt. Open `/milestone3`. Keep both a buyer session and a seller session ready in separate browser profiles to avoid spending time logging in during the recording. The JSON URLs use the account ID displayed by the page.

| Time | Presenter | Actions and suggested narration |
| --- | --- | --- |
| 0:00–0:10 | Introduction | “This is our Mini-Amazon Milestone 3 demo. We demonstrate four SQL-backed endpoints and their frontend results.” |
| 0:10–0:45 | Tiancheng Yu — Products | Enter k=2 and click Find products, then change to k=3. Show that the results are descending by price. “The parameterized query limits results using k and breaks ties by product ID. Invalid k is rejected.” Briefly show `/api/products/top?k=3`. |
| 0:45–1:25 | Leyang Han — Users | In the buyer session, select Purchase history, then View order 3. “The user ID is checked against the login session. Our SQL query joins Orders and OrderItems and calculates final total, number of units and fulfillment status, newest first. The detail page uses saved prices and delivery snapshots.” Show `/api/users/3/purchases` in a fresh demo database. |
| 1:25–1:55 | Ziyi Shen — Carts | Select Cart in the buyer session. Show two products/sellers, quantities, unit prices, subtotals and $8.97 total. “These cart lines are stored in PostgreSQL and persist across sessions. Current stock is joined separately, so a removed listing remains visible as unavailable.” Show `/api/users/3/cart`. |
| 1:55–2:30 | Zhiyuan Qi — Sellers | In seller.one's session, open Inventory; search vanilla and click Apply, then reset to show all listings including zero stock. “The inventory SQL filters by the authenticated seller. We include stock, price and product details with pagination.” Show `/api/sellers/1/inventory`, then use seller.two's session to show different inventory. |
| 2:30–2:45 | Closing | In the buyer session request `/api/users/1/purchases` to demonstrate 403. “Private queries cannot read another account's data. All four queries execute SQL and render frontend results. Checkout is not part of this milestone demonstration.” |

Do not spend the recording on source-code scrolling, installation, analytics or final-stage features. Test video sharing with a signed-out viewer before adding its URL to README.txt. Rebuild the package after adding the video link so both README copies agree.
