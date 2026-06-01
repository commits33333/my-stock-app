import streamlit as st
import os

# 🚨 여기에 가입하신 KRX 일반 아이디와 비밀번호를 반드시 입력하세요.
os.environ['KRX_ID'] = 'bsp5799'
os.environ['KRX_PW'] = 'qlwkej00!!'

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
st.markdown("전체 시장을 분석하여 강력 추천 종목을 스캔합니다.")

# 🚨 [핵심 해결책] 메모리 칩(USB) 장착: 탭을 눌러도 데이터가 날아가지 않게 저장소 생성
if 'scanned_data' not in st.session_state:
    st.session_state.scanned_data = None

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# 2. 사이드바 및 실행 버튼
st.sidebar.header("⚙️ 분석 설정")

scan_mode = st.sidebar.radio(
    "💡 스캔 모드 선택 (현재 시간에 맞게 선택하세요)",
    ("☀️ 오전 실시간 모드 (에러 없음, 차트/거래량 초고속 스캔)",
     "🌙 장 마감 정밀 모드 (오후 4시 이후, 재무/수급 포함 딥스캔)")
)

st.sidebar.divider()

st.sidebar.subheader("🔍 타겟 종목 범위 필터")
set_price = st.sidebar.number_input("최대 주가 (원 이하)", min_value=1000, max_value=1000000, value=50000, step=5000)
set_marcap_bn = st.sidebar.number_input("최대 시가총액 (억 원 이하)", min_value=100, max_value=100000, value=5000, step=500)
set_marcap = set_marcap_bn * 100000000

st.sidebar.divider()

start_button = st.sidebar.button("🚀 전체 시장 종합 분석 시작")

# ==========================================
# 3. 데이터 수집 및 스캔 영역 (버튼 누를 때 1번만 실행)
# ==========================================
if start_button:
    progress_text = st.empty()
    progress_bar = st.progress(0)

    fund_df = pd.DataFrame(columns=['EPS', 'PER', 'PBR'])
    foreigner_df = pd.DataFrame(columns=['순매수거래대금'])
    inst_df = pd.DataFrame(columns=['순매수거래대금'])

    try:
        start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')

        if scan_mode == "🌙 장 마감 정밀 모드 (오후 4시 이후, 재무/수급 포함 딥스캔)":
            progress_text.text("1/4: 재무 및 수급 데이터 싹쓸이 중...")
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
            except Exception as e:
                st.error("🚨 데이터 연동 실패! 오전 실시간 모드로 변경해주세요.")
                st.stop()

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
                progress_text.text(f"3/4: 전 종목 정밀 채점 중... ({i}/{total_count})")

            try:
                fin_score, sup_score, chart_score = 0, 0, 0
                per_val, pbr_val, eps_val = 0, 0, 0
                f_buy, i_buy = 0, 0
                chart_status = "일반/하락추세"
                vol_ratio = 0
                current_price = 0

                df = fdr.DataReader(code, start_date)
                if len(df) >= 60:
                    current_price = int(df['Close'].iloc[-1])
                    df['MA20'] = df['Close'].rolling(window=20).mean()
                    df['MA60'] = df['Close'].rolling(window=60).mean()
                    df['Vol20'] = df['Volume'].rolling(window=20).mean()
                    df['RSI'] = calculate_rsi(df)

                    today = df.iloc[-1]
                    yest = df.iloc[-2]

                    if today['Vol20'] >= 50000 and not pd.isna(today['RSI']):
                        is_정배열 = today['Close'] > today['MA20'] and today['MA20'] > today['MA60']
                        is_바닥탈출 = (yest['MA20'] > today['MA20']) and (today['Close'] > today['MA20'])
                        vol_ratio = today['Volume'] / today['Vol20']

                        if is_정배열:
                            chart_score += 20
                            chart_status = "정배열"
                        elif is_바닥탈출:
                            chart_score += 10
                            chart_status = "바닥탈출"

                        if chart_status != "일반/하락추세":
                            if vol_ratio >= 3: chart_score += 10
                            elif vol_ratio >= 1.5: chart_score += 5

                            rsi_val = today['RSI']
                            if 40 <= rsi_val <= 65: chart_score += 10
                            elif rsi_val > 70: chart_score -= 20

                if scan_mode == "🌙 장 마감 정밀 모드 (오후 4시 이후, 재무/수급 포함 딥스캔)":
                    if code in fund_df.index and not fund_df.empty:
                        per_val = fund_df.loc[code, 'PER']
                        if per_val > 0 and per_val <= 20: fin_score += 15
                    if code in foreigner_df.index and not foreigner_df.empty:
                        f_buy = foreigner_df.loc[code, '순매수거래대금']
                        if f_buy > 0: sup_score += 15
                    if code in inst_df.index and not inst_df.empty:
                        i_buy = inst_df.loc[code, '순매수거래대금']
                        if i_buy > 0: sup_score += 15

                total_score = fin_score + sup_score + chart_score

                all_scored_stocks.append({
                    '종목명': name, '종합점수': total_score,
                    '재무점수': fin_score, '수급점수': sup_score, '차트점수': chart_score,
                    '현재가': current_price, 'PER': round(per_val, 2) if per_val > 0 else 0,
                    # 📌 O/X 대신 보기 편하게 콤마(,) 찍힌 진짜 금액(원)으로 저장!
                    '외인매수(원)': f"{int(f_buy):,}" if f_buy > 0 else "0",
                    '기관매수(원)': f"{int(i_buy):,}" if i_buy > 0 else "0",
                    '차트상태': chart_status, '거래량배수': round(vol_ratio, 1)
                })
            except:
                continue

        progress_bar.progress(100)
        progress_text.success("🎉 스캔 완료!")

        if len(all_scored_stocks) > 0:
            result_df = pd.DataFrame(all_scored_stocks)
            result_df = result_df.sort_values(by=['종합점수', 'PER'], ascending=[False, True]).reset_index(drop=True)
            result_df.insert(0, '순위', range(1, len(result_df) + 1))
            
            # 🚨 [핵심 해결책] 스캔이 다 끝나면 결과를 '메모리 칩'에 쏙 저장합니다!
            st.session_state.scanned_data = result_df
        else:
            st.session_state.scanned_data = None
            st.error("조건에 맞는 종목이 없습니다.")

    except Exception as e:
        st.error("🚨 스캔 중 에러가 발생했습니다.")
        st.code(traceback.format_exc())

