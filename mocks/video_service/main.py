from fastapi import FastAPI
app = FastAPI()

@app.get('/videos/{video_id}')
def get_video(video_id: str):
    return {'id': video_id, 'title': 'Mock Video'}

@app.get('/healthz')
def healthz():
    return {'status': 'ok'}
