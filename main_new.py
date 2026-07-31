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

# 간단한 프론트엔드 HTML (닉네임 및 채팅/화면공유 구조 반영)
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>실시간 대시보드</title>
</head>
<body>
    <h2>실시간 대시보드 (WebSocket & WebRTC)</h2>
    <div>
        <label>닉네임: <input type="text" id="nicknameInput" value="누나1"></label>
        <button onclick="connectWebSocket()">접속하기</button>
    </div>
    <hr>
    <div>
        <h3>채팅창</h3>
        <div id="chatLog" style="border:1px solid #ccc; height:150px; overflow-y:scroll; margin-bottom:10px;"></div>
        <input type="text" id="messageInput" placeholder="메시지를 입력하세요..." onkeypress="if(event.key==='Enter') sendMessage()">
        <button onclick="sendMessage()">전송</button>
    </div>

    <script>
        let ws = null;

        function connectWebSocket() {
            const nickname = document.getElementById('nicknameInput').value || "익명";
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
                alert("먼저 접속해주세요!");
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
                # WebRTC 시그널링 메시지 브로드캐스트
                await manager.broadcast(data)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        
    except Exception:
        manager.disconnect(websocket)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
