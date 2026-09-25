"""
Populates content_queue with test data.

Usage:
    python -m scripts.seed_db
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, engine
from app.models.models import Base, ContentQueue, ContentStatus


def seed(n: int = 10):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(ContentQueue).count()
        if existing > 0:
            print(f"content_queue already has {existing} rows; skipping seed.")
            return

        rows = []
        for i in range(1, n + 1):
            # Row 10 is deliberately "future-dated" content -- used in the
            # simulation to prove that a wrongful bulk purge would have wiped
            # out content that hadn't even been posted yet, and that restore
            # brings it back.
            future = i == n
            text = (
                f"Scheduled post #{i}"
                if not future
                else f"FUTURE-DATED post #{i} (scheduled {(datetime.utcnow() + timedelta(days=7)).date()})"
            )
            rows.append(ContentQueue(content_text=text, status=ContentStatus.PENDING))

        db.add_all(rows)
        db.commit()
        print(f"Seeded {n} rows into content_queue.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
