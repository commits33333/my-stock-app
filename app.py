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
st.title("🏆 실전 퀀트 멀티 팩터 대시보드 (고급 차트 패턴 적용)")
st.markdown("전체 시장을 분석하여 골든크로스, 밥그릇 패턴 등 강력 추천 종목을 스캔합니다.")

# 🚨 메모리 칩 유지
if 'scanned_data' not in st.session_state:
    st.session_state.scanned_data = None

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

st.sidebar.header("⚙️ 분석 설정")
st.sidebar.info("장중에는 거래소 상태에 따라 차트/거래량 위주로 자동 스캔합니다.")
st.sidebar.divider()

st.sidebar.subheader("🔍 타겟 종목 범위 필터")
set_price = st.sidebar.number_input("최대 주가 (원 이하)", min_value=1000, max_value=5000000, value=2000000, step=10000)
set_marcap_bn = st.sidebar.number_input("최대 시가총액 (억 원 이하)", min_value=100, max_value=6000000, value=5000000, step=10000)

# 억 단위 -> 원 단위 변환
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

                df = fdr.DataReader(code, start_date)
                if len(df) >= 60:
                    current_price = int(df['Close'].iloc[-1])
                    # 🚨 5일선 추가
                    df['MA5'] = df['Close'].rolling(window=5).mean()
                    df['MA20'] = df['Close'].rolling(window=20).mean()
                    df['MA60'] = df['Close'].rolling(window=60).mean()
                    df['Vol20'] = df['Volume'].rolling(window=20).mean()
                    df['RSI'] = calculate_rsi(df)

                    today = df.iloc[-1]
                    yest = df.iloc[-2]
                    day10_ago = df.iloc[-11] # 10일 전 데이터

                    if today['Vol20'] >= 50000 and not pd.isna(today['RSI']):
                        is_정배열 = today['Close'] > today['MA20'] and today['MA20'] > today['MA60']
                        is_바닥탈출 = (yest['MA20'] > today['MA20']) and (today['Close'] > today['MA20'])
                        is_20일선회복 = today['Close'] > today['MA20']
                        
                        # 🚨 [신규 패턴 1] 골든크로스 (5일선이 20일선을 상향 돌파)
                        is_골든크로스 = (yest['MA5'] <= yest['MA20']) and (today['MA5'] > today['MA20'])
                        
                        # 🚨 [신규 패턴 2] 밥그릇(라운딩바텀) 패턴
                        # 10일 전엔 20일선 하락 -> 현재 20일선 상승 반전 -> 오늘 주가가 60일선 강력 돌파
                        is_밥그릇 = (day10_ago['MA20'] > yest['MA20']) and (today['MA20'] >= yest['MA20']) and (today['Close'] > today['MA60'])
                        
                        vol_ratio = today['Volume'] / today['Vol20']

                        # 우선순위: 밥그릇 > 골든크로스 > 정배열 > 바닥탈출
                        if is_밥그릇:
                            chart_score += 25; chart_status = "밥그릇(U자)"
                        elif is_골든크로스:
                            chart_score += 20; chart_status = "골든크로스"
                        elif is_정배열: 
                            chart_score += 15; chart_status = "정배열"
                        elif is_바닥탈출: 
                            chart_score += 10; chart_status = "바닥탈출"
                        elif is_20일선회복:
                            chart_score += 5; chart_status = "20일선회복"

                        if chart_status != "일반/하락추세":
                            # 거래량 점수 세분화
                            if vol_ratio >= 3.0: chart_score += 10
                            elif vol_ratio >= 2.0: chart_score += 7
                            elif vol_ratio >= 1.5: chart_score += 4
                            elif vol_ratio >= 1.0: chart_score += 1
                            
                            # RSI 점수 세분화 (과열 감점 포함)
                            rsi_val = today['RSI']
                            if 40 <= rsi_val <= 60: chart_score += 10
                            elif (30 <= rsi_val < 40) or (60 < rsi_val <= 70): chart_score += 5
                            elif rsi_val > 70: chart_score -= 10

                # 다중 팩터 재무/수급 채점 로직
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
                    '종목명': name, '종합점수': total_score,
                    '재무점수': fin_score, '수급점수': sup_score, '차트점수': chart_score,
                    '현재가': current_price, 
                    'PER': round(per_val, 2) if per_val > 0 else 0,
                    'PBR': round(pbr_val, 2) if pbr_val > 0 else 0,
                    '배당률(%)': round(div_val, 2) if div_val > 0 else 0,
                    '외인매수(원)': f"{int(f_buy):,}" if f_buy > 0 else "0",
                    '기관매수(원)': f"{int(i_buy):,}" if i_buy > 0 else "0",
                    '차트상태': chart_status, '거래량배수': round(vol_ratio, 1)
                })
            except:
                continue

        progress_bar.progress(100)
        progress_text.success("🎉 정밀 스캔 완료!")

        if len(all_scored_stocks) > 0:
            result_df = pd.DataFrame(all_scored_stocks)
            result_df = result_df.sort_values(by=['종합점수', '수급점수', '재무점수', 'PER'], ascending=[False, False, False, True]).reset_index(drop=True)
            result_df.insert(0, '순위', range(1, len(result_df) + 1))
            st.session_state.scanned_data = result_df
        else:
            st.session_state.scanned_data = None
            st.error("조건에 맞는 종목이 없습니다.")

    except Exception as e:
        st.error("🚨 스캔 중 에러가 발생했습니다.")
        st.code(traceback.format_exc())

