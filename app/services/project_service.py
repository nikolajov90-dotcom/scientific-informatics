from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.schemas.project import ProjectCreate


async def create_project(
    db: AsyncSession,
    project_data: ProjectCreate,
) -> Project:
    project = Project(
        name=project_data.name,
        description=project_data.description,
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    return project


async def get_project(
    db: AsyncSession,
    project_id: int,
) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))

    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project


async def get_projects(
    db: AsyncSession,
) -> list[Project]:
    result = await db.execute(select(Project))
    return list(result.scalars().all())


async def delete_project(
    db: AsyncSession,
    project_id: int,
) -> None:
    result = await db.execute(delete(Project).where(Project.id == project_id))
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
