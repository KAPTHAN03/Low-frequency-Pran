name: Hourly Cloud Alert Bot

on:
  schedule:
    # ⏱️ รันอัตโนมัติทุก 1 ชั่วโมง (นาทีที่ 0)
    - cron: '0 * * * *'
  workflow_dispatch: # ปุ่มกด Manual Run

jobs:
  run-bot:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4
        with:
          persist-credentials: true

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Libraries
        run: |
          pip install openmeteo-requests requests-cache tenacity pandas geopy requests

      - name: Run Cloud Alert Script
        # ⚡ จุดสำคัญ: บังคับฉีดข้อมูลสภาพแวดล้อมระบบส่งต่อไปยัง Python
        env:
          GITHUB_EVENT_NAME: ${{ github.event_name }}
          GITHUB_WORKFLOW: ${{ github.workflow }}
        run: python cloud_alert_v2.py

      - name: Commit and Push State File
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          
          if [ -f cloud_radar_state.json ]; then
            git add cloud_radar_state.json
            git commit -m "🤖 [Automated] Update cloud radar state memory [Skip CI]" || echo "No changes to commit"
            git push || echo "No changes to push"
          fi
