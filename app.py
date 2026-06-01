import streamlit as st
import os

# 🚨 여기에 가입하신 KRX 일반 아이디와 비밀번호를 반드시 입력하세요.
os.environ['KRX_ID'] = 'bsp5799'
os.environ['KRX_PW'] = 'qlwkej00!!'

import FinanceDataReader as fdr
from pykrx import stock
import pandas as pd
from datetime import datetime, timedelta
import traceback
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="실전 퀀트 대시보드", layout="wide")
st.title("🏆 실전 퀀트 멀티 팩터 대시보드 (초정밀 랭킹)")
st.markdown("전체 시장을 분석하여 강력 추천 종목과 전체 흐름을 스캔합니다.")

# ==========================================
# 🚨 점수 산출 방법 도움말 팝업 버튼 (오타 수정 완료)
# ==========================================
with st.popover("💡 점수 산출 방법 도움말 보기"):
    st.markdown("### 🔬 초정밀 멀티 팩터 채점 기준표 (총 100점 만점)")
    
    col1, col2, col3 = st.columns(3) 
    
    with col1:
        st.markdown("""
        #### 💼 1. 재무 점수 (최대 30점)
        * **PER 수익성 (최대 15점)**
          * 5 이하: **15점**
          * 5 초과 ~ 10 이하: **12점**
          * 10 초과 ~ 20 이하: **9점**
          * 20 초과 ~ 설정치 이하: **5점**
        * **PBR 자산우량성 (최대 10점)**
          * 0.5 이하: **10점**
          * 0.5 초과 ~ 1.0 이하: **7점**
          * 1.0 초과 ~ 1.5 이하: **4점**
        * **배당수익률 (최대 5점)**
          * 5% 이상: **5점**
          * 3% 이상 ~ 5% 미만: **3점**
          * 1% 이상 ~ 3% 미만: **1점**
        """)
        
    with col2:
        st.markdown("""
        #### 🤝 2. 수급 점수 (최대 30점)
        * **외국인 순매수 (최대 15점)**
          * 100억 원 이상: **15점**
          * 50억 원 이상: **12점**
          * 10억 원 이상: **9점**
          * 1억 원 이상: **5점**
          * 1억 원 미만 흑자: **2점**
        * **기관 순매수 (최대 15점)**
          * 100억 원 이상: **15점**
          * 50억 원 이상: **12점**
          * 10억 원 이상: **9점**
          * 1억 원 이상: **5점**
          * 1억 원 미만 흑자: **2점**
        """)
        
    with col3:
        st.markdown("""
        #### 📈 3. 차트 점수 (최대 40점)
        * **핵심 추세 패턴 (가장 높은 1개만 적용)**
          * 밥그릇(U자) 반전: **25점**
          * 골든크로스 (5-20일선): **20점**
          * 대세 정배열 흐름: **15점**
          * 단기 바닥탈출: **10점**
          * 20일선 단순회복: **5점**
        * **세력 거래량 동반 (가점)**
          * 평소 거래량의 3배 이상: **+10점**
          * 2배 이상 ~ 3배 미만: **+7점**
          * 1.5배 이상 ~ 2배 미만: **+4점**
          * 1배 이상 ~ 1.5배 미만: **+1점**
        * **RSI 심리 지표 (과열 방지)**
          * 40 이상 ~ 60 이하 (황금진입): **+10점**
          * 30~40 미만 또는 60 초과~70 이하: **+5점**
          * 70 초과 (**초과열 경고**): **-10점 감점**
        """)
    st.info("⚠️ 장중(오전)에는 거래소 트래픽 차단으로 인해 재무/수급 점수가 0점 처리되며, 차트 점수(40점 만점) 위주로 자동 전환되어 채점됩니다.")

st.divider()

if 'scanned_data' not in st.session_state:
    st.session_state.scanned_data = None

st.sidebar.header("⚙️ 분석 설정")
st.sidebar.info("장중에는 거래소 상태에 따라 차트/거래량 위주로 자동 스캔합니다.")
st.sidebar.divider()

st.sidebar.subheader("🔍 타겟 종목 범위 필터")
set_price = st.sidebar.number_input("최대 주가 (원 이하)", min_value=1000, max_value=5000000, value=2000000, step=10000)
set_marcap_bn = st.sidebar.number_input("최대 시가총액 (억 원 이하)", min_value=100, max_value=6000000, value=5000000, step=10000)

