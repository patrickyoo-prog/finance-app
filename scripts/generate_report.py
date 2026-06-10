#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import formatdate
from email import encoders

import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# 한글 지원
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

# 환경 변수
NOTION_TOKEN = os.getenv('NOTION_API_TOKEN')
DATABASE_ID = os.getenv('NOTION_DATABASE_ID')
GMAIL_EMAIL = os.getenv('GMAIL_EMAIL')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')

# 디렉토리 생성
Path('reports').mkdir(exist_ok=True)

def get_last_day_of_month():
    """현재 달의 마지막 날짜 반환"""
    today = datetime.now()
    if today.month == 12:
        last_day = datetime(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(today.year, today.month + 1, 1) - timedelta(days=1)
    return last_day

def get_notion_data():
    """노션에서 현재 월의 데이터 수집"""
    url = f'https://api.notion.com/v1/databases/{DATABASE_ID}/query'
    headers = {
        'Authorization': f'Bearer {NOTION_TOKEN}',
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json'
    }

    # 현재 월 범위 계산
    today = datetime.now()
    month_start = datetime(today.year, today.month, 1).isoformat()

    if today.month == 12:
        month_end = datetime(today.year + 1, 1, 1).isoformat()
    else:
        month_end = datetime(today.year, today.month + 1, 1).isoformat()

    payload = {
        'filter': {
            'and': [
                {
                    'property': 'Date',
                    'date': {
                        'on_or_after': month_start
                    }
                },
                {
                    'property': 'Date',
                    'date': {
                        'before': month_end
                    }
                }
            ]
        },
        'sorts': [
            {
                'property': 'Date',
                'direction': 'ascending'
            }
        ]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f'❌ Notion API 오류: {response.status_code}')
            print(response.text)
            return None

        data = response.json()
        records = []

        for page in data.get('results', []):
            props = page['properties']
            record = {
                'date': props.get('Date', {}).get('date', {}).get('start', ''),
                'amount': props.get('Amount', {}).get('number', 0),
                'category': props.get('Category', {}).get('select', {}).get('name', '기타'),
                'type': props.get('Type', {}).get('select', {}).get('name', '소비'),
                'memo': props.get('Memo', {}).get('rich_text', [{}])[0].get('text', {}).get('content', '')
            }
            if record['date'] and record['amount']:
                records.append(record)

        print(f'✅ 노션에서 {len(records)}개의 거래 내역 수집')
        return records

    except Exception as e:
        print(f'❌ 데이터 수집 오류: {e}')
        return None

def analyze_data(records):
    """데이터 분석"""
    try:
        df = pd.DataFrame(records)

        if df.empty:
            print('❌ 이번 달 데이터가 없습니다.')
            return None, None, None

        # 데이터 타입 변환
        df['date'] = pd.to_datetime(df['date'])
        df['amount'] = pd.to_numeric(df['amount'])

        # 소비/소득 분리
        expense_df = df[df['type'] == '소비']
        income_df = df[df['type'] == '소득']

        # 카테고리별 합계
        category_summary = expense_df.groupby('category')['amount'].sum().sort_values(ascending=False)

        # 일일 합계
        daily_summary = expense_df.groupby(df['date'].dt.date)['amount'].sum()

        print(f'✅ 데이터 분석 완료')
        print(f'   - 총 소비: ₩{expense_df["amount"].sum():,.0f}')
        print(f'   - 총 수입: ₩{income_df["amount"].sum():,.0f}')
        print(f'   - 카테고리 수: {len(category_summary)}')

        return df, category_summary, daily_summary

    except Exception as e:
        print(f'❌ 분석 오류: {e}')
        return None, None, None

def create_charts(category_summary, daily_summary):
    """차트 생성"""
    try:
        fig, axes = plt.subplots(2, 1, figsize=(10, 8))

        # 1. 카테고리별 원형 차트
        colors_list = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E2']
        axes[0].pie(
            category_summary.values,
            labels=category_summary.index,
            autopct='%1.1f%%',
            colors=colors_list,
            startangle=90
        )
        axes[0].set_title('카테고리별 소비 비율', fontsize=14, fontweight='bold')

        # 2. 일일 소비 추이
        axes[1].bar(range(len(daily_summary)), daily_summary.values, color='#4F46E5', alpha=0.7)
        axes[1].set_xlabel('날짜', fontsize=12)
        axes[1].set_ylabel('금액 (₩)', fontsize=12)
        axes[1].set_title('일일 소비 추이', fontsize=14, fontweight='bold')
        axes[1].grid(True, alpha=0.3, axis='y')

        # X축 레이블
        if len(daily_summary) > 0:
            step = max(1, len(daily_summary) // 10)
            axes[1].set_xticks(range(0, len(daily_summary), step))
            axes[1].set_xticklabels([str(daily_summary.index[i]) for i in range(0, len(daily_summary), step)], rotation=45)

        plt.tight_layout()
        chart_path = 'reports/chart.png'
        plt.savefig(chart_path, dpi=100, bbox_inches='tight')
        plt.close()

        print(f'✅ 차트 생성 완료: {chart_path}')
        return chart_path

    except Exception as e:
        print(f'❌ 차트 생성 오류: {e}')
        return None

def create_pdf_report(df, category_summary, daily_summary, chart_path):
    """PDF 보고서 생성"""
    try:
        today = datetime.now()
        filename = f'reports/{today.year}{today.month:02d}_monthly_report.pdf'

        doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        story = []

        # 커스텀 스타일
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#4F46E5'),
            spaceAfter=10,
            alignment=TA_CENTER
        )

        # 제목
        story.append(Paragraph(f'{today.year}년 {today.month}월 가계부 분석 보고서', title_style))
        story.append(Paragraph(f'생성일: {today.strftime("%Y-%m-%d %H:%M")}', styles['Normal']))
        story.append(Spacer(1, 0.2*inch))

        # 요약 통계
        expense_df = df[df['type'] == '소비']
        income_df = df[df['type'] == '소득']
        total_expense = expense_df['amount'].sum()
        total_income = income_df['amount'].sum()
        net_saving = total_income - total_expense

        summary_data = [
            ['항목', '금액'],
            ['총 소비', f'₩{total_expense:,.0f}'],
            ['총 수입', f'₩{total_income:,.0f}'],
            ['순저축', f'₩{net_saving:,.0f}']
        ]

        summary_table = Table(summary_data, colWidths=[2.5*inch, 2.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F0F0F0')),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 11)
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))

        # 카테고리별 분석
        story.append(Paragraph('📊 카테고리별 소비 분석', styles['Heading2']))
        category_data = [['카테고리', '금액', '비율']]
        for cat, amount in category_summary.items():
            ratio = (amount / total_expense * 100) if total_expense > 0 else 0
            category_data.append([cat, f'₩{amount:,.0f}', f'{ratio:.1f}%'])

        category_table = Table(category_data, colWidths=[2*inch, 2*inch, 1.5*inch])
        category_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 9)
        ]))
        story.append(category_table)
        story.append(Spacer(1, 0.3*inch))

        # 차트 삽입
        if chart_path and os.path.exists(chart_path):
            story.append(Paragraph('📈 소비 추이 분석', styles['Heading2']))
            img = Image(chart_path, width=5.5*inch, height=4*inch)
            story.append(img)

        # PDF 생성
        doc.build(story)

        print(f'✅ PDF 보고서 생성 완료: {filename}')
        return filename

    except Exception as e:
        print(f'❌ PDF 생성 오류: {e}')
        return None

