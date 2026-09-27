from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.annotation_file import AnnotationFile
from app.models.variant import Variant
from app.models.vcf_file import VCFFile

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


@pytest.mark.asyncio
async def test_upload_vcf():
    transport = ASGITransport(app=app)

    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
2\t121746135\t.\tC\tT\t100\tPASS\tAF=0.5
"""

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        create_response = await client.post(
            "/projects/",
            json={
                "name": "VCF test project",
                "description": "Project for VCF upload test",
            },
        )

        project_id = create_response.json()["id"]

        response = await client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "test.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["project_id"] == project_id
    assert data["vcf_id"] is not None
    assert data["filename"] == "test.vcf"
    assert data["path"] == "uploads/test.vcf"

    async with TestSessionLocal() as session:
        result = await session.execute(
            select(VCFFile).where(VCFFile.id == data["vcf_id"])
        )
        vcf_file = result.scalar_one()

        assert vcf_file.project_id == project_id
        assert vcf_file.filename == "test.vcf"

        result = await session.execute(
            select(Variant).where(Variant.vcf_file_id == data["vcf_id"])
        )
        db_variants = list(result.scalars().all())

    assert len(db_variants) == 1
    assert db_variants[0].chrom == "2"
    assert db_variants[0].pos == 121746135
    assert db_variants[0].ref == "C"
    assert db_variants[0].alt == "T"
    assert db_variants[0].af == 0.5


@pytest.mark.asyncio
async def test_upload_vcf_project_not_found():
    transport = ASGITransport(app=app)

    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
2\t121746135\t.\tC\tT\t100\tPASS\tAF=0.5
"""

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/projects/999999/vcf/",
            files={
                "file": (
                    "test.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


@pytest.mark.asyncio
async def test_upload_vcf_invalid_extension():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        create_response = await client.post(
            "/projects/",
            json={
                "name": "Invalid VCF test project",
                "description": "Project for invalid extension test",
            },
        )

        project_id = create_response.json()["id"]

        response = await client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "test.txt",
                    "This is not a VCF file.",
                    "text/plain",
                )
            },
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid VCF file extension"}


@pytest.mark.asyncio
async def test_list_vcf_files():
    transport = ASGITransport(app=app)

    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
