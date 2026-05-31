import streamlit as st
import FinanceDataReader as fdr
from pykrx import stock
import pandas as pd
from datetime import datetime, timedelta
import time
import traceback
import warnings
warnings.filterwarnings('ignore')

# 1. 화면 기본 설정
st.set_page_config(page_title="실전 퀀트 대시보드", layout="wide")
st.title("🏆 실전 퀀트 멀티 팩터 대시보드 (전 종목 스캔)")
st.markdown("전체 시장을 분석하여 1~20위는 강력 추천으로, 21위부터는 시장 흐름 파악용으로 분리하여 보여줍니다.")

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# 2. 사이드바 및 실행 버튼
st.sidebar.header("⚙️ 분석 설정")
st.sidebar.info("전체 종목을 꼼꼼히 채점하므로 약 3~5분 정도 소요됩니다.")

st.sidebar.divider() 

st.sidebar.subheader("🔍 타겟 종목 범위 필터")
set_price = st.sidebar.number_input("최대 주가 (원 이하)", min_value=1000, max_value=1000000, value=50000, step=5000)
set_marcap_bn = st.sidebar.number_input("최대 시가총액 (억 원 이하)", min_value=100, max_value=100000, value=5000, step=500)
set_marcap = set_marcap_bn * 100000000 

st.sidebar.divider()

start_button = st.sidebar.button("🚀 전체 시장 종합 분석 시작")

if start_button:
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    fund_df = pd.DataFrame(columns=['EPS', 'PER', 'PBR'])
    foreigner_df = pd.DataFrame(columns=['순매수거래대금'])
    inst_df = pd.DataFrame(columns=['순매수거래대금'])
    
    try:
        progress_text.text("1/4: 최신 거래일 확인 및 재무 데이터 싹쓸이 중...")
        recent_days = fdr.DataReader('005930').tail(1)
        latest_date = recent_days.index[0].strftime("%Y%m%d")
        start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')
        
        try:
            fund_kospi = stock.get_market_fundamental(latest_date, market="KOSPI")
            time.sleep(0.5)
            fund_kosdaq = stock.get_market_fundamental(latest_date, market="KOSDAQ")
            fund_df = pd.concat([fund_kospi, fund_kosdaq])
        except:
            st.warning("⚠️ 현재 한국거래소(KRX) 주말 점검으로 '재무 데이터'를 가져올 수 없어 차트 점수만으로 분석합니다.")
            
        progress_bar.progress(25)
        
        progress_text.text("2/4: 외국인 및 기관 수급 장부 확보 중...")
        
        try:
            foreigner_kospi = stock.get_market_net_purchases_of_equities_by_ticker(latest_date, latest_date, "KOSPI", "외국인")
            time.sleep(0.5)
            foreigner_kosdaq = stock.get_market_net_purchases_of_equities_by_ticker(latest_date, latest_date, "KOSDAQ", "외국인")
            foreigner_df = pd.concat([foreigner_kospi, foreigner_kosdaq])
            
            time.sleep(0.5)
            inst_kospi = stock.get_market_net_purchases_of_equities_by_ticker(latest_date, latest_date, "KOSPI", "기관합계")
            time.sleep(0.5)
            inst_kosdaq = stock.get_market_net_purchases_of_equities_by_ticker(latest_date, latest_date, "KOSDAQ", "기관합계")
            inst_df = pd.concat([inst_kospi, inst_kosdaq])
        except:
            st.warning("⚠️ 현재 한국거래소(KRX) 주말 점검으로 '수급 데이터'를 가져올 수 없어 차트 점수만으로 분석합니다.")
            
        progress_bar.progress(50)
        
        progress_text.text(f"3/4: 기초 대상 {set_price:,}원 이하, {set_marcap_bn:,}억 이하
