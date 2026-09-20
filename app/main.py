from fastapi import FastAPI

from app.api.routes.projects import router as projects_router
from app.db.session import init_db

app = FastAPI()

app.include_router(projects_router)


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/")
async def root():
    return {"message": "Scientific Informatics API"}