2\t121746135\t.\tC\tT\t100\tPASS\tAF=0.5
"""

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        create_response = await client.post(
            "/projects/",
            json={
                "name": "VCF list test project",
                "description": "Project for VCF list test",
            },
        )

        project_id = create_response.json()["id"]

        await client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "test.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

        response = await client.get(f"/projects/{project_id}/vcf/")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["filename"] == "test.vcf"


@pytest.mark.asyncio
async def test_get_vcf():
    transport = ASGITransport(app=app)

    vcf_content = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
2\t121746135\t.\tC\tT\t100\tPASS\tAF=0.5
"""

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        create_response = await client.post(
            "/projects/",
            json={
                "name": "VCF get test project",
                "description": "Project for VCF get test",
            },
        )

        project_id = create_response.json()["id"]

        upload_response = await client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "test.vcf",
                    vcf_content,
                    "text/plain",
                )
            },
        )

        vcf_id = upload_response.json()["vcf_id"]

        response = await client.get(f"/projects/{project_id}/vcf/{vcf_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == vcf_id
    assert data["filename"] == "test.vcf"

    assert len(data["variants"]) == 1

    variant = data["variants"][0]

    assert variant["chrom"] == "2"
    assert variant["pos"] == 121746135
    assert variant["ref"] == "C"
    assert variant["alt"] == "T"
    assert variant["qual"] == 100.0
    assert variant["filter"] == "PASS"
    assert variant["af"] == 0.5


@pytest.mark.asyncio
async def test_delete_vcf():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        project_response = await client.post(
            "/projects/",
            json={
                "name": "Test project",
                "description": "Test description",
            },
        )

        project_id = project_response.json()["id"]

        vcf_content = (
            "##fileformat=VCFv4.2\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
            "2\t121746135\t.\tC\tT\t100\tPASS\tAF=0.5\n"
        )

        files = {
            "file": ("test.vcf", vcf_content, "text/plain"),
        }

        upload_response = await client.post(
            f"/projects/{project_id}/vcf/",
            files=files,
        )

        vcf_id = upload_response.json()["vcf_id"]

        file_path = Path("uploads/test.vcf")
        assert file_path.exists()

        delete_response = await client.delete(f"/projects/{project_id}/vcf/{vcf_id}")

        assert delete_response.status_code == 204
        assert not file_path.exists()

    async with TestSessionLocal() as session:
        vcf_result = await session.execute(select(VCFFile).where(VCFFile.id == vcf_id))
        assert vcf_result.scalar_one_or_none() is None

        variant_result = await session.execute(
            select(Variant).where(Variant.vcf_file_id == vcf_id)
        )
        assert variant_result.scalars().all() == []


@pytest.mark.asyncio
async def test_upload_annotation():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        project_response = await client.post(
            "/projects/",
            json={
                "name": "Test project",
                "description": "Test description",
            },
        )

        project_id = project_response.json()["id"]

        annotation_content = (
            "#VariantID\tType\tName\tGeneID\tGeneSymbol\t"
            "ClinicalSignificance\tRS_dbSNP\tChromosome\tStart\tStop\t"
            "ReferenceAllele\tAlternateAllele\n"
            "123456\tSNV\tTP53\t7157\tTP53\tPathogenic\t"
            "12345\t2\t121746135\t121746135\tC\tT\n"
        )

        files = {
            "file": (
                "clinvar.tsv",
                annotation_content,
                "text/tab-separated-values",
            ),
        }

        response = await client.post(
            f"/projects/{project_id}/annotation/",
            files=files,
        )

        assert response.status_code == 200

        data = response.json()

        assert data["project_id"] == project_id
        assert data["filename"] == "clinvar.tsv"
        assert "annotation_id" in data


@pytest.mark.asyncio
async def test_upload_invalid_annotation():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        project_response = await client.post(
            "/projects/",
            json={
                "name": "Test project",
                "description": "Test description",
            },
        )

        project_id = project_response.json()["id"]

        invalid_content = "wrong\tclinvar\theader\n123\tSNV\tTP53\n"

        files = {
            "file": (
                "invalid.tsv",
                invalid_content,
                "text/tab-separated-values",
            ),
        }

        response = await client.post(
            f"/projects/{project_id}/annotation/",
            files=files,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == ("Invalid ClinVar annotation format")

        assert not Path("uploads/invalid.tsv").exists()


@pytest.mark.asyncio
async def test_list_annotation_files():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        project_response = await client.post(
            "/projects/",
            json={
                "name": "Test project",
                "description": "Test description",
            },
        )

        project_id = project_response.json()["id"]

        annotation_content = (
            "#VariantID\tType\tName\tGeneID\tGeneSymbol\t"
            "ClinicalSignificance\tRS_dbSNP\tChromosome\tStart\tStop\t"
            "ReferenceAllele\tAlternateAllele\n"
            "123456\tSNV\tTP53\t7157\tTP53\tPathogenic\t"
            "12345\t2\t121746135\t121746135\tC\tT\n"
        )

        files = {
            "file": (
                "clinvar.tsv",
                annotation_content,
                "text/tab-separated-values",
            ),
        }

        upload_response = await client.post(
            f"/projects/{project_id}/annotation/",
            files=files,
        )

        assert upload_response.status_code == 200

        response = await client.get(f"/projects/{project_id}/annotation/")

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 1
        assert data[0]["filename"] == "clinvar.tsv"


@pytest.mark.asyncio
async def test_delete_annotation():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        project_response = await client.post(
            "/projects/",
            json={
                "name": "Test project",
                "description": "Test description",
            },
        )

        project_id = project_response.json()["id"]

        annotation_content = (
            "#VariantID\tType\tName\tGeneID\tGeneSymbol\t"
            "ClinicalSignificance\tRS_dbSNP\tChromosome\tStart\tStop\t"
            "ReferenceAllele\tAlternateAllele\n"
            "123456\tSNV\tTP53\t7157\tTP53\tPathogenic\t"
            "12345\t2\t121746135\t121746135\tC\tT\n"
        )

        files = {
            "file": (
                "clinvar.tsv",
                annotation_content,
                "text/tab-separated-values",
            ),
        }

        upload_response = await client.post(
            f"/projects/{project_id}/annotation/",
            files=files,
        )

        annotation_id = upload_response.json()["annotation_id"]

        file_path = Path("uploads/clinvar.tsv")
        assert file_path.exists()

        delete_response = await client.delete(
            f"/projects/{project_id}/annotation/{annotation_id}"
        )

        assert delete_response.status_code == 204
        assert not file_path.exists()

    async with TestSessionLocal() as session:
        result = await session.execute(
            select(AnnotationFile).where(AnnotationFile.id == annotation_id)
        )

        assert result.scalar_one_or_none() is None