def send_email(pdf_filename):
    """이메일로 보고서 전송"""
    try:
        if not os.path.exists(pdf_filename):
            print(f'❌ PDF 파일을 찾을 수 없습니다: {pdf_filename}')
            return False

        msg = MIMEMultipart()
        msg['From'] = GMAIL_EMAIL
        msg['To'] = GMAIL_EMAIL
        msg['Date'] = formatdate(localtime=True)

        today = datetime.now()
        msg['Subject'] = f'[가계부] {today.year}년 {today.month}월 분석 보고서'

        body = f'''{today.year}년 {today.month}월 가계부 분석 보고서

안녕하세요,

이번 달의 가계부 분석 보고서를 첨부합니다.
보고서에는 소비 내역, 카테고리별 분석, 일일 추이 등이 포함되어 있습니다.

생성일: {today.strftime("%Y-%m-%d %H:%M")}

감사합니다.
'''
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # PDF 첨부
        with open(pdf_filename, 'rb') as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(pdf_filename)}')
            msg.attach(part)

        # Gmail 전송
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(GMAIL_EMAIL, GMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()

        print(f'✅ 이메일 전송 성공: {GMAIL_EMAIL}')
        return True

    except Exception as e:
        print(f'❌ 이메일 전송 오류: {e}')
        return False

def main():
    print('\n' + '='*50)
    print('📊 월별 가계부 분석 보고서 생성')
    print('='*50 + '\n')

    # 환경 변수 확인
    if not all([NOTION_TOKEN, DATABASE_ID, GMAIL_EMAIL, GMAIL_PASSWORD]):
        print('❌ 환경 변수가 설정되지 않았습니다.')
        print('   필요한 변수: NOTION_API_TOKEN, NOTION_DATABASE_ID, GMAIL_EMAIL, GMAIL_PASSWORD')
        return

    # 1. 데이터 수집
    print('1️⃣  노션에서 데이터 수집 중...')
    records = get_notion_data()
    if not records:
        print('❌ 데이터 수집 실패')
        return

    # 2. 데이터 분석
    print('\n2️⃣  데이터 분석 중...')
    df, category_summary, daily_summary = analyze_data(records)
    if df is None:
        return

    # 3. 차트 생성
    print('\n3️⃣  차트 생성 중...')
    chart_path = create_charts(category_summary, daily_summary)

    # 4. PDF 생성
    print('\n4️⃣  PDF 보고서 생성 중...')
    pdf_filename = create_pdf_report(df, category_summary, daily_summary, chart_path)
    if not pdf_filename:
        return

    # 5. 이메일 전송
    print('\n5️⃣  이메일 전송 중...')
    send_email(pdf_filename)

    print('\n' + '='*50)
    print('✅ 모든 작업 완료!')
    print('='*50 + '\n')

if __name__ == '__main__':
    main()
