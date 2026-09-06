import os
from aiohttp import web

ROOT = os.path.dirname(os.path.abspath(__file__))

async def arena(request):
    return web.FileResponse(os.path.join(ROOT, "ice_arena.html"))

async def health(request):
    return web.json_response({"ok": True, "service": "ice-arena"})

app = web.Application()
app.router.add_get("/", arena)
app.router.add_get("/ice-arena", arena)
app.router.add_get("/health", health)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