set_marcap = set_marcap_bn * 100000000 

st.sidebar.info("💡 현재 세팅: 시총 500조(삼성전자급) 우량주까지 모두 스캔합니다.")

st.sidebar.divider()

st.sidebar.subheader("💼 재무 채점 기준 (가치투자)")
set_per = st.sidebar.number_input("허용할 최대 PER", min_value=5, max_value=200, value=40, step=5)
st.sidebar.info("💡 모든 점수는 수치에 따라 1점 단위까지 정밀하게 차등 지급됩니다.")

st.sidebar.divider()

start_button = st.sidebar.button("🚀 전체 시장 종합 분석 시작")

if start_button:
    progress_text = st.empty()
    progress_bar = st.progress(0)

    fund_df = pd.DataFrame()
    foreigner_df = pd.DataFrame()
    inst_df = pd.DataFrame()
    krx_success = False

    try:
        start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')
        
        progress_text.text("1/4: KRX 재무 및 수급 데이터 요청 중...")
        recent_days = fdr.DataReader('005930').tail(2)
        latest_date = recent_days.index[0].strftime("%Y%m%d")

        try:
            fund_kospi = stock.get_market_fundamental(latest_date, market="KOSPI")
            fund_kosdaq = stock.get_market_fundamental(latest_date, market="KOSDAQ")
            fund_df = pd.concat([fund_kospi, fund_kosdaq])

            foreigner_kospi = stock.get_market_net_purchases_of_equities_by_ticker(latest_date, latest_date, "KOSPI", "외국인")
            foreigner_kosdaq = stock.get_market_net_purchases_of_equities_by_ticker(latest_date, latest_date, "KOSDAQ", "외국인")
            foreigner_df = pd.concat([foreigner_kospi, foreigner_kosdaq])

            inst_kospi = stock.get_market_net_purchases_of_equities_by_ticker(latest_date, latest_date, "KOSPI", "기관합계")
            inst_kosdaq = stock.get_market_net_purchases_of_equities_by_ticker(latest_date, latest_date, "KOSDAQ", "기관합계")
            inst_df = pd.concat([inst_kospi, inst_kosdaq])
            
            krx_success = True
            st.success("✅ KRX 데이터 수집 성공! 완벽한 3박자(재무+수급+차트) 분석을 시작합니다.")
            
        except Exception:
            krx_success = False
            st.warning("⚠️ 현재 장중(오전) 트래픽 폭주로 외국인/재무 데이터를 긁어올 수 없습니다. '차트/거래량' 실시간 스캔으로 자동 전환합니다.")

        progress_bar.progress(30)
        progress_text.text(f"2/4: 기초 대상 종목 세팅 중...")

        krx_list = fdr.StockListing('KRX')
        cond_price = krx_list['Close'] <= set_price
        cond_marcap = krx_list['Marcap'] <= set_marcap
        target_stocks = krx_list[cond_price & cond_marcap]

        total_count = len(target_stocks)
        all_scored_stocks = []

        for i, (index, row) in enumerate(target_stocks.iterrows()):
            code = row['Code']
            name = row['Name']

            if i % 50 == 0:
                current_prog = 30 + int((i / total_count) * 70)
                progress_bar.progress(min(current_prog, 99))
                progress_text.text(f"3/4: 전 종목 초정밀 채점 중... ({i}/{total_count})")

            try:
                fin_score, sup_score, chart_score = 0, 0, 0
                per_val, pbr_val, div_val = 0, 0, 0
                f_buy, i_buy = 0, 0
                chart_status = "일반/하락추세"
                vol_ratio = 0
                current_price = 0
                
                chart_details = []

                df = fdr.DataReader(code, start_date)
                if len(df) >= 60:
                    current_price = int(df['Close'].iloc[-1])
                    df['MA5'] = df['Close'].rolling(window=5).mean()
                    df['MA20'] = df['Close'].rolling(window=20).mean()
                    df['MA60'] = df['Close'].rolling(window=60).mean()
                    df['Vol20'] = df['Volume'].rolling(window=20).mean()
                    df['RSI'] = calculate_rsi(df)

                    today = df.iloc[-1]
                    yest = df.iloc[-2]
                    day10_ago = df.iloc[-11]

                    if today['Vol20'] >= 50000 and not pd.isna(today['RSI']):
                        is_정배열 = today['Close'] > today['MA20'] and today['MA20'] > today['MA60']
                        is_바닥탈출 = (yest['MA20'] > today['MA20']) and (today['Close'] > today['MA20'])
                        is_20일선회복 = today['Close'] > today['MA20']
                        
                        is_골든크로스 = (yest['MA5'] <= yest['MA20']) and (today['MA5'] > today['MA20'])
                        is_밥그릇 = (day10_ago['MA20'] > yest['MA20']) and (today['MA20'] >= yest['MA20']) and (today['Close'] > today['MA60'])
                        
                        vol_ratio = today['Volume'] / today['Vol20']

                        if is_밥그릇:
                            chart_score += 25; chart_status = "밥그릇(U자)"
                            chart_details.append("밥그릇(+25)")
                        elif is_골든크로스:
                            chart_score += 20; chart_status = "골든크로스"
                            chart_details.append("골든크로스(+20)")
                        elif is_정배열: 
                            chart_score += 15; chart_status = "정배열"
                            chart_details.append("정배열(+15)")
                        elif is_바닥탈출: 
                            chart_score += 10; chart_status = "바닥탈출"
                            chart_details.append("바닥탈출(+10)")
                        elif is_20일선회복:
                            chart_score += 5; chart_status = "20일선회복"
                            chart_details.append("20일선회복(+5)")

                        if chart_status != "일반/하락추세":
                            if vol_ratio >= 3.0: 
                                chart_score += 10; chart_details.append("거래량 3배(+10)")
                            elif vol_ratio >= 2.0: 
                                chart_score += 7; chart_details.append("거래량 2배(+7)")
                            elif vol_ratio >= 1.5: 
                                chart_score += 4; chart_details.append("거래량 1.5배(+4)")
                            elif vol_ratio >= 1.0: 
                                chart_score += 1; chart_details.append("거래량 상승(+1)")
                            
                            rsi_val = today['RSI']
                            if 40 <= rsi_val <= 60: 
                                chart_score += 10; chart_details.append("RSI안정(+10)")
                            elif (30 <= rsi_val < 40) or (60 < rsi_val <= 70): 
                                chart_score += 5; chart_details.append("RSI보통(+5)")
                            elif rsi_val > 70: 
                                chart_score -= 10; chart_details.append("RSI과열(-10)")

                chart_detail_str = " + ".join(chart_details) if chart_details else "-"

                if krx_success:
                    if code in fund_df.index and not fund_df.empty:
                        per_val = fund_df.loc[code, 'PER']
                        pbr_val = fund_df.loc[code, 'PBR']
                        div_val = fund_df.loc[code, 'DIV']
                        
                        if 0 < per_val <= 5: fin_score += 15
                        elif 5 < per_val <= 10: fin_score += 12
                        elif 10 < per_val <= 20: fin_score += 9
                        elif 20 < per_val <= set_per: fin_score += 5
                            
                        if 0 < pbr_val <= 0.5: fin_score += 10
                        elif 0.5 < pbr_val <= 1.0: fin_score += 7
                        elif 1.0 < pbr_val <= 1.5: fin_score += 4
                            
                        if div_val >= 5.0: fin_score += 5
                        elif div_val >= 3.0: fin_score += 3
                        elif div_val >= 1.0: fin_score += 1
                        
                    if code in foreigner_df.index and not foreigner_df.empty:
                        f_buy = foreigner_df.loc[code, '순매수거래대금']
                        if f_buy >= 10000000000: sup_score += 15
                        elif f_buy >= 5000000000: sup_score += 12
                        elif f_buy >= 1000000000: sup_score += 9
                        elif f_buy >= 100000000: sup_score += 5
                        elif f_buy > 0: sup_score += 2
                        
                    if code in inst_df.index and not inst_df.empty:
                        i_buy = inst_df.loc[code, '순매수거래대금']
                        if i_buy >= 10000000000: sup_score += 15
                        elif i_buy >= 5000000000: sup_score += 12
                        elif i_buy >= 1000000000: sup_score += 9
                        elif i_buy >= 100000000: sup_score += 5
                        elif i_buy > 0: sup_score += 2

                total_score = fin_score + sup_score + chart_score

                all_scored_stocks.append({
                    '종목코드': code,  # 🚨 종목코드 추가 보관!
                    '종목명': name, 
                    '종합점수': total_score,
                    '재무점수': fin_score, 
                    '수급점수': sup_score, 
                    '차트점수': chart_score,
                    '차트상태': chart_status, 
                    '차트채점내역': chart_detail_str, 
                    '현재가': f"{current_price:,}", 
                    'PER': round(per_val, 2) if per_val > 0 else 0,
                    'PBR': round(pbr_val, 2) if pbr_val > 0 else 0,
                    '배당률(%)': round(div_val, 2) if div_val > 0 else 0,
                    '외인매수(원)': f"{int(f_buy):,}" if f_buy > 0 else "0",
                    '기관매수(원)': f"{int(i_buy):,}" if i_buy > 0 else "0",
                    '거래량배수': round(vol_ratio, 1)
                })
            except:
                continue

        progress_bar.progress(100)
        progress_text.success("🎉 정밀 스캔 완료!")

        if len(all_scored_stocks) > 0:
            result_df = pd.DataFrame(all_scored_stocks)
            
            # 🚨 종목코드를 이용해 네이버 금융 차트 주소 자동 생성!
            result_df['바로가기'] = "https://finance.naver.com/item/main.naver?code=" + result_df['종목코드']
            
            result_df = result_df.sort_values(by=['종합점수', '수급점수', '재무점수', 'PER'], ascending=[False, False, False, True]).reset_index(drop=True)
            result_df.insert(0, '종합순위', range(1, len(result_df) + 1))
            st.session_state.scanned_data = result_df
        else:
            st.session_state.scanned_data = None
            st.error("조건에 맞는 종목이 없습니다.")

    except Exception as e:
        st.error("🚨 스캔 중 에러가 발생했습니다.")
        st.code(traceback.format_exc())

