import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force a throwaway sqlite DB before any app module is imported, so
# app.core.config / app.core.database pick it up.
os.environ["DATABASE_URL"] = "sqlite:///./test_harness.db"
os.environ["TRUST_THRESHOLD"] = "2"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.models.models import Base, ContentQueue, ContentStatus

TEST_DB_URL = "sqlite:///./test_harness.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    for i in range(1, 6):
        session.add(ContentQueue(content_text=f"Post {i}", status=ContentStatus.PENDING))
    session.commit()
    session.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    with TestClient(app) as c:
        yield c
