from flask import Flask, jsonify, request, render_template_string
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)

ADMIN_PIN = "1234"

# 🌟 [초기 시작 설정: 인원 0명, 대기반/호출반 빈 상태]
system_data = {
    "grade": "-",
    "class_num": "-",
    "current_call": "대기 중 (호출반 없음)",
    "congestion": "원활",
    "current_count": 0,          # 👈 서버 시작 인원 0명
    "max_count": 100,
    "total_entered": 0,
    "menu_name": "일반 메뉴",
    "menu_multiplier": 1.0,
    "avg_wait_time": 0.0,
    "peak_time": "12:45",
    "menu": ["발아현미밥", "고추장찌개", "돈육불고기", "상추쌈", "포기김치", "우유"],
    "calories": "785",
    "allergies": "우유, 대두, 밀",
    "teachers": "김교사, 이교사",
    "history_labels": ["30분 전", "25분 전", "20분 전", "15분 전", "10분 전", "5분 전", "현재"],
    "history_data": [0, 0, 0, 0, 0, 0, 0],
    "waiting_queue": []          # 👈 초기 대기열 없음
}

# 🌟 [1. 저녁 24시(자정) 데이터 자동 초기화 로직]
def reset_daily_data():
    system_data["current_count"] = 0
    system_data["current_call"] = "대기 중 (호출반 없음)"
    system_data["grade"] = "-"
    system_data["class_num"] = "-"
    system_data["waiting_queue"] = []
    system_data["history_data"] = [0, 0, 0, 0, 0, 0, 0]
    print("[시스템] 24시 자정 기준 데이터 자동 초기화가 완료되었습니다.")

# 백그라운드 스케줄러 등록 (매일 00:00 실행)
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(reset_daily_data, 'cron', hour=0, minute=0)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

def recalculate_metrics():
    # 남아있는 인원이 10명 이하이고 대기열에 반이 남아있다면 다음 반 자동 호출
    if system_data["current_count"] <= 10 and len(system_data["waiting_queue"]) > 0:
        next_class = system_data["waiting_queue"].pop(0)
        system_data["current_call"] = f"{next_class} 이동하세요!"

    system_data["avg_wait_time"] = round(system_data["current_count"] * system_data["menu_multiplier"] * 0.15, 1)
    count = system_data["current_count"]
    if count <= 20:
        system_data["congestion"] = "원활"
    elif count <= 55:
        system_data["congestion"] = "보통"
    else:
        system_data["congestion"] = "혼잡"

