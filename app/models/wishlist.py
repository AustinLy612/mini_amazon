from flask import current_app as app


class WishlistItem:
    def __init__(self, id, uid, pid, time_added):
        self.id = id
        self.uid = uid
        self.pid = pid
        self.time_added = time_added

    @staticmethod
    def get_all_by_uid(uid):
        rows = app.db.execute("""
SELECT id, uid, pid, time_added
FROM Wishes
WHERE uid = :uid
ORDER BY time_added DESC, id DESC
""", uid=uid)

        return [WishlistItem(*row) for row in rows]
