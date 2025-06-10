from fastapi import FastAPI
import asyncio
import random
app = FastAPI()

@app.get('/healthz')
def healthz():
    return {'status': 'ok'}

@app.on_event('startup')
async def startup():
    # simulate invoice.paid events
    async def publish():
        while True:
            await asyncio.sleep(5)
            print('invoice.paid', random.randint(1,100))
    asyncio.create_task(publish())