# ----------------------------------------------------
# 1. 학생용 모바일 뷰 (호출/대기반 숨김 처리)
# ----------------------------------------------------
STUDENT_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>급식실 스마트 대기 시스템 - 학생용</title>
    <link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.8/dist/web/static/pretendard.css" />
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0" rel="stylesheet" />
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Pretendard', sans-serif; background-color: #1e1e24; margin: 0; display: flex; justify-content: center; }
        .app-container { width: 100%; max-width: 420px; background-color: #F8F9FA; min-height: 100vh; position: relative; padding-bottom: 80px; box-shadow: 0 0 25px rgba(0,0,0,0.5); }
        .header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; background: white; font-weight: 700; font-size: 18px; color: #1E293B; border-bottom: 1px solid #E2E8F0; }
        .header-title { display: flex; align-items: center; gap: 8px; }
        .live-tag { background: #E0F2FE; color: #0284C7; font-size: 11px; padding: 4px 8px; border-radius: 12px; font-weight: 700; display: flex; align-items: center; gap: 4px; }
        .content { padding: 16px; }
        .status-card { background: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); margin-bottom: 16px; border: 1px solid #F1F5F9; }
        .status-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .status-header span { font-size: 14px; font-weight: 700; color: #475569; }
        .badge { padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; }
        .badge.원활 { background: #DCFCE7; color: #15803D; }
        .badge.보통 { background: #FEF3C7; color: #D97706; }
        .badge.혼잡 { background: #FEE2E2; color: #DC2626; }
        .count-display { text-align: center; margin: 16px 0; }
        .count-display .main-num { font-size: 44px; font-weight: 900; color: #0F172A; }
        .count-display .max-num { font-size: 18px; color: #94A3B8; font-weight: 600; }
        .progress-bg { background: #E2E8F0; height: 12px; border-radius: 10px; overflow: hidden; margin-bottom: 12px; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #3B82F6, #1D4ED8); width: 0%; transition: width 0.5s ease; }
        .legend-row { display: flex; justify-content: space-between; font-size: 11px; font-weight: 600; color: #64748B; }
        .wait-card { background: white; padding: 16px 20px; border-radius: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); margin-bottom: 16px; display: flex; align-items: center; gap: 16px; border: 1px solid #F1F5F9; }
        .wait-icon { background: #EEF2FF; color: #2563EB; width: 48px; height: 48px; border-radius: 16px; display: flex; align-items: center; justify-content: center; }
        .wait-info h4 { margin: 0 0 2px 0; font-size: 12px; color: #64748B; font-weight: 600; }
        .wait-info .time-text { font-size: 20px; font-weight: 800; color: #1E293B; }
        .wait-info .sub-text { font-size: 11px; color: #94A3B8; margin-top: 2px; }
        .chart-card { background: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); margin-bottom: 16px; border: 1px solid #F1F5F9; }
        .chart-card h4 { margin: 0 0 16px 0; font-size: 15px; color: #1E293B; font-weight: 700; display: flex; align-items: center; gap: 6px; }
        .menu-card { background: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); margin-bottom: 16px; border: 1px solid #F1F5F9; }
        .menu-title { font-weight: 700; font-size: 16px; color: #1E293B; display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
        .menu-time { font-size: 12px; color: #94A3B8; margin-bottom: 12px; }
        .menu-list { list-style-type: disc; padding-left: 20px; color: #334155; font-size: 14px; font-weight: 500; line-height: 1.6; margin: 0; }
        .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
        .info-box { padding: 14px; border-radius: 16px; font-size: 12px; }
        .info-box.blue { background: #EEF2FF; color: #2563EB; font-weight: 700; }
        .info-box.orange { background: #FFF7ED; color: #C2410C; font-weight: 700; }
        .info-box h5 { margin: 0 0 4px 0; font-size: 11px; color: #64748B; font-weight: 500; }
        .teacher-card { background: white; padding: 16px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); font-size: 13px; font-weight: 700; color: #334155; border: 1px solid #F1F5F9; margin-bottom: 16px; }
        .bottom-nav { position: absolute; bottom: 0; width: 100%; background: white; display: flex; justify-content: space-around; padding: 14px 0; border-top: 1px solid #E2E8F0; border-radius: 20px 20px 0 0; }
        .nav-item { text-align: center; color: #2563EB; font-size: 12px; font-weight: 700; display: flex; flex-direction: column; align-items: center; gap: 4px; }
    </style>
</head>
<body>
    <div class="app-container">
        <div class="header">
            <div class="header-title">
                <span class="material-symbols-rounded" style="color:#2563EB;">restaurant</span>
                급식실 스마트 대기
            </div>
            <div class="live-tag">
                <span class="material-symbols-rounded" style="font-size:12px;">bolt</span> 실시간 연동 중
            </div>
        </div>
        <div class="content">
            <div class="status-card">
                <div class="status-header">
                    <span>현재 급식실 이용 인원</span>
                    <span class="badge" id="congestion-badge">● 원활</span>
                </div>
                <div class="count-display">
                    <span class="main-num" id="current-count">0</span>
                    <span class="max-num"> / <span id="max-count">100</span>명</span>
                </div>
                <div class="progress-bg">
                    <div class="progress-fill" id="progress-bar"></div>
                </div>
                <div class="legend-row">
                    <span style="color:#15803D;">● 여유 (0~20명)</span>
                    <span style="color:#D97706;">● 보통 (21~55명)</span>
                    <span style="color:#DC2626;">● 혼잡 (56명 이상)</span>
                </div>
            </div>
            <div class="wait-card">
                <div class="wait-icon"><span class="material-symbols-rounded">schedule</span></div>
                <div class="wait-info">
                    <h4>메뉴 가중치 반영 예상 대기시간</h4>
                    <div class="time-text">약 <span id="avg-wait" style="color:#2563EB;">0.0</span>분 소요 예상</div>
                    <div class="sub-text">(오늘 메뉴: <span id="menu-type-name">일반 메뉴</span> <span id="menu-mult">1.0</span>x)</div>
                </div>
            </div>
            <div class="chart-card">
                <h4><span class="material-symbols-rounded" style="color:#2563EB;">show_chart</span> 실시간 혼잡도 추이</h4>
                <canvas id="congestionChart" height="170"></canvas>
            </div>
            <div class="menu-card">
                <div class="menu-title"><span class="material-symbols-rounded" style="color:#2563EB;">lunch_dining</span> 오늘의 중식 메뉴</div>
                <div class="menu-time">배식 시간: 12:30 ~ 13:30</div>
                <ul class="menu-list" id="menu-list"></ul>
            </div>
            <div class="info-grid">
                <div class="info-box blue">
                    <h5>예상 칼로리</h5>
                    <span id="calories" style="font-size:16px;">785</span> kcal
                </div>
                <div class="info-box orange">
                    <h5>알레르기 정보</h5>
                    <span id="allergies" style="font-size:12px;">우유, 대두, 밀</span>
                </div>
            </div>
            <div class="teacher-card">
                📋 오늘의 급식 지도: <span id="teachers" style="color:#2563EB;">김교사, 이교사</span>
            </div>
        </div>
        <div class="bottom-nav">
            <div class="nav-item"><span class="material-symbols-rounded">home</span>학생용 현황판</div>
            <div class="nav-item" style="color:#94A3B8;"><span class="material-symbols-rounded">calendar_month</span>식단표</div>
        </div>
    </div>
    <script>
        const ctx = document.getElementById('congestionChart').getContext('2d');
        const congestionChart = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets: [{ label: '대기 인원수(명)', data: [], borderColor: '#2563EB', backgroundColor: 'rgba(37, 99, 235, 0.1)', borderWidth: 3, fill: true, tension: 0.4 }] },
            options: { responsive: true, plugins: { legend: { display: false } } }
        });

        setInterval(() => {
            fetch('/api/get_status')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('current-count').innerText = data.current_count;
                    document.getElementById('max-count').innerText = data.max_count;
                    let percent = (data.current_count / data.max_count) * 100;
                    document.getElementById('progress-bar').style.width = Math.min(Math.max(percent, 0), 100) + '%';
                    
                    let badge = document.getElementById('congestion-badge');
                    badge.innerText = '● ' + data.congestion;
                    badge.className = 'badge ' + data.congestion;
                    
                    document.getElementById('avg-wait').innerText = data.avg_wait_time;
                    document.getElementById('menu-type-name').innerText = data.menu_name;
                    document.getElementById('menu-mult').innerText = data.menu_multiplier;
                    
                    let menuHtml = '';
                    data.menu.forEach(item => { menuHtml += `<li>${item}</li>`; });
                    document.getElementById('menu-list').innerHTML = menuHtml;
                    
                    document.getElementById('calories').innerText = data.calories;
                    document.getElementById('allergies').innerText = data.allergies;
                    document.getElementById('teachers').innerText = data.teachers;
                    
                    if (congestionChart && congestionChart.data) {
                        congestionChart.data.labels = data.history_labels;
                        congestionChart.data.datasets[0].data = data.history_data;
                        congestionChart.update('none');
                    }
                })
                .catch(err => console.error("데이터 동기화 에러:", err));
        }, 1000);
    </script>
</body>
</html>
"""

# ----------------------------------------------------
# 2. 관리자용 모바일 뷰 (호출반 & 대기반 전용 조회 포함)
# ----------------------------------------------------
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>급식실 스마트 대기 - 관리자</title>
    <link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.8/dist/web/static/pretendard.css" />
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0" rel="stylesheet" />
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Pretendard', sans-serif; background-color: #1e1e24; margin: 0; display: flex; justify-content: center; }
        .app-container { width: 100%; max-width: 420px; background-color: #F8F9FA; min-height: 100vh; position: relative; padding-bottom: 40px; }
        .header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; background: #0F172A; color: white; font-weight: 700; font-size: 18px; }
        .content { padding: 16px; }
        .pin-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(15,23,42,0.95); display: flex; align-items: center; justify-content: center; z-index: 999; }
        .pin-box { background: white; padding: 24px; border-radius: 20px; width: 85%; max-width: 320px; text-align: center; }
        .pin-box h3 { margin: 0 0 8px 0; color: #0F172A; }
        .pin-box p { font-size: 12px; color: #64748B; margin-bottom: 16px; }
        .pin-input { width: 100%; padding: 12px; border: 2px solid #E2E8F0; border-radius: 12px; font-size: 20px; text-align: center; letter-spacing: 6px; font-weight: 800; margin-bottom: 12px; outline: none; }
        .pin-btn { width: 100%; padding: 12px; background: #2563EB; color: white; border: none; border-radius: 12px; font-weight: 700; cursor: pointer; }
        .box { background: white; padding: 20px; border-radius: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); margin-bottom: 16px; border: 1px solid #F1F5F9; }
        .box-title { font-weight: 700; font-size: 15px; color: #2563EB; display: flex; align-items: center; gap: 6px; margin-bottom: 16px; }
        .label { font-size: 12px; color: #64748B; font-weight: 600; margin-bottom: 8px; display: block; }
        .count-input-row { display: flex; gap: 8px; margin-bottom: 12px; }
        .num-input { flex: 1; padding: 12px; border: 1px solid #E2E8F0; border-radius: 12px; font-size: 18px; font-weight: 800; text-align: center; outline: none; }
        .btn-apply { padding: 0 20px; background: #2563EB; color: white; border: none; border-radius: 12px; font-weight: 700; cursor: pointer; }
        .quick-btn-row { display: flex; gap: 8px; margin-bottom: 8px; }
        .btn-quick { flex: 1; padding: 10px; border: 1px solid #E2E8F0; border-radius: 10px; background: #F8FAFC; font-weight: 700; color: #334155; cursor: pointer; }
        .btn-class-add { width: 100%; padding: 12px; background: #10B981; color: white; border: none; border-radius: 12px; font-weight: 700; font-size: 14px; cursor: pointer; }
        .btn-group { display: flex; background: #F1F5F9; border-radius: 12px; padding: 4px; margin-bottom: 12px; }
        .btn-group .btn { flex: 1; padding: 10px 0; text-align: center; font-size: 13px; font-weight: 600; color: #64748B; border-radius: 8px; cursor: pointer; }
        .btn-group .btn.active { background: white; color: #2563EB; font-weight: 800; }
        .num-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-bottom: 16px; }
        .num-grid .btn { padding: 10px 0; background: white; border: 1px solid #E2E8F0; border-radius: 8px; text-align: center; font-weight: 600; color: #475569; cursor: pointer; }
        .num-grid .btn.active { background: #2563EB; color: white; border-color: #2563EB; font-weight: 800; }
        .btn-broadcast { width: 100%; padding: 14px; background: #2563EB; color: white; border: none; border-radius: 12px; font-weight: 700; cursor: pointer; margin-bottom: 8px; }
        .btn-queue-add { width: 100%; padding: 12px; background: #059669; color: white; border: none; border-radius: 12px; font-weight: 700; cursor: pointer; margin-bottom: 8px; }
        .btn-stop { width: 100%; padding: 12px; background: #FEE2E2; color: #DC2626; border: none; border-radius: 12px; font-weight: 700; font-size: 13px; cursor: pointer; }
        .queue-box { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 12px; margin-bottom: 12px; font-size: 13px; font-weight: 600; color: #334155; }
        .call-status-box { background: #EEF2FF; border: 1px solid #C7D2FE; border-radius: 12px; padding: 14px; margin-bottom: 12px; }
        .type-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
        .type-btn { padding: 12px 6px; border: 1px solid #E2E8F0; border-radius: 12px; background: white; text-align: center; cursor: pointer; }
        .type-btn.active { border-color: #2563EB; background: #EEF2FF; color: #2563EB; font-weight: 700; }
        .type-btn .title { font-size: 12px; font-weight: 700; display: block; margin-bottom: 2px; }
        .type-btn .sub { font-size: 10px; color: #94A3B8; }
        .input-box { width: 100%; padding: 12px; border: 1px solid #E2E8F0; border-radius: 10px; font-family: 'Pretendard'; font-size: 13px; margin-bottom: 10px; box-sizing: border-box; }
        .btn-save-info { width: 100%; padding: 12px; background: #0F172A; color: white; border: none; border-radius: 10px; font-weight: 700; font-size: 13px; cursor: pointer; }
        .btn-clear-q { background: #EF4444; color: white; border: none; border-radius: 6px; padding: 4px 8px; font-size: 11px; cursor: pointer; float: right; }
    </style>
</head>
<body>
    <div id="pin-modal" class="pin-overlay">
        <div class="pin-box">
            <h3>🔒 관리자 인증</h3>
            <p>보안을 위해 PIN 번호를 입력하세요.</p>
            <input type="password" id="pin-input" class="pin-input" maxlength="4" placeholder="••••">
            <button class="pin-btn" onclick="verifyPin()">확인</button>
        </div>
    </div>

    <div class="app-container">
        <div class="header">
            <span>⚙️ 급식실 현장 관리자 모드</span>
        </div>
        <div class="content">
            <div class="box">
                <div class="box-title"><span class="material-symbols-rounded">visibility</span> 실시간 대기반 & 호출반 현황</div>
                <div class="call-status-box">
                    <span class="label" style="color:#1D4ED8; margin-bottom:4px;">📢 현재 호출되어 들어오는 반:</span>
                    <div id="admin-current-call" style="font-size:18px; font-weight:800; color:#1E4ED8;">로딩 중...</div>
                </div>
                <div class="queue-box">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <strong>📌 자동 호출 대기반 목록:</strong>
                        <button class="btn-clear-q" onclick="clearQueue()">대기목록 초기화</button>
                    </div>
                    <div id="queue-display" style="color:#2563EB;">불러오는 중...</div>
                </div>
            </div>

            <div class="box">
                <div class="box-title"><span class="material-symbols-rounded">edit_number</span> 대기 인원 직접 입력 및 조정</div>
                <span class="label">현재 급식실 대기 인원수 (명)</span>
                <div class="count-input-row">
                    <input type="number" id="direct-count-input" class="num-input" value="0">
                    <button class="btn-apply" onclick="applyDirectCount()">적용</button>
                </div>
                <div class="quick-btn-row">
                    <button class="btn-quick" onclick="quickAdjust(-1)">-1명</button>
                    <button class="btn-quick" onclick="quickAdjust(+1)">+1명</button>
                    <button class="btn-quick" onclick="quickAdjust(+10)">+10명</button>
                </div>
                <button class="btn-class-add" onclick="quickAdjust(+24)">🏫 +1반 추가 (+24명)</button>
            </div>

            <div class="box">
                <div class="box-title"><span class="material-symbols-rounded">campaign</span> 학년 / 반 호출 및 순서 설정</div>
                <span class="label">학년 선택</span>
                <div class="btn-group">
                    <div class="btn grade-btn active" onclick="selectGrade('1')">1학년</div>
                    <div class="btn grade-btn" onclick="selectGrade('2')">2학년</div>
                    <div class="btn grade-btn" onclick="selectGrade('3')">3학년</div>
                </div>
                
                <span class="label">반 선택 (1~10반)</span>
                <div class="num-grid">
                    <div class="btn class-btn" onclick="selectClass('1')">1</div>
                    <div class="btn class-btn" onclick="selectClass('2')">2</div>
                    <div class="btn class-btn active" onclick="selectClass('3')">3</div>
                    <div class="btn class-btn" onclick="selectClass('4')">4</div>
                    <div class="btn class-btn" onclick="selectClass('5')">5</div>
                    <div class="btn class-btn" onclick="selectClass('6')">6</div>
                    <div class="btn class-btn" onclick="selectClass('7')">7</div>
                    <div class="btn class-btn" onclick="selectClass('8')">8</div>
                    <div class="btn class-btn" onclick="selectClass('9')">9</div>
                    <div class="btn class-btn" onclick="selectClass('10')">10</div>
                </div>
                
                <button class="btn-broadcast" onclick="sendBroadcastCall()">📢 바로 호출하기</button>
                <button class="btn-queue-add" onclick="addQueueCall()">📋 10명 이하 시 대기반에 추가</button>
                
                <button class="btn-stop" onclick="sendStopCall()">🚨 입장 일시 중단 / 전체 대기</button>
            </div>

            <div class="box">
                <div class="box-title"><span class="material-symbols-rounded">tune</span> 오늘의 메뉴 타입 선택 (가중치 연산)</div>
                <div class="type-grid">
                    <div class="type-btn" id="m-popular" onclick="setMenuType('인기 메뉴', 1.2, 'm-popular')">
                        <span class="title">🔥 인기 메뉴</span>
                        <span class="sub">1.2배 소요</span>
                    </div>
                    <div class="type-btn active" id="m-normal" onclick="setMenuType('일반 메뉴', 1.0, 'm-normal')">
                        <span class="title">🍱 일반 메뉴</span>
                        <span class="sub">1.0배 기본</span>
                    </div>
                    <div class="type-btn" id="m-fast" onclick="setMenuType('빠른 메뉴', 0.8, 'm-fast')">
                        <span class="title">⚡ 빠른 메뉴</span>
                        <span class="sub">0.8배 단축</span>
                    </div>
                </div>
            </div>

            <div class="box">
                <div class="box-title"><span class="material-symbols-rounded">edit_note</span> 식단 및 지도 교사 정보 입력</div>
                <span class="label">급식 지도 선생님</span>
                <input type="text" id="inp-teachers" class="input-box" value="김교사, 이교사">
                
                <span class="label">오늘의 메뉴 (쉼표로 구분)</span>
                <input type="text" id="inp-menu" class="input-box" value="발아현미밥, 고추장찌개, 돈육불고기, 상추쌈, 포기김치, 우유">
                
                <button class="btn-save-info" onclick="saveSettings()">정보 저장 및 학생 화면 반영</button>
            </div>
        </div>
    </div>

    <script>
        let currentPin = "";
        let selectedGrade = "1";
        let selectedClass = "3";
        let isEditingInput = false;

        document.getElementById('direct-count-input').addEventListener('focus', () => { isEditingInput = true; });
        document.getElementById('direct-count-input').addEventListener('blur', () => { isEditingInput = false; });

        function verifyPin() {
            let val = document.getElementById('pin-input').value;
            fetch('/api/verify_admin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin: val })
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    currentPin = val;
                    document.getElementById('pin-modal').style.display = 'none';
                } else {
                    alert('비밀번호가 올바르지 않습니다!');
                    document.getElementById('pin-input').value = '';
                }
            });
        }

        function applyDirectCount() {
            let val = parseInt(document.getElementById('direct-count-input').value) || 0;
            fetch('/api/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin: currentPin, action: 'set_count', value: val })
            }).then(() => alert('대기 인원수가 ' + val + '명으로 설정되었습니다!'));
        }

        function quickAdjust(delta) {
            let input = document.getElementById('direct-count-input');
            let current = parseInt(input.value) || 0;
            let nextVal = Math.max(0, current + delta);
            input.value = nextVal;
            applyDirectCount();
        }

        function selectGrade(g) {
            selectedGrade = g;
            document.querySelectorAll('.grade-btn').forEach(b => b.classList.remove('active'));
            event.currentTarget.classList.add('active');
        }

        function selectClass(c) {
            selectedClass = c;
            document.querySelectorAll('.class-btn').forEach(b => b.classList.remove('active'));
            event.currentTarget.classList.add('active');
        }

        function sendBroadcastCall() {
            let msg = selectedGrade + '학년 ' + selectedClass + '반 이동하세요!';
            fetch('/api/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin: currentPin, action: 'set_call', grade: selectedGrade, class_num: selectedClass, value: msg })
            }).then(() => alert(msg + ' 호출 신호를 전송했습니다!'));
        }

        function addQueueCall() {
            let className = selectedGrade + '학년 ' + selectedClass + '반';
            fetch('/api/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin: currentPin, action: 'add_queue', className: className })
            }).then(() => alert(className + '을(를) 대기반 목록에 추가했습니다!'));
        }

        function clearQueue() {
            if(confirm('대기반 목록을 초기화하시겠습니까?')) {
                fetch('/api/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pin: currentPin, action: 'clear_queue' })
                });
            }
        }

        function sendStopCall() {
            let msg = "현재 대기 중 (입장 일시 중단)";
            fetch('/api/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin: currentPin, action: 'set_call', grade: selectedGrade, class_num: selectedClass, value: msg })
            }).then(() => alert('입장 중단 신호를 보냈습니다.'));
        }

        function setMenuType(name, mult, btnId) {
            document.querySelectorAll('.type-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(btnId).classList.add('active');
            fetch('/api/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin: currentPin, action: 'set_menu_type', name: name, multiplier: mult })
            });
        }

        function saveSettings() {
            let teachers = document.getElementById('inp-teachers').value;
            let menuArr = document.getElementById('inp-menu').value.split(',').map(s => s.trim());
            fetch('/api/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin: currentPin, action: 'save_settings', teachers: teachers, menu: menuArr })
            }).then(() => alert('식단 및 교사 정보가 업데이트되었습니다!'));
        }

        setInterval(() => {
            fetch('/api/get_status')
                .then(res => res.json())
                .then(data => {
                    if (!isEditingInput) {
                        document.getElementById('direct-count-input').value = data.current_count;
                    }
                    document.getElementById('admin-current-call').innerText = data.current_call;
                    
                    let qText = data.waiting_queue.length > 0 
                        ? data.waiting_queue.map((item, idx) => `[${idx+1}] ${item}`).join(' ➔ ') 
                        : '대기 중인 반 없음';
                    document.getElementById('queue-display').innerText = qText;
                });
        }, 1000);
    </script>
</body>
</html>
"""

# ----------------------------------------------------
# 3. 백엔드 라우팅 및 API 처리
# ----------------------------------------------------
@app.route('/')
def student_view():
    return render_template_string(STUDENT_HTML)

@app.route('/admin')
def admin_view():
    return render_template_string(ADMIN_HTML)

@app.route('/api/get_status')
def get_status():
    recalculate_metrics()
    return jsonify(system_data)

@app.route('/api/verify_admin', methods=['POST'])
def verify_admin():
    pin = request.json.get('pin')
    return jsonify({"success": pin == ADMIN_PIN})

# 관리자 조작 API
@app.route('/api/update', methods=['POST'])
def update_data():
    data = request.json or {}
    if data.get('pin') != ADMIN_PIN:
        return jsonify({"status": "error", "message": "권한 없음"}), 403
        
    action = data.get('action')
    if action == 'set_count':
        system_data['current_count'] = max(0, data.get('value', 0))
    elif action == 'set_call':
        system_data['grade'] = data.get('grade', system_data['grade'])
        system_data['class_num'] = data.get('class_num', system_data['class_num'])
        system_data['current_call'] = data.get('value', system_data['current_call'])
    elif action == 'add_queue':
        cls_name = data.get('className')
        if cls_name and cls_name not in system_data['waiting_queue']:
            system_data['waiting_queue'].append(cls_name)
    elif action == 'clear_queue':
        system_data['waiting_queue'] = []
    elif action == 'set_menu_type':
        system_data['menu_name'] = data.get('name', system_data['menu_name'])
        system_data['menu_multiplier'] = data.get('multiplier', system_data['menu_multiplier'])
    elif action == 'save_settings':
        system_data['teachers'] = data.get('teachers', system_data['teachers'])
        system_data['menu'] = data.get('menu', system_data['menu'])

    return jsonify({"status": "success", "system_data": system_data})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)