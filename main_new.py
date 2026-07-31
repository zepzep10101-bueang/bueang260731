import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        # WebSocket 객체와 닉네임을 딕셔너리로 관리
        self.active_connections: dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, nickname: str):
        await websocket.accept()
        self.active_connections[websocket] = nickname

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

# 누나의 기존 대시보드 UI (배경 유튜브, GIF, 화면 공유 + 닉네임 연동 반영)
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>실시간 대시보드</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            font-family: Arial, sans-serif;
            color: white;
            background-color: #111;
        }
        /* 배경 유튜브 및 GIF 영역 스타일 예시 */
        #bg-container {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            z-index: -1;
            overflow: hidden;
            opacity: 0.6;
        }
        .dashboard-box {
            background: rgba(0, 0, 0, 0.7);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        #chatLog {
            border: 1px solid #555;
            height: 150px;
            overflow-y: scroll;
            margin-bottom: 10px;
            padding: 10px;
            background: rgba(0, 0, 0, 0.5);
        }
    </style>
</head>
<body>
    <!-- 배경 유튜브 / GIF 영역 -->
    <div id="bg-container">
        <!-- 예시 GIF 또는 유튜브 배경 요소 -->
        <img src="https://media.giphy.com/media/3oK7LdBx2uGkPKnZm0/giphy.gif" style="width:100%; height:100%; object-fit:cover;" alt="background gif">
    </div>

    <h2>실시간 대시보드 (WebSocket & WebRTC)</h2>
    
    <div class="dashboard-box">
        <label>닉네임: <input type="text" id="nicknameInput" value="누나1"></label>
        <button onclick="connectWebSocket()">접속하기</button>
    </div>

    <div class="dashboard-box">
        <h3>채팅창</h3>
        <div id="chatLog"></div>
        <input type="text" id="messageInput" placeholder="메시지를 입력하세요..." style="width: 70%; padding: 5px;" onkeypress="if(event.key==='Enter') sendMessage()">
        <button onclick="sendMessage()" style="padding: 5px 15px;">전송</button>
    </div>

    <div class="dashboard-box">
        <h3>화면 공유 영역</h3>
        <video id="screenVideo" autoplay playsinline style="width: 100%; max-width: 400px; background: #000;"></video>
        <button onclick="startScreenShare()">화면 공유 시작</button>
    </div>

    <script>
        let ws = null;
        let localStream = null;

        function connectWebSocket() {
            const nickname = document.getElementById('nicknameInput').value || "누나1";
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${location.host}/ws?nickname=${encodeURIComponent(nickname)}`);

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                const chatLog = document.getElementById('chatLog');
                
                if (data.type === 'chat') {
                    chatLog.innerHTML += `<div><b>${data.sender}</b>: ${data.msg}</div>`;
                    chatLog.scrollTop = chatLog.scrollHeight;
                }
            };

            ws.onopen = function() {
                alert("웹소켓 연결 성공!");
            };

            ws.onclose = function() {
                alert("웹소켓 연결이 끊어졌습니다.");
            };
        }

        function sendMessage() {
            if (!ws || ws.readyState !== WebSocket.OPEN) {
                alert("먼저 접속하기 버튼을 눌러주세요!");
                return;
            }
            const input = document.getElementById('messageInput');
            if (!input.value.trim()) return;

            ws.send(JSON.stringify({
                type: "chat",
                msg: input.value
            }));
            input.value = "";
        }

        async function startScreenShare() {
            try {
                localStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
                const videoElement = document.getElementById('screenVideo');
                videoElement.srcObject = localStream;
            } catch (err) {
                console.error("화면 공유 실패:", err);
            }
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get():
    return HTML_CONTENT

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, nickname: str = "누나1"):
    await manager.connect(websocket, nickname)
    try:
        while True:
            data = await websocket.receive_text()
            packet = json.loads(data)
            p_type = packet.get("type")

            if p_type == "chat":
                current_nickname = manager.active_connections.get(websocket, nickname)
                msg_text = packet.get("msg")
                
                response_data = json.dumps({
                    "type": "chat",
                    "sender": current_nickname,
                    "msg": msg_text
                })
                await manager.broadcast(response_data)
                
            elif p_type in ["offer", "answer", "candidate"]:
                await manager.broadcast(data)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main_new:app", host="0.0.0.0", port=port, reload=True)
