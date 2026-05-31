
import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import time

# 화면 넓게 쓰기 설정
st.set_page_config(page_title="나만의 조건검색기", layout="wide")

st.title("🏆 나만의 실전 주식 조건검색기")
st.markdown("한국거래소(KRX) 실시간 데이터를 바탕으로 3대 트렌드 종목을 발굴합니다.")

# 1. 왼쪽 사이드바 (조건 설정판)
st.sidebar.header("🔍 필터 조건 설정")
max_price = st.sidebar.slider("주가 상한선 (원)", 1000, 100000, 50000, step=1000)
max_marcap = st.sidebar.slider("시가총액 상한선 (억 원)", 500, 10000, 5000)

st.sidebar.markdown("---")
st.sidebar.header("📈 차트 공식 선택")
st.sidebar.info("버튼을 누르면 아래 선택된 공식에 맞는 종목을 분류하여 보여줍니다.")
apply_attack = st.sidebar.checkbox("🔥 공격형 (거래량 폭발)", value=True)
apply_stable = st.sidebar.checkbox("🍏 안정형 (정배열 우상향)", value=True)
apply_reverse = st.sidebar.checkbox("💎 역발상형 (바닥 탈출)", value=True)

# 2. 검색 시작 버튼
if st.sidebar.button("🚀 실시간 검색 시작 (클릭)"):
    
    # 여기서부터는 진짜 분석이 시작되는 영역입니다.
    st.info("데이터 분석을 시작합니다. 종목 수에 따라 3~5분 정도 소요될 수 있습니다...")
    
    # 진행 상황을 보여주는 바(Bar) 생성
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 3. 주식 데이터 불러오기 및 기본 필터링
    krx_list = fdr.StockListing('KRX')
    cond_price = krx_list['Close'] <= max_price
    cond_marcap = krx_list['Marcap'] <= (max_marcap * 100000000) # 억 단위 변환
    final_stocks = krx_list[cond_price & cond_marcap]
    
    total_count = len(final_stocks)
    start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')
    result_list = []
    
    # 4. 차트 분석 루프 시작
    for i, (index, row) in enumerate(final_stocks.iterrows()):
        code = row['Code']
        name = row['Name']
        
        # 진행률 바 업데이트 (화면이 멈춘게 아님을 보여줌)
        current_progress = int(((i + 1) / total_count) * 100)
        progress_bar.progress(current_progress)
        status_text.text(f"분석 진행 중: {i+1} / {total_count} 종목 완료 ({name})")
        
        try:
            df = fdr.DataReader(code, start_date)
            if len(df) < 60: continue
                
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA60'] = df['Close'].rolling(window=60).mean()
            df['Vol20'] = df['Volume'].rolling(window=20).mean()
            
            today = df.iloc[-1]
            yest = df.iloc[-2]
            
            if today['Volume'] == 0 or today['Vol20'] < 30000: continue
                
            volume_ratio = round(today['Volume'] / today['Vol20'], 2)
            change_rate = round(((today['Close'] - yest['Close']) / yest['Close']) * 100, 2)
            
            is_정배열 = today['Close'] > today['MA20'] and today['MA20'] > today['MA60']
            is_거래량폭발 = today['Volume'] >= (today['Vol20'] * 3)
            is_바닥탈출 = (yest['MA20'] > today['MA20']) and (today['Close'] > today['MA20'])
            
            if is_정배열 or is_거래량폭발 or is_바닥탈출:
                result_list.append({
                    '종목명': name, '현재가': int(today['Close']), 
                    '당일상승률(%)': change_rate, '거래량배수': volume_ratio,
                    '정배열': is_정배열, '바닥탈출': is_바닥탈출
                })
                
        except:
            continue
            
    progress_bar.empty()
    status_text.success("🎉 분석이 모두 완료되었습니다!")
    
    # 5. 분석된 데이터를 화면에 표(Table)로 뿌려주기
    if len(result_list) > 0:
        all_df = pd.DataFrame(result_list)
        
        # 화면을 3개의 탭으로 나누기
        tab1, tab2, tab3 = st.tabs(["🔥 공격형 TOP 10", "🍏 안정형 TOP 10", "💎 역발상형 TOP 10"])
        
        with tab1:
            if apply_attack:
                attack_df = all_df.sort_values(by='거래량배수', ascending=False).head(10)[['종목명', '현재가', '당일상승률(%)', '거래량배수']]
                st.dataframe(attack_df, use_container_width=True)
            else:
                st.warning("왼쪽 필터에서 공격형 공식을 체크해 주세요.")
                
        with tab2:
            if apply_stable:
                stable_filter = (all_df['정배열'] == True) & (all_df['당일상승률(%)'] >= 0) & (all_df['당일상승률(%)'] <= 5)
                stable_df = all_df[stable_filter].sort_values(by='거래량배수', ascending=False).head(10)[['종목명', '현재가', '당일상승률(%)', '거래량배수']]
                st.dataframe(stable_df, use_container_width=True)
            else:
                st.warning("왼쪽 필터에서 안정형 공식을 체크해 주세요.")
                
        with tab3:
            if apply_reverse:
                reversal_df = all_df[all_df['바닥탈출'] == True].sort_values(by='당일상승률(%)', ascending=False).head(10)[['종목명', '현재가', '당일상승률(%)', '거래량배수']]
                st.dataframe(reversal_df, use_container_width=True)
