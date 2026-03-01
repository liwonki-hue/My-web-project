# .github/workflows/update-piping-data.yml
# ─────────────────────────────────────────────────────────────
# Azure SQL → HTML 데이터 자동 업데이트
# 실행 시점:
#   - 매일 오전 6시 (KST) = UTC 21:00 (전날)
#   - 매일 오전 9시 (KST) = UTC 00:00
#   - 수동 실행 가능 (Actions 탭 → Run workflow)
# ─────────────────────────────────────────────────────────────

name: Update Piping Construction Data

on:
  schedule:
    # KST 오전 6시 (UTC 21:00 전날) - 야간 작업 반영
    - cron: '0 21 * * *'
    # KST 오전 9시 (UTC 00:00) - 업무 시작 전 갱신
    - cron: '0 0 * * *'

  # 수동 실행 버튼 활성화
  workflow_dispatch:
    inputs:
      reason:
        description: '수동 실행 사유 (선택)'
        required: false
        default: '데이터 즉시 갱신'

jobs:
  update-data:
    runs-on: ubuntu-latest
    
    # 타임아웃: 10분 (보통 2~3분이면 완료)
    timeout-minutes: 10

    steps:
      # ── 1. 저장소 체크아웃 ──────────────────────────────
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      # ── 2. Python 설치 ──────────────────────────────────
      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      # ── 3. ODBC Driver 18 설치 (Azure SQL 전용) ─────────
      - name: Install ODBC Driver 18 for SQL Server
        run: |
          curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
          curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list \
            | sudo tee /etc/apt/sources.list.d/mssql-release.list
          sudo apt-get update
          sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
          sudo apt-get install -y unixodbc-dev

      # ── 4. Python 패키지 설치 ───────────────────────────
      - name: Install Python packages
        run: pip install pyodbc

      # ── 5. 데이터 업데이트 스크립트 실행 ────────────────
      - name: Run data update script
        env:
          SQL_SERVER:   ${{ secrets.SQL_SERVER }}
          SQL_DATABASE: ${{ secrets.SQL_DATABASE }}
          SQL_USERNAME: ${{ secrets.SQL_USERNAME }}
          SQL_PASSWORD: ${{ secrets.SQL_PASSWORD }}
        run: python update_html_data.py

      # ── 6. 변경사항 커밋 & 푸시 ─────────────────────────
      - name: Commit and push updated HTML
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          
          # 변경사항이 있을 때만 커밋
          if git diff --quiet con_control/index.html; then
            echo "ℹ️  데이터 변경 없음 - 커밋 생략"
          else
            git add con_control/index.html
            git commit -m "🔄 Auto-update piping data [$(date -u '+%Y-%m-%d %H:%M UTC')]"
            git push
            echo "✅ HTML 업데이트 완료 & 푸시됨"
          fi
