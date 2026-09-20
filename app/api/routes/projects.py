from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.project import ProjectCreate
from app.services.project_service import create_project, delete_project, get_projects

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_project_endpoint(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await create_project(db, project_data)


@router.get("/")
async def get_projects_endpoint(
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await get_projects(db)


@router.delete("/{project_id}")
async def delete_project_endpoint(
    project_id: int,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    return await delete_project(db, project_id)
