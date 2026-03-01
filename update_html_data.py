"""
update_html_data.py
─────────────────────────────────────────────────────────────
Azure SQL Server → RAW 배열 생성 → gzip → Base64 → HTML 삽입
GitHub Actions 에서 자동 실행됨
─────────────────────────────────────────────────────────────
환경변수 (GitHub Secrets에 등록):
  SQL_SERVER   : dwg-server-2171.database.windows.net
  SQL_DATABASE : Dwg_Database
  SQL_USERNAME : dwgadmin
  SQL_PASSWORD : (비밀번호)
"""

import os
import sys
import json
import gzip
import base64
import pyodbc
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# 1. 설정
# ─────────────────────────────────────────────────────────────
HTML_PATH = "con_control/index.html"   # GitHub 저장소 내 HTML 경로

# GitHub Secrets → 환경변수로 읽기
SERVER   = os.environ["SQL_SERVER"]
DATABASE = os.environ["SQL_DATABASE"]
USERNAME = os.environ["SQL_USERNAME"]
PASSWORD = os.environ["SQL_PASSWORD"]

# ─────────────────────────────────────────────────────────────
# 2. DB 연결 및 데이터 조회
# ─────────────────────────────────────────────────────────────
print("🔌 Azure SQL 연결 중...")
conn_str = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"UID={USERNAME};"
    f"PWD={PASSWORD};"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# ConstructionMaster 테이블에서 전체 조회
# RAW 배열 인덱스 순서:
#   [0]System  [1]Unit  [2]Area  [3]LineNo  [4]ISODrawing  [5]Spool_No
#   [6]Bore    [7]Material  [8]Size(float)  [9]ShopField
#   [10]JointNo  [11]Completed  [12]DI(계산)  [13]Remark
SQL = """
SELECT
    ISNULL(System,   '')  AS System,
    ISNULL(Unit,     '')  AS Unit,
    ISNULL(Area,     '')  AS Area,
    ISNULL(LineNo,   '')  AS LineNo,
    ISNULL(ISODrawing,'') AS ISODrawing,
    ISNULL(Spool_No, '')  AS Spool_No,
    ISNULL(Bore,     '')  AS Bore,
    ISNULL(Material, '')  AS Material,
    ISNULL(Size,     0)   AS Size,
    ISNULL(ShopField,'')  AS ShopField,
    ISNULL(JointNo,  '')  AS JointNo,
    ISNULL(Completed,'')  AS Completed,
    ISNULL(Remark,   '')  AS Remark
FROM dbo.ConstructionMaster
ORDER BY System, Unit, Area, LineNo, Spool_No, JointNo
"""

print("📊 데이터 조회 중...")
cursor.execute(SQL)
rows = cursor.fetchall()
cursor.close()
conn.close()
print(f"   → {len(rows):,} 행 조회 완료")

# ─────────────────────────────────────────────────────────────
# 3. RAW 배열 생성 (HTML의 r[인덱스] 에 맞게)
# ─────────────────────────────────────────────────────────────
def safe_str(v):
    """None / 빈칸 → 빈 문자열"""
    if v is None:
        return ""
    s = str(v).strip()
    return s

def safe_float(v):
    """Size 컬럼 → float (실패 시 0)"""
    try:
        return float(v) if v else 0.0
    except (ValueError, TypeError):
        return 0.0

RAW = []
for row in rows:
    size  = safe_float(row[8])
    comp  = safe_str(row[11])
    di    = size if comp else 0   # 완료된 경우만 DI 집계

    RAW.append([
        safe_str(row[0]),   # [0]  System
        safe_str(row[1]),   # [1]  Unit
        safe_str(row[2]),   # [2]  Area
        safe_str(row[3]),   # [3]  LineNo
        safe_str(row[4]),   # [4]  ISODrawing
        safe_str(row[5]),   # [5]  Spool_No
        safe_str(row[6]),   # [6]  Bore
        safe_str(row[7]),   # [7]  Material
        size,               # [8]  Size (float) ← DI 계산 기준
        safe_str(row[9]),   # [9]  ShopField
        safe_str(row[10]),  # [10] JointNo
        comp,               # [11] Completed (날짜 문자열 or "")
        di,                 # [12] 완료 DI
        safe_str(row[12]),  # [13] Remark
    ])

print(f"   → RAW 배열 {len(RAW):,} 건 생성")

# ─────────────────────────────────────────────────────────────
# 4. JSON → gzip 압축 → Base64 인코딩
# ─────────────────────────────────────────────────────────────
json_bytes    = json.dumps(RAW, ensure_ascii=False).encode("utf-8")
gzipped       = gzip.compress(json_bytes, compresslevel=9)
b64_str       = base64.b64encode(gzipped).decode("ascii")
print(f"   → 압축 후 Base64 크기: {len(b64_str):,} 문자")

# ─────────────────────────────────────────────────────────────
# 5. HTML 파일의 PIPING_B64 교체
# ─────────────────────────────────────────────────────────────
print(f"📝 HTML 업데이트: {HTML_PATH}")

with open(HTML_PATH, "r", encoding="utf-8") as f:
    html = f.read()

# PIPING_B64 변수 찾아서 값 교체
# HTML 내 패턴: const PIPING_B64='...(base64)...';
import re

# 메타 정보 추가 (마지막 업데이트 시간)
now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
new_b64_block = (
    f"/* AUTO-GENERATED: {now_utc} | {len(RAW):,} records */\n"
    f"const PIPING_B64='{b64_str}';"
)

# 기존 PIPING_B64 블록 교체 (주석 포함 or 없는 경우 모두 처리)
pattern = r"(?:/\* AUTO-GENERATED:[^\n]*\*/\n)?const PIPING_B64='[^']*';"
if re.search(pattern, html):
    html = re.sub(pattern, new_b64_block, html)
    print("   → PIPING_B64 블록 교체 완료")
else:
    print("❌ HTML에서 'const PIPING_B64=' 패턴을 찾지 못했습니다.")
    print("   HTML 파일을 확인하고 패턴을 수동으로 맞춰주세요.")
    sys.exit(1)

with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ 완료! {now_utc} 기준 {len(RAW):,}건 반영됨")
