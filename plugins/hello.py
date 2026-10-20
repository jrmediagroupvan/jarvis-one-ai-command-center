"""Example feature plugin. Add another Python file with register(app)."""
from fastapi import APIRouter

def register(app):
    router = APIRouter(prefix='/api/plugins/hello', tags=['plugin: hello'])
    @router.get('')
    def hello():
        return {'message':'Hello from your custom JARVIS plugin!'}
    app.include_router(router)
