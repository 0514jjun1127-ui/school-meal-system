import serial
import requests
import time

ARDUINO_PORT = 'COM8' 
BAUD_RATE = 9600

# 🌟 정확한 Render 주소(2mrb)로 수정 완료!
SERVER_URL = "https://school-meal-system-2mrb.onrender.com/api/arduino/count"

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
                res = requests.post(SERVER_URL, json={"event": "leave"})
                if res.status_code == 200:
                    print(f"성공! 현재 인원수: {res.json().get('current_count')}명")
            except Exception as e:
                print("서버 전송 실패:", e)
                
    time.sleep(0.1)