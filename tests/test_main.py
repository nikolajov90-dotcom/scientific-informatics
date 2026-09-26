import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/scientific_informatics"
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_test_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = get_test_db


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_root():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Scientific Informatics API"}


@pytest.mark.asyncio
async def test_create_project():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/projects/",
            json={
                "name": "Test project",
                "description": "Test description",
            },
        )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] is not None
    assert data["name"] == "Test project"
    assert data["description"] == "Test description"
    assert data["created_at"] is not None


@pytest.mark.asyncio
async def test_list_projects():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        await client.post(
            "/projects/",
            json={
                "name": "Test project",
                "description": "Test description",
            },
        )

        response = await client.get("/projects/")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "Test project"
    assert data[0]["description"] == "Test description"


@pytest.mark.asyncio
async def test_delete_project():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        create_response = await client.post(
            "/projects/",
            json={
                "name": "Test project",
                "description": "Test description",
            },
        )

        project_id = create_response.json()["id"]

        response = await client.delete(f"/projects/{project_id}")

    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.asyncio
async def test_delete_project_not_found():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.delete("/projects/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}
