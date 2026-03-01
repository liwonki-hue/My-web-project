# .github/workflows/update-piping-data.yml
name: Update Piping Construction Data

on:
  schedule:
    - cron: '0 21 * * *'   # KST 오전 6시
    - cron: '0 0 * * *'    # KST 오전 9시
  workflow_dispatch:
    inputs:
      reason:
        description: '수동 실행 사유 (선택)'
        required: false
        default: '데이터 즉시 갱신'

jobs:
  update-data:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install ODBC Driver 18 for SQL Server
        run: |
          curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
          curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list \
            | sudo tee /etc/apt/sources.list.d/mssql-release.list
          sudo apt-get update
          sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
          sudo apt-get install -y unixodbc-dev

      - name: Install Python packages
        run: pip install pyodbc requests

      # ── GitHub Actions 실행 서버 IP를 Azure SQL 방화벽에 등록 ──
      - name: Add runner IP to Azure SQL firewall
        run: |
          RUNNER_IP=$(curl -s https://api.ipify.org)
          echo "Runner IP: $RUNNER_IP"
          echo "RUNNER_IP=$RUNNER_IP" >> $GITHUB_ENV

          az login --service-principal \
            -u ${{ secrets.AZURE_CLIENT_ID }} \
            -p ${{ secrets.AZURE_CLIENT_SECRET }} \
            --tenant ${{ secrets.AZURE_TENANT_ID }}

          az sql server firewall-rule create \
            --resource-group ${{ secrets.AZURE_RESOURCE_GROUP }} \
            --server dwg-server-2171 \
            --name "GitHubActions-$(date +%s)" \
            --start-ip-address $RUNNER_IP \
            --end-ip-address $RUNNER_IP

          echo "✅ 방화벽 규칙 추가: $RUNNER_IP"
          sleep 10

      - name: Run data update script
        env:
          SQL_SERVER:   ${{ secrets.SQL_SERVER }}
          SQL_DATABASE: ${{ secrets.SQL_DATABASE }}
          SQL_USERNAME: ${{ secrets.SQL_USERNAME }}
          SQL_PASSWORD: ${{ secrets.SQL_PASSWORD }}
        run: python update_html_data.py

      - name: Remove runner IP from Azure SQL firewall
        if: always()
        run: |
          az sql server firewall-rule list \
            --resource-group ${{ secrets.AZURE_RESOURCE_GROUP }} \
            --server dwg-server-2171 \
            --query "[?startIpAddress=='$RUNNER_IP'].name" -o tsv | \
          xargs -I {} az sql server firewall-rule delete \
            --resource-group ${{ secrets.AZURE_RESOURCE_GROUP }} \
            --server dwg-server-2171 \
            --name {} --yes
          echo "✅ 임시 방화벽 규칙 삭제"

      - name: Commit and push updated HTML
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          if git diff --quiet con_control/index.html; then
            echo "ℹ️  데이터 변경 없음"
          else
            git add con_control/index.html
            git commit -m "🔄 Auto-update piping data [$(date -u '+%Y-%m-%d %H:%M UTC')]"
            git push
          fi
