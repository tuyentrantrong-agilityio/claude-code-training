from fastapi import APIRouter

from app.api.v1 import admin, ask, auth, follow_ups, health, home, me, meetings, reports

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(meetings.router)
api_router.include_router(admin.router)
api_router.include_router(reports.router)
api_router.include_router(follow_ups.router)
api_router.include_router(ask.router)
api_router.include_router(home.router)
