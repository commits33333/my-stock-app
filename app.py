import streamlit as st
import os
import pandas as pd
from datetime import datetime, timedelta
import traceback
import warnings

warnings.filterwarnings('ignore')

# 🚨기에 가입하신 KRX 일반 아이디와 비밀번호를 입력하세요.
os.environ['KRX_ID'] = 'bsp5799'
os.environ['KRX_PW'] = 'qlwkej00!!'

import FinanceDataReader as fdr
from pykrx import stock

# 스트림릿 페이지 설정
st.set_page_config(page_title="실전 퀀트 멀티 팩터 대시보드", layout="wide")
st.title("🏆 실전 퀀트 멀티 팩터 대시보드")
st.markdown("전체 시장을 입체적으로 분석하여 각 팩터별 최적의 종목을 스캔합니다.")

# ==========================================
# 💡 점수 산출 방법 도움말 팝업 버튼 (정상화 완료)
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
        * **핵심 추세 패턴**
          * 밥그릇(U자) 반전: **25점**
          * 골든크로스 (5-20일선): **20점**
          * 대세 정배열 흐름: **15점**
          * 단기 바닥탈출: **10점**
          * 20일선 단순회복: **5점**
        * **세력 거래량 동반**
          * 평소 거래량의 3배 이상: **+10점**
          * 2배 이상 ~ 3배 미만: **+7점**
          * 1.5배 이상 ~ 2배 미만: **+4점**
          * 1배 이상 ~ 1.5배 미만: **+1점**
        * **RSI 심리 지표**
          * 40 이상 ~ 60 이하 (황금진입): **+10점**
          * 30-40 미만 또는 60 초과-70 이하: **+5점**
          * 70 초과 (초과열 경고): **-10점 감점**
        """)
    st.info("⚠️ 장중(오전)이거나 서버가 막혔을 때는 재무/수급 점수가 0점 처리되며, 차트 점수 위주로 채점됩니다.")

st.divider()

# 세션 상태 초기화
if 'scanned_data' not in st.session_state:
    st.session_state.scanned_data = None
if 'krx_status' not in st.session_state:
    st.session_state.krx_status = True

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    loss = loss.replace(0, 1e-9)  # 0 나누기 방지
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ==========================================
# ⚙️ 사이드바 설정 영역
# ==========================================
st.sidebar.header("⚙️ 분석 설정")

st.sidebar.subheader("⚡ 스캔 범위 모드")
test_mode = st.sidebar.checkbox("1분 고속 테스트 모드 (시총 상위 100개)", value=False)
if test_mode:
    st.sidebar.success("✅ 상위 우량주 100개만 빠르게 검증합니다.")
else:
    st.sidebar.info("🔥 전 종목을 정밀 스캔합니다. (약 20~30분 소요)")

st.sidebar.divider()

st.sidebar.subheader("🔍 타겟 종목 범위 필터")
set_price = st.sidebar.number_input("최대 주가 (원 이하)", min_value=1000, max_value=5000000, value=2000000, step=10000)

st.sidebar.subheader("🛡️ 잡주 방어막 (시가총액)")
min_marcap_bn = st.sidebar.number_input("최소 시가총액 (억 원 이상)", min_value=10, max_value=10000, value=500, step=100)
set_marcap_bn = st.sidebar.number_input("최대 시가총액 (억 원 이하)", min_value=100, max_value=6000000, value=5000000, step=10000)

min_marcap = min_marcap_bn * 100000000
set_marcap = set_marcap_bn * 100000000 

st.sidebar.divider()

st.sidebar.subheader("💼 재무 채점 기준")
set_per = st.sidebar.number_input("허용할 최대 PER", min_value=5, max_value=200, value=40, step=5)
st.sidebar.divider()

start_button = st.sidebar.button("🚀 전체 시장 종합 분석 시작")

# ==========================================
# 📊 데이터 스캔 및 연산 로직
# ==========================================
if start_button:
    progress_text = st.empty()
    progress_bar = st.progress(0)

    fund_df, foreigner_df, inst_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    krx_success = False

    try:
        start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')
        progress_text.text("1/4: KRX 대량 데이터 동기화 중...")
        
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
            st.session_state.krx_status = True
        except Exception:
            krx_success = False
            st.session_state.krx_status = False

        progress_bar.progress(30)
        progress_text.text("2/4: 필터링 조건 기둥 세팅 중...")

        krx_list = fdr.StockListing('KRX').dropna(subset=['Close', 'Marcap'])
        cond_price = krx_list['Close'] <= set_price
        cond_marcap_max = krx_list['Marcap'] <= set_marcap
        cond_marcap_min = krx_list['Marcap'] >= min_marcap
        target_stocks = krx_list[cond_price & cond_marcap_max & cond_marcap_min]
        
        if test_mode:
            target_stocks = target_stocks.sort_values(by='Marcap', ascending=False).head(100)

        total_count = len(target_stocks)
        all_scored_stocks = []

        for i, (index, row) in enumerate(target_stocks.iterrows()):
            code = row['Code']
            name = row['Name']

            if i % 10 == 0:
                current_prog = 30 + int((i / total_count) * 70)
                progress_bar.progress(min(current_prog, 99))
                progress_text.text(f"3/4: 전 종목 핵심 지표 연산 중... ({i}/{total_count})")

            # 불량 및 규격 외 종목 사전 필터링
            if any(x in name for x in ['스팩', '스펙', '우선주', '원전']) or ('제' in name and '호' in name):
                continue

            try:
                df = fdr.DataReader(code, start_date)
                if df.empty or len(df) < 60:
                    continue
                    
                current_price = int(df['Close'].iloc[-1])
                if current_price == 0:
                    continue

                fin_score, sup_score, chart_score = 0, 0, 0
                per_val, pbr_val, div_val, f_buy, i_buy = 0, 0, 0, 0, 0
                chart_status = "일반/하락추세"
                vol_ratio = 0
                chart_details = []

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
                        chart_score += 25; chart_status = "밥그릇(U자)"; chart_details.append("밥그릇(+25)")
                    elif is_골든크로스:
                        chart_score += 20; chart_status = "골든크로스"; chart_details.append("골든크로스(+20)")
                    elif is_정배열: 
                        chart_score += 15; chart_status = "정배열"; chart_details.append("정배열(+15)")
                    elif is_바닥탈출: 
                        chart_score += 10; chart_status = "바닥탈출"; chart_details.append("바닥탈출(+10)")
                    elif is_20일선회복:
                        chart_score += 5; chart_status = "20일선회복"; chart_details.append("20일선회복(+5)")

                    if chart_status != "일반/하락추세":
                        if vol_ratio >= 3.0: chart_score += 10; chart_details.append("거래량 3배(+10)")
                        elif vol_ratio >= 2.0: chart_score += 7; chart_details.append("거래량 2배(+7)")
                        elif vol_ratio >= 1.5: chart_score += 4; chart_details.append("거래량 1.5배(+4)")
                        elif vol_ratio >= 1.0: chart_score += 1; chart_details.append("거래량 상승(+1)")
                        
                        rsi_val = today['RSI']
                        if 40 <= rsi_val <= 60: chart_score += 10; chart_details.append("RSI안정(+10)")
                        elif (30 <= rsi_val < 40) or (60 < rsi_val <= 70): chart_score += 5; chart_details.append("RSI보통(+5)")
                        elif rsi_val > 70: chart_score -= 10; chart_details.append("RSI과열(-10)")

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
                    '종목코드': code, '종목명': name, '종합점수': total_score,
                    '재무점수': fin_score, '수급점수': sup_score, '차트점수': chart_score,
                    '차트상태': chart_status, '차트채점내역': chart_detail_str, 
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
        progress_text.success("🎉 정밀 매트릭스 스캔 완료!")

        if len(all_scored_stocks) > 0:
            result_df = pd.DataFrame(all_scored_stocks)
            result_df['바로가기'] = "https://finance.naver.com/item/main.naver?code=" + result_df['종목코드']
            result_df = result_df.sort_values(by=['종합점수', '수급점수', '재무점수', 'PER'], ascending=[False, False, False, True]).reset_index(drop=True)
            result_df.insert(0, '종합순위', range(1, len(result_df) + 1))
            st.session_state.scanned_data = result_df
        else:
            st.session_state.scanned_data = None
            st.error("설정한 조건 범위 내에 매칭되는 종목이 존재하지 않습니다.")

    except Exception as e:
        st.error("🚨 치명적 런타임 에러가 발생했습니다.")
        st.code(traceback.format_exc())

# ==========================================
# 🚨 데이터 안전 렌더링 함수 (전체 컬럼 일치 기둥 구조)
# ==========================================
def display_safe_dataframe(df, cols, title, link_config):
    st.subheader(f"🌟 [{title} TOP 20]")
    if len(df) == 0:
        st.info("⚠️ 현재 시장에서 해당 조건에 부합하는 타겟 종목이 없습니다.")
        st.dataframe(pd.DataFrame(columns=cols), column_config=link_config, use_container_width=True)
    else:
        st.dataframe(df[cols].head(20), column_config=link_config, use_container_width=True)
        
    st.divider()
    st.subheader(f"📊 [{title} 21위 ~ 나머지 전체]")
    if len(df) <= 20:
        st.info("⚠️ 하위 후속 순위 종목이 존재하지 않습니다.")
        st.dataframe(pd.DataFrame(columns=cols), column_config=link_config, use_container_width=True)
    else:
        st.dataframe(df[cols].iloc[20:], column_config=link_config, use_container_width=True)

# ==========================================
# 🖥️ 메인 화면 뷰 출력 영역
# ==========================================
if st.session_state.scanned_data is not None:
    result_df = st.session_state.scanned_data
    
    if not st.session_state.krx_status:
        st.error("🚨 **[서버 차단 알림] 과도한 중복 요청으로 거래소 노드가 임시 차단 상태입니다.** \n현재는 실시간 차트 점수 위주로 자동 계산 모드가 활성화되어 있습니다. 잠시 후 서버 잠금이 풀리면 재무 및 수급 데이터가 정상 산출됩니다.")

    tab1, tab2, tab3, tab4 = st.tabs(["🏆 종합 전체 랭킹", "💼 재무/가치 랭킹", "🤝 수급주 랭킹", "📈 차트/타이밍 랭킹"])

    # 전 탭 공통 항목 매핑 기둥
    all_cols = ['종합순위', '종목명', '종합점수', '재무점수', '수급점수', '차트점수', '차트상태', '차트채점내역', '현재가', 'PER', 'PBR', '배당률(%)', '외인매수(원)', '기관매수(원)', '거래량배수', '바로가기']

    link_column_config = {
        "바로가기": st.column_config.LinkColumn(
            "📈 네이버 차트",
            help="클릭하면 네이버 금융 새 창으로 직행합니다.",
            display_text="🔗 차트 열기"
        )
    }

    with tab1:
        display_safe_dataframe(result_df, all_cols, "종합 전체 스캔", link_column_config)

    with tab2:
        fin_sorted = result_df.sort_values(by=['재무점수', 'PER'], ascending=[False, True]).reset_index(drop=True)
        display_safe_dataframe(fin_sorted, all_cols, "재무 우량주", link_column_config)

    with tab3:
        sup_sorted = result_df.sort_values(by=['수급점수', '외인매수(원)'], ascending=[False, False]).reset_index(drop=True)
        display_safe_dataframe(sup_sorted, all_cols, "수급 대장주", link_column_config)

    with tab4:
        st.subheader("📈 [차트 분석] 패턴별 대장주 분리 보기")
        
        # 각 차트 스펙트럼별 단독 서브 탭 7개 구축
        chart_sub1, chart_sub2, chart_sub3, chart_sub4, chart_sub5, chart_sub6, chart_sub7 = st.tabs([
            "🌟 종합 차트 우수", "⚡ 골든크로스 포착", "↗️ 대세 정배열", "🥣 밥그릇(U자) 반전", "🌱 단기 바닥탈출", "🔥 거래량 폭발", "🤝 외인매수+차트 교집합"
        ])

        with chart_sub1:
            chart_top = result_df.sort_values(by='차트점수', ascending=False).reset_index(drop=True)
            display_safe_dataframe(chart_top, all_cols, "우상향 유력 종목", link_column_config)
            
        with chart_sub2:
            gc_top = result_df[result_df['차트상태'] == '골든크로스'].sort_values(by='차트점수', ascending=False).reset_index(drop=True)
            display_safe_dataframe(gc_top, all_cols, "골든크로스 포착 종목", link_column_config)
            
        with chart_sub3:
            jb_top = result_df[result_df['차트상태'] == '정배열'].sort_values(by='차트점수', ascending=False).reset_index(drop=True)
            display_safe_dataframe(jb_top, all_cols, "대세 정배열 종목", link_column_config)
            
        with chart_sub4:
            bg_top = result_df[result_df['차트상태'] == '밥그릇(U자)'].sort_values(by='차트점수', ascending=False).reset_index(drop=True)
            display_safe_dataframe(bg_top, all_cols, "밥그릇(U자) 반전 종목", link_column_config)
            
        with chart_sub5:
            bt_top = result_df[result_df['차트상태'] == '바닥탈출'].sort_values(by='차트점수', ascending=False).reset_index(drop=True)
            display_safe_dataframe(bt_top, all_cols, "단기 바닥탈출 종목", link_column_config)
            
        with chart_sub6:
            vol_top = result_df.sort_values(by='거래량배수', ascending=False).reset_index(drop=True)
            display_safe_dataframe(vol_top, all_cols, "거래량 폭발", link_column_config)
            
        with chart_sub7:
            foreign_chart_df = result_df[result_df['외인매수(원)'] != "0"].sort_values(by='차트점수', ascending=False).reset_index(drop=True)
            display_safe_dataframe(foreign_chart_df, all_cols, "외인매수 + 차트 우수 교집합", link_column_config)

else:
    st.write("👈 왼쪽 사이드바에서 필터를 지정한 뒤 **[🚀 전체 시장 종합 분석 시작]**을 눌러 스캔을 시작해 주세요.")
