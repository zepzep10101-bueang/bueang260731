from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List
import json
import uvicorn
import os

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str, sender: WebSocket = None):
        for connection in self.active_connections:
            if sender and connection == sender:
                continue
            await connection.send_text(message)

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <title>행운방 대시보드</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Arial', sans-serif; }
            body, html { width: 100%; height: 100%; overflow-x: hidden; overflow-y: auto; background: #111; }

            .video-background {
                position: fixed;
                top: 0; left: 0; width: 100vw; height: 100vh;
                z-index: -2;
                overflow: hidden;
                pointer-events: none;
                background: black;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .video-background img, .video-background iframe {
                width: 100%;
                height: 100%;
                object-fit: cover;
                border: none;
            }

            .overlay {
                position: fixed;
                top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0, 0, 0, 0.4);
                z-index: -1;
                pointer-events: none;
            }

            .main-container {
                display: grid;
                grid-template-columns: 3fr 1fr;
                gap: 20px;
                padding: 20px;
                min-height: 100vh;
                color: white;
                position: relative;
                z-index: 1;
            }

            .card-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
                gap: 15px;
                align-content: start;
            }

            .timer-card {
                background: rgba(20, 20, 30, 0.85);
                border-radius: 12px;
                padding: 12px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                border: 1px solid rgba(255, 255, 255, 0.25);
                backdrop-filter: blur(5px);
                min-height: 330px;
                position: relative;
                overflow: hidden;
            }

            .card-media-bg {
                position: absolute;
                top: 0; left: 0; width: 100%; height: 100%;
                z-index: 1;
                opacity: 0.4;
                pointer-events: none;
                overflow: hidden;
            }
            .card-media-bg img, .card-media-bg iframe {
                width: 100%;
                height: 100%;
                object-fit: cover;
                position: absolute;
                top: 0; left: 0;
                border: none;
            }

            .card-stream-box {
                width: 100%;
                height: 160px;
                background: rgba(0, 0, 0, 0.7);
                border-radius: 6px;
                overflow: hidden;
                position: relative;
                margin-top: 6px;
                display: flex;
                align-items: center;
                justify-content: center;
                border: 1px solid rgba(255,255,255,0.2);
                z-index: 2;
            }

            .card-memo {
                background: rgba(0, 0, 0, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.3);
                color: white;
                padding: 6px;
                border-radius: 4px;
                font-size: 11px;
                resize: none;
                height: 50px;
                margin-top: 6px;
                position: relative;
                z-index: 2;
                width: 100%;
            }

            .side-panel {
                display: flex;
                flex-direction: column;
                gap: 15px;
            }
            .panel-box {
                background: rgba(30, 30, 40, 0.85);
                border-radius: 12px;
                padding: 15px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                backdrop-filter: blur(5px);
            }
            .chat-box {
                flex-grow: 1;
                display: flex;
                flex-direction: column;
                justify-content: flex-end;
            }
            .chat-input {
                display: flex;
                margin-top: 10px;
            }
            .chat-input input {
                flex-grow: 1;
                padding: 8px;
                border-radius: 4px;
                border: none;
                background: rgba(255, 255, 255, 0.9);
                color: black;
            }
            .chat-input button {
                padding: 8px 15px;
                background: #ff7675;
                border: none;
                color: white;
                border-radius: 4px;
                cursor: pointer;
                margin-left: 5px;
            }
            
            .bg-control {
                display: flex;
                flex-direction: column;
                gap: 8px;
                margin-top: 8px;
            }
            .slider-container {
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 11px;
                color: #ccc;
                margin-top: 4px;
            }
            .slider-container input[type="range"] {
                flex-grow: 1;
            }
        </style>
    </head>
    <body>

        <div class="video-background" id="bgContainer">
            <div id="bgMediaWrapper" style="width:100%; height:100%; display:flex; align-items:center; justify-content:center;"></div>
        </div>
        <div class="overlay"></div>

        <div class="main-container">
            <div class="card-grid" id="cardGrid"></div>

            <div class="side-panel">
                <div class="panel-box">
                    <h3>👑 대시보드</h3>
                    <p style="margin-top:5px; font-size:14px;">현재 접속 인원: <span id="userCount" style="color:#ff7675; font-weight:bold;">1명</span></p>
                </div>

                <div class="panel-box">
                    <h3>🖼️ 배경 변경 (이미지 / GIF / 유튜브)</h3>
                    <div class="bg-control">
                        <div style="font-size: 11px; color: #aaa;">이미지/GIF 업로드:</div>
                        <input type="file" accept="image/*,image/gif" style="font-size:11px;" onchange="uploadMasterBackground(event)">
                        
                        <div style="font-size: 11px; color: #aaa; margin-top: 5px;">유튜브 링크 입력:</div>
                        <div style="display:flex; gap:4px;">
                            <input type="text" id="bgYoutubeInput" placeholder="유튜브 URL 또는 ID" style="flex-grow:1; font-size:11px; padding:4px; background:rgba(255,255,255,0.9); color:black; border:none; border-radius:3px;">
                            <button onclick="setYoutubeBackground()" style="font-size:11px; padding:4px 8px; background:#ff7675; border:none; color:white; border-radius:3px; cursor:pointer;">적용</button>
                        </div>
                        
                        <div class="slider-container">
                            <span>크기:</span>
                            <input type="range" id="bgScaleSlider" min="50" max="250" value="100" oninput="resizeBackground(this.value)">
                            <span id="scaleValue">100%</span>
                        </div>
                    </div>
                </div>

                <div class="panel-box chat-box">
                    <h3>💬 실시간 채팅</h3>
                    <div id="chatHistory" style="height: 180px; overflow-y: auto; margin-top: 10px; font-size: 13px; color: #ddd; line-height: 1.4;">
                        [안내] 대시보드에 연결되었습니다.
                    </div>
                    <div class="chat-input">
                        <input type="text" id="chatInput" placeholder="메시지 입력..." onkeypress="if(event.key==='Enter') sendChat()">
                        <button onclick="sendChat()">전송</button>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let currentScale = 100;
            let ws;
            const cardData = Array.from({length: 8}, (_, i) => ({ id: i+1, user: `누나${i+1}`, memo: '' }));

            function initCards() {
                const grid = document.getElementById('cardGrid');
                grid.innerHTML = '';
                cardData.forEach((card, index) => {
                    grid.innerHTML += `
                        <div class="timer-card">
                            <div class="card-media-bg" id="card-media-${index}"></div>
                            <div style="display:flex; justify-content:space-between; align-items:center; gap:4px; position:relative; z-index:2;">
                                <input type="text" value="${card.user}" style="width:75px; padding:2px; font-size:11px; background:rgba(255,255,255,0.2); border:1px solid rgba(255,255,255,0.4); color:white; border-radius:3px;">
                                <input type="file" accept="image/*,image/gif" style="width:75px; font-size:9px; padding:1px;" onchange="loadCardImage(event, ${index})">
                            </div>
                            <div class="card-stream-box">
                                <span style="font-size:11px; color:#aaa;">화면 미공유 중</span>
                            </div>
                            <div style="position:relative; z-index:2;">
                                <textarea class="card-memo" placeholder="메모 입력란..."></textarea>
                            </div>
                        </div>
                    `;
                });
            }

            function loadCardImage(event, index) {
                const file = event.target.files[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = function(e) {
                    const mediaBg = document.getElementById(`card-media-${index}`);
                    mediaBg.innerHTML = `<img src="${e.target.result}" alt="BG">`;
                };
                reader.readAsDataURL(file);
            }

            function connectWebSocket() {
                const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
                ws = new WebSocket(wsProtocol + window.location.host + "/ws");

                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    if (data.type === "chat") {
                        const history = document.getElementById('chatHistory');
                        history.innerHTML += `<br>${data.msg}`;
                        history.scrollTop = history.scrollHeight;
                    } else if (data.type === "count") {
                        document.getElementById('userCount').innerText = data.count + "명";
                    } else if (data.type === "bg_change") {
                        currentScale = data.scale || 100;
                        const wrapper = document.getElementById('bgMediaWrapper');
                        wrapper.innerHTML = data.mediaHtml;
                        document.getElementById('bgScaleSlider').value = currentScale;
                        document.getElementById('scaleValue').innerText = currentScale + "%";
                        applyScale();
                    } else if (data.type === "bg_resize") {
                        currentScale = data.scale;
                        document.getElementById('bgScaleSlider').value = currentScale;
                        document.getElementById('scaleValue').innerText = currentScale + "%";
                        applyScale();
                    }
                };

                ws.onclose = function() {
                    setTimeout(connectWebSocket, 2000);
                };
            }

            function applyScale() {
                const wrapper = document.getElementById('bgMediaWrapper');
                if (wrapper) wrapper.style.transform = `scale(${currentScale / 100})`;
            }

            function sendChat() {
                const input = document.getElementById('chatInput');
                if (!input.value.trim()) return;
                ws.send(JSON.stringify({ type: "chat", msg: input.value }));
                input.value = '';
            }

            function uploadMasterBackground(event) {
                const file = event.target.files[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = function(e) {
                    const scale = document.getElementById('bgScaleSlider').value;
                    const mediaHtml = `<img src="${e.target.result}" alt="Background">`;
                    ws.send(JSON.stringify({ type: "bg_change", mediaHtml: mediaHtml, scale: scale }));
                };
                reader.readAsDataURL(file);
            }

            function setYoutubeBackground() {
                const inputVal = document.getElementById('bgYoutubeInput').value.trim();
                if (!inputVal) return;
                
                let videoId = inputVal;
                if (inputVal.includes('youtube.com') || inputVal.includes('youtu.be')) {
                    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
                    const match = inputVal.match(regExp);
                    if (match && match[2].length === 11) {
                        videoId = match[2];
                    }
                }

                const scale = document.getElementById('bgScaleSlider').value;
                const mediaHtml = `<iframe src="https://www.youtube.com/embed/${videoId}?autoplay=1&mute=1&loop=1&playlist=${videoId}" allow="autoplay; encrypted-media" allowfullscreen></iframe>`;
                ws.send(JSON.stringify({ type: "bg_change", mediaHtml: mediaHtml, scale: scale }));
            }

            function resizeBackground(scale) {
                currentScale = scale;
                document.getElementById('scaleValue').innerText = scale + "%";
                applyScale();
                ws.send(JSON.stringify({ type: "bg_resize", scale: scale }));
            }

            initCards();
            connectWebSocket();
        </script>
    </body>
    </html>
    """

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    await manager.broadcast(json.dumps({"type": "count", "count": len(manager.active_connections)}))
    
    try:
        while True:
            data = await websocket.receive_text()
            packet = json.loads(data)
            p_type = packet.get("type")

            if p_type == "chat":
                msg_text = packet.get('msg')
                for conn in manager.active_connections:
                    if conn == websocket:
                        await conn.send_text(json.dumps({"type": "chat", "msg": f"나: {msg_text}"}))
                    else:
                        await conn.send_text(json.dumps({"type": "chat", "msg": f"상대방: {msg_text}"}))
            elif p_type in ["bg_change", "bg_resize"]:
                await manager.broadcast(json.dumps(packet))
                await websocket.send_text(json.dumps(packet))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(json.dumps({"type": "count", "count": len(manager.active_connections)}))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main_new:app", host="0.0.0.0", port=port)