# ==========================================
# 4. 화면 출력 영역 (버튼이나 탭을 눌러도 항상 기억을 꺼내서 그림)
# ==========================================
if st.session_state.scanned_data is not None:
    # 저장된 메모리 칩에서 데이터를 꺼내옵니다.
    result_df = st.session_state.scanned_data
    
    top20_df = result_df.head(20)
    rest_df = result_df.iloc[20:]

    tab1, tab2, tab3, tab4 = st.tabs(["🏆 종합 전체 랭킹", "💼 재무/가치 랭킹", "🤝 수급주 랭킹", "📈 차트/타이밍 랭킹"])

    with tab1:
        st.subheader("🌟 [강력 추천 구역] 종합 점수 랭킹 TOP 20")
        st.dataframe(top20_df, use_container_width=True)
        st.divider()
        st.subheader("📊 [전체 스캔 구역] 21위 ~ 나머지 전체 종목")
        st.dataframe(rest_df, use_container_width=True)

    with tab2:
        st.subheader("💼 [재무 TOP 20] 저평가(PER) 우량주")
        fin_sorted = result_df.sort_values(by=['재무점수', 'PER'], ascending=[False, True]).reset_index(drop=True)
        fin_sorted['재무순위'] = range(1, len(fin_sorted) + 1)
        st.dataframe(fin_sorted[['재무순위', '종목명', '재무점수', 'PER', '현재가']].head(20), use_container_width=True)

    with tab3:
        st.subheader("🤝 [수급 TOP 20] 외국인/기관 매수 랭킹")
        sup_sorted = result_df.sort_values(by='수급점수', ascending=False).reset_index(drop=True)
        sup_sorted['수급순위'] = range(1, len(sup_sorted) + 1)
        st.dataframe(sup_sorted[['수급순위', '종목명', '수급점수', '외인매수(원)', '기관매수(원)', '현재가']].head(20), use_container_width=True)

    with tab4:
        st.subheader("📈 [차트 분석] 패턴별 대장주 분리 보기 (TOP 20)")
        
        # 📌 이제 여기서 버튼을 아무리 눌러도 화면이 백지화되지 않습니다!
        foreigner_filter = st.radio(
            "💡 외국인 수급 필터를 선택하세요:",
            ("기본 랭킹 (차트 순수 점수)", "외국인 매수 종목만 랭킹 (차트 + 외인 수급 교집합)"),
            horizontal=True
        )

        if foreigner_filter == "외국인 매수 종목만 랭킹 (차트 + 외인 수급 교집합)":
            # 📌 O가 아니라 '0원'이 아닌 진짜 돈이 들어온 종목으로 필터링
            chart_base_df = result_df[result_df['외인매수(원)'] != "0"]
            st.info("✅ 현재 '외국인 순매수'가 확인된 종목 안에서만 차트 순위를 보여줍니다.")
        else:
            chart_base_df = result_df
            st.info("✅ 수급과 무관하게 전체 종목 대상 '순수 차트 흐름' 순위를 보여줍니다.")

        chart_sub1, chart_sub2, chart_sub3, chart_sub4 = st.tabs([
            "🌟 종합 차트 우수", "↗️ 정배열만 보기", "💎 바닥탈출만 보기", "🔥 거래량 폭발만 보기"
        ])

        display_cols = ['종목명', '차트점수', '차트상태', '거래량배수', '외인매수(원)', '현재가']

        with chart_sub1:
            chart_top = chart_base_df.sort_values(by='차트점수', ascending=False).head(20)
            st.dataframe(chart_top[display_cols], use_container_width=True)
        with chart_sub2:
            trend_top = chart_base_df[chart_base_df['차트상태'] == '정배열'].sort_values(by='차트점수', ascending=False).head(20)
            st.dataframe(trend_top[display_cols], use_container_width=True)
        with chart_sub3:
            reversal_top = chart_base_df[chart_base_df['차트상태'] == '바닥탈출'].sort_values(by='차트점수', ascending=False).head(20)
            st.dataframe(reversal_top[display_cols], use_container_width=True)
        with chart_sub4:
            vol_top = chart_base_df.sort_values(by='거래량배수', ascending=False).head(20)
            st.dataframe(vol_top[['종목명', '거래량배수', '차트상태', '외인매수(원)', '현재가']], use_container_width=True)

else:
    st.write("👈 왼쪽 사이드바에서 가격과 시가총액을 자유롭게 설정하신 후, **[🚀 전체 시장 종합 분석 시작]** 버튼을 눌러주세요!")
