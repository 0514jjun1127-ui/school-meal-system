import serial
import requests
import time

# ⚠️ 본인의 아두이노 포트 번호(COM6 등)로 맞춰주세요!
ARDUINO_PORT = 'COM8' 
BAUD_RATE = 9600

# 로컬에서 실행 중인 Flask 서버 주소
SERVER_URL = "http://127.0.0.1:5000/api/arduino/count"

try:
    py_serial = serial.Serial(port=ARDUINO_PORT, baudrate=BAUD_RATE, timeout=1)
    print(f"✅ 아두이노 연결 성공 ({ARDUINO_PORT})")
except Exception as e:
    print(f"❌ 아두이노 연결 실패: {e}")
    exit()

while True:
    if py_serial.readable():
        response = py_serial.readline().decode().strip()
        
        if response == "ENTER":
            print("🚶 감지 완료! -> 웹 서버로 퇴장(-1명) 데이터 전송")
            try:
                # 🌟 "enter"를 "leave"로 변경하여 -1 처리!
                res = requests.post(SERVER_URL, json={"event": "leave"})
                if res.status_code == 200:
                    print(f"성공! 현재 인원수: {res.json().get('current_count')}명")
            except Exception as e:
                print("서버 전송 실패 (python app.py가 켜져 있는지 확인하세요):", e)
                
    time.sleep(0.1)