# ==========================================
# 🚨 화면 출력 영역
# ==========================================
if st.session_state.scanned_data is not None:
    result_df = st.session_state.scanned_data

    tab1, tab2, tab3, tab4 = st.tabs(["🏆 종합 전체 랭킹", "💼 재무/가치 랭킹", "🤝 수급주 랭킹", "📈 차트/타이밍 랭킹"])

    all_cols = ['순위', '종목명', '종합점수', '재무점수', '수급점수', '차트점수', '현재가', 'PER', 'PBR', '배당률(%)', '외인매수(원)', '기관매수(원)', '차트상태', '거래량배수']

    with tab1:
        st.subheader("🌟 [강력 추천] 종합 점수 랭킹 TOP 20")
        st.dataframe(result_df[all_cols].head(20), use_container_width=True)
        st.divider()
        st.subheader("📊 [종합 전체 스캔] 21위 ~ 나머지 전체")
        st.dataframe(result_df[all_cols].iloc[20:], use_container_width=True)

    with tab2:
        fin_sorted = result_df.sort_values(by=['재무점수', 'PER'], ascending=[False, True]).reset_index(drop=True)
        fin_sorted['재무순위'] = range(1, len(fin_sorted) + 1)
        fin_display = fin_sorted[['재무순위', '종목명', '재무점수', 'PER', 'PBR', '배당률(%)', '현재가']]
        
        st.subheader("💼 [강력 추천] 다중 팩터 고득점 재무 우량주 TOP 20")
        st.dataframe(fin_display.head(20), use_container_width=True)
        st.divider()
        st.subheader("📊 [재무 전체 스캔] 21위 ~ 나머지 전체")
        st.dataframe(fin_display.iloc[20:], use_container_width=True)

    with tab3:
        sup_sorted = result_df.sort_values(by=['수급점수', '외인매수(원)'], ascending=[False, False]).reset_index(drop=True)
        sup_sorted['수급순위'] = range(1, len(sup_sorted) + 1)
        sup_display = sup_sorted[['수급순위', '종목명', '수급점수', '외인매수(원)', '기관매수(원)', '현재가']]
        
        st.subheader("🤝 [강력 추천] 금액별 차등 채점 - 수급 대장주 TOP 20")
        st.dataframe(sup_display.head(20), use_container_width=True)
        st.divider()
        st.subheader("📊 [수급 전체 스캔] 21위 ~ 나머지 전체")
        st.dataframe(sup_display.iloc[20:], use_container_width=True)

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

        # 🚨 차트 탭 메뉴를 새로운 패턴에 맞게 업데이트
        chart_sub1, chart_sub2, chart_sub3, chart_sub4 = st.tabs([
            "🌟 종합 차트 우수", "↗️ 정배열/골든크로스", "💎 밥그릇/바닥탈출", "🔥 거래량 폭발"
        ])

        display_cols = ['종목명', '차트점수', '차트상태', '거래량배수', '외인매수(원)', '현재가']

        with chart_sub1:
            chart_top = chart_base_df.sort_values(by='차트점수', ascending=False).reset_index(drop=True)
            st.subheader("🌟 [차트 TOP 20] 우상향 유력 종목")
            st.dataframe(chart_top[display_cols].head(20), use_container_width=True)
            st.divider()
            st.subheader("📊 [차트 전체 스캔] 21위 ~ 나머지 전체")
            st.dataframe(chart_top[display_cols].iloc[20:], use_container_width=True)
            
        with chart_sub2:
            trend_top = chart_base_df[chart_base_df['차트상태'].isin(['정배열', '골든크로스'])].sort_values(by='차트점수', ascending=False).reset_index(drop=True)
            st.subheader("↗️ [정배열 & 골든크로스 TOP 20]")
            st.dataframe(trend_top[display_cols].head(20), use_container_width=True)
            st.divider()
            st.subheader("📊 [정배열 & 골든크로스 전체 스캔]")
            st.dataframe(trend_top[display_cols].iloc[20:], use_container_width=True)
            
        with chart_sub3:
            reversal_top = chart_base_df[chart_base_df['차트상태'].isin(['바닥탈출', '밥그릇(U자)'])].sort_values(by='차트점수', ascending=False).reset_index(drop=True)
            st.subheader("💎 [밥그릇 & 바닥탈출 TOP 20]")
            st.dataframe(reversal_top[display_cols].head(20), use_container_width=True)
            st.divider()
            st.subheader("📊 [밥그릇 & 바닥탈출 전체 스캔]")
            st.dataframe(reversal_top[display_cols].iloc[20:], use_container_width=True)
            
        with chart_sub4:
            vol_top = chart_base_df.sort_values(by='거래량배수', ascending=False).reset_index(drop=True)
            st.subheader("🔥 [거래량 폭발 TOP 20]")
            st.dataframe(vol_top[['종목명', '거래량배수', '차트상태', '외인매수(원)', '현재가']].head(20), use_container_width=True)
            st.divider()
            st.subheader("📊 [거래량 폭발 전체 스캔]")
            st.dataframe(vol_top[['종목명', '거래량배수', '차트상태', '외인매수(원)', '현재가']].iloc[20:], use_container_width=True)
else:
    st.write("👈 왼쪽 사이드바에서 가격과 시가총액을 설정하신 후, **[🚀 전체 시장 종합 분석 시작]** 버튼을 눌러주세요!")