# ==========================================
# 🚨 화면 출력 영역 (링크 버튼 설정 포함)
# ==========================================
if st.session_state.scanned_data is not None:
    result_df = st.session_state.scanned_data

    tab1, tab2, tab3, tab4 = st.tabs(["🏆 종합 전체 랭킹", "💼 재무/가치 랭킹", "🤝 수급주 랭킹", "📈 차트/타이밍 랭킹"])

    # 🚨 끝에 '바로가기' 열 추가
    all_cols = ['종합순위', '종목명', '종합점수', '재무점수', '수급점수', '차트점수', '차트상태', '차트채점내역', '현재가', 'PER', 'PBR', '배당률(%)', '외인매수(원)', '기관매수(원)', '거래량배수', '바로가기']

    # 🚨 스트림릿 마법의 기능: 더러운 URL 주소를 예쁜 클릭 버튼으로 변신시킵니다!
    link_column_config = {
        "바로가기": st.column_config.LinkColumn(
            "📈 네이버 차트",
            help="클릭하면 네이버 금융 해당 종목으로 이동합니다.",
            display_text="🔗 차트 열기"  # 표에는 이 글자만 보임
        )
    }

    with tab1:
        st.subheader("🌟 [강력 추천] 종합 점수 랭킹 TOP 20")
        st.dataframe(result_df[all_cols].head(20), column_config=link_column_config, use_container_width=True)
        st.divider()
        st.subheader("📊 [종합 전체 스캔] 21위 ~ 나머지 전체")
        st.dataframe(result_df[all_cols].iloc[20:], column_config=link_column_config, use_container_width=True)

    with tab2:
        fin_sorted = result_df.sort_values(by=['재무점수', 'PER'], ascending=[False, True]).reset_index(drop=True)
        fin_sorted.insert(0, '재무순위', range(1, len(fin_sorted) + 1))
        fin_cols = ['재무순위'] + all_cols 
        
        st.subheader("💼 [강력 추천] 다중 팩터 고득점 재무 우량주 TOP 20")
        st.dataframe(fin_sorted[fin_cols].head(20), column_config=link_column_config, use_container_width=True)
        st.divider()
        st.subheader("📊 [재무 전체 스캔] 21위 ~ 나머지 전체")
        st.dataframe(fin_sorted[fin_cols].iloc[20:], column_config=link_column_config, use_container_width=True)

    with tab3:
        sup_sorted = result_df.sort_values(by=['수급점수', '외인매수(원)'], ascending=[False, False]).reset_index(drop=True)
        sup_sorted.insert(0, '수급순위', range(1, len(sup_sorted) + 1))
        sup_cols = ['수급순위'] + all_cols 
        
        st.subheader("🤝 [강력 추천] 금액별 차등 채점 - 수급 대장주 TOP 20")
        st.dataframe(sup_sorted[sup_cols].head(20), column_config=link_column_config, use_container_width=True)
        st.divider()
        st.subheader("📊 [수급 전체 스캔] 21위 ~ 나머지 전체")
        st.dataframe(sup_sorted[sup_cols].iloc[20:], column_config=link_column_config, use_container_width=True)

    with tab4:
        st.subheader("📈 [차트 분석] 패턴별 대장주 분리 보기")
        foreigner_filter = st.radio(
            "💡 외국인 수급 필터를 선택하세요:",
            ("기본 랭킹 (차트 순수 점수)", "외국인 매수 종목만 랭킹 (차트 + 외인 수급 교집합)"),
            horizontal=True
        )

        if foreigner_filter == "외국인 매수 종목만 랭킹 (차트 + 외인 수급 교집합)":
            chart_base_df = result_df[result_df['외인매수(원)'] != "0"].reset_index(drop=True)
            st.info("✅ 현재 '외국인 순매수'가 확인된 종목 안에서만 차트 순위를 보여줍니다.")
        else:
            chart_base_df = result_df.copy()
            st.info("✅ 수급과 무관하게 전체 종목 대상 '순수 차트 흐름' 순위를 보여줍니다.")

        chart_sub1, chart_sub2, chart_sub3, chart_sub4 = st.tabs([
            "🌟 종합 차트 우수", "↗️ 정배열/골든크로스", "💎 밥그릇/바닥탈출", "🔥 거래량 폭발"
        ])

        with chart_sub1:
            chart_top = chart_base_df.sort_values(by='차트점수', ascending=False).reset_index(drop=True)
            chart_top.insert(0, '차트순위', range(1, len(chart_top) + 1))
            chart_cols = ['차트순위'] + all_cols
            
            st.subheader("🌟 [차트 TOP 20] 우상향 유력 종목")
            st.dataframe(chart_top[chart_cols].head(20), column_config=link_column_config, use_container_width=True)
            st.divider()
            st.subheader("📊 [차트 전체 스캔] 21위 ~ 나머지 전체")
            st.dataframe(chart_top[chart_cols].iloc[20:], column_config=link_column_config, use_container_width=True)
            
        with chart_sub2:
            trend_top = chart_base_df[chart_base_df['차트상태'].isin(['정배열', '골든크로스'])].sort_values(by='차트점수', ascending=False).reset_index(drop=True)
            trend_top.insert(0, '차트순위', range(1, len(trend_top) + 1))
            
            st.subheader("↗️ [정배열 & 골든크로스 TOP 20]")
            st.dataframe(trend_top[['차트순위'] + all_cols].head(20), column_config=link_column_config, use_container_width=True)
            st.divider()
            st.subheader("📊 [정배열 & 골든크로스 전체 스캔]")
            st.dataframe(trend_top[['차트순위'] + all_cols].iloc[20:], column_config=link_column_config, use_container_width=True)
            
        with chart_sub3:
            reversal_top = chart_base_df[chart_base_df['차트상태'].isin(['바닥탈출', '밥그릇(U자)'])].sort_values(by='차트점수', ascending=False).reset_index(drop=True)
            reversal_top.insert(0, '차트순위', range(1, len(reversal_top) + 1))
            
            st.subheader("💎 [밥그릇 & 바닥탈출 TOP 20]")
            st.dataframe(reversal_top[['차트순위'] + all_cols].head(20), column_config=link_column_config, use_container_width=True)
            st.divider()
            st.subheader("📊 [밥그릇 & 바닥탈출 전체 스캔]")
            st.dataframe(reversal_top[['차트순위'] + all_cols].iloc[20:], column_config=link_column_config, use_container_width=True)
            
        with chart_sub4:
            vol_top = chart_base_df.sort_values(by='거래량배수', ascending=False).reset_index(drop=True)
            vol_top.insert(0, '차트순위', range(1, len(vol_top) + 1))
            
            st.subheader("🔥 [거래량 폭발 TOP 20]")
            st.dataframe(vol_top[['차트순위'] + all_cols].head(20), column_config=link_column_config, use_container_width=True)
            st.divider()
            st.subheader("📊 [거래량 폭발 전체 스캔]")
            st.dataframe(vol_top[['차트순위'] + all_cols].iloc[20:], column_config=link_column_config, use_container_width=True)
else:
    st.write("👈 왼쪽 사이드바에서 가격과 시가총액을 설정하신 후, **[🚀 전체 시장 종합 분석 시작]** 버튼을 눌러주세요!")
