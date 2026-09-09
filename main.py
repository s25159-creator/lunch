import streamlit as st
import requests
import calendar
from datetime import datetime, date
import re

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 디자인 CSS 적용
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="한 달 급식 달력 & 추천기",
    page_icon="🍱",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .day-card {
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 15px;
        background-color: #FFFFFF;
        min-height: 200px;
    }
    .today-card {
        border: 2px solid #2E7D32 !important;
        background-color: #F1F8E9 !important;
    }
    .date-header {
        font-weight: bold;
        font-size: 1.05rem;
        border-bottom: 1px solid #EEEEEE;
        padding-bottom: 5px;
        margin-bottom: 8px;
    }
    .today-badge {
        background-color: #2E7D32;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
        margin-left: 5px;
    }
    .search-highlight-card {
        border: 2px solid #FF9800 !important;
        background-color: #FFF8E1 !important;
    }
    .recommend-highlight-card {
        border: 2px solid #E91E63 !important;
        background-color: #FCE4EC !important;
    }
    .meal-title-lunch { color: #1976D2; font-weight: bold; margin-top: 6px; }
    .meal-title-dinner { color: #D32F2F; font-weight: bold; margin-top: 6px; }
    .meal-title-other { color: #388E3C; font-weight: bold; margin-top: 6px; }
    .meal-content { font-size: 0.85rem; line-height: 1.4; color: #333333; }
    .recommend-badge {
        display: inline-block;
        background-color: #E91E63;
        color: white;
        font-size: 0.75rem;
        font-weight: bold;
        padding: 2px 6px;
        border-radius: 4px;
        margin-bottom: 4px;
    }
    .no-meal { color: #9E9E9E; font-size: 0.85rem; font-style: italic; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. 인기 추천 키워드 및 메뉴 정제 함수 정의
# -----------------------------------------------------------------------------
# 학생 선호 인기 급식 키워드
POPULAR_KEYWORDS = [
    "돈가스", "돈까스", "치킨", "닭강정", "떡볶이", "마라탕", "스파게티", "파스타",
    "피자", "햄버거", "탕수육", "짜장", "짬뽕", "갈비", "불고기", "삼겹살",
    "우동", "라멘", "카레", "오므라이스", "아이스크림", "케이크", "와플",
    "푸딩", "마카롱", "에이드", "빙수", "소떡소떡"
]

def clean_menu_only_name(menu_text):
    """
    NEIS 급식 메뉴 텍스트에서 알레르기 번호, 특수문자, 괄호 등을 제거하고 
    순수 메뉴(요리) 이름만 추출합니다.
    """
    if not menu_text:
        return ""

    # HTML 줄바꿈 태그 변환
    lines = menu_text.replace("<br/>", "\n").replace("<br>", "\n").split("\n")
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 1. 괄호 안의 내용 제거 (예: (완), (자율) 등)
        line = re.sub(r'\(.*?\)', '', line)
        
        # 2. 알레르기 숫자 및 마침표 패턴 제거 (예: 1.2.5. 또는 1.5.13 등)
        line = re.sub(r'[\d\.]+', '', line)
        
        # 3. 양옆 공백 및 특수기호 정리
        line = line.strip()
        
        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)

# -----------------------------------------------------------------------------
# 3. API 데이터 호출 함수
# -----------------------------------------------------------------------------
def fetch_meal_data(office_code, school_code, from_ymd, to_ymd):
    """NEIS 나이스 API를 호출하여 한 달치 급식 데이터를 가져옵니다."""
    if "NEIS_KEY" not in st.secrets:
        st.error("🔑 NEIS API 키가 설정되지 않았습니다. `.streamlit/secrets.toml` 파일에 `NEIS_KEY`를 등록해 주세요.")
        st.stop()
        
    api_key = st.secrets["NEIS_KEY"]
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    
    params = {
        "KEY": api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_FROM_YMD": from_ymd,
        "MLSV_TO_YMD": to_ymd
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "mealServiceDietInfo" in data:
            return data["mealServiceDietInfo"][1]["row"]
        elif "RESULT" in data and data["RESULT"]["CODE"] != "INFO-000":
            if data["RESULT"]["CODE"] == "INFO-200":
                return []
            st.warning(f"API 메시지: {data['RESULT']['MESSAGE']}")
            return []
        return []
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"API 통신 실패: 인터넷 연결 또는 NEIS 서버 상태를 확인하세요. ({e})")
    except Exception as e:
        raise Exception(f"응답 데이터 처리 중 오류 발생: {e}")

# -----------------------------------------------------------------------------
# 4. 사이드바 구성
# -----------------------------------------------------------------------------
st.sidebar.title("🏫 학교 및 설정")

office_code = st.sidebar.text_input("시도교육청코드", value="B10")
school_code = st.sidebar.text_input("표준학교코드", value="7010057")

# -----------------------------------------------------------------------------
# 5. 상단 메뉴 설정 (연도, 월, 급식 종류)
# -----------------------------------------------------------------------------
st.title("🍱 우리 학교 한 달 급식 달력")

today = date.today()

col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    selected_year = st.selectbox("연도 선택", range(today.year - 1, today.year + 2), index=1)

with col2:
    selected_month = st.selectbox("월 선택", range(1, 13), index=today.month - 1)

with col3:
    meal_type_filter = st.radio(
        "급식 종류",
        ["전체 보기", "중식만 보기", "석식만 보기"],
        horizontal=True
    )

st.markdown("---")

# -----------------------------------------------------------------------------
# 6. 달력 데이터 조회 및 추천 키워드 매칭
# -----------------------------------------------------------------------------
_, last_day = calendar.monthrange(selected_year, selected_month)
from_ymd = f"{selected_year}{selected_month:02d}01"
to_ymd = f"{selected_year}{selected_month:02d}{last_day:02d}"

meal_dict = {}
try:
    meal_rows = fetch_meal_data(office_code, school_code, from_ymd, to_ymd)
    
    for row in meal_rows:
        ymd = row["MLSV_YMD"]
        meal_name = row["MMEAL_SC_NM"]  # 조식/중식/석식
        dish_name = row["DDISH_NM"]     # 식단 메뉴
        
        if ymd not in meal_dict:
            meal_dict[ymd] = {}
            
        meal_dict[ymd][meal_name] = dish_name

except Exception as api_err:
    st.error(f"❌ [API 통신 오류] {api_err}")
    st.stop()

# -----------------------------------------------------------------------------
# 7. 검색 및 추천 제어 섹션
# -----------------------------------------------------------------------------
search_col, recommend_col = st.columns([2, 1])

with search_col:
    search_keyword = st.text_input("🔍 급식 메뉴 검색 (예: 돈까스, 닭갈비, 케이크)", "").strip()

with recommend_col:
    st.write("✨ **오늘의 추천 기능**")
    btn_recommend = st.button("👑 이번 달 특식/인기 메뉴 추천받기", use_container_width=True)

# 💡 추천 급식 날짜 및 메인 요리 분석
recommended_days = {}
for ymd_key, day_meals in meal_dict.items():
    for m_name, dish_str in day_meals.items():
        found_popular = [kw for kw in POPULAR_KEYWORDS if kw in dish_str]
        if found_popular:
            if ymd_key not in recommended_days:
                recommended_days[ymd_key] = []
            recommended_days[ymd_key].extend(found_popular)

if btn_recommend:
    if recommended_days:
        st.balloons()
        st.subheader("🎉 이번 달 추천 특식 날짜!")
        rec_info_list = []
        for r_ymd, kw_list in sorted(recommended_days.items()):
            r_month = int(r_ymd[4:6])
            r_day = int(r_ymd[6:8])
            unique_kws = list(set(kw_list))
            rec_info_list.append(f"• **{r_month}월 {r_day}일**: {', '.join(unique_kws)}")
        st.success("\n".join(rec_info_list))
    else:
        st.warning("이달의 자동 등록된 인기 키워드 메뉴가 없습니다.")

# -----------------------------------------------------------------------------
# 8. 주간 달력 렌더링
# -----------------------------------------------------------------------------
try:
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(selected_year, selected_month)
    weekday_names = ["월", "화", "수", "목", "금"]

    if search_keyword:
        matched_count = sum(
            1 for day_meals in meal_dict.values()
            for dish_str in day_meals.values()
            if search_keyword.lower() in dish_str.lower()
        )
        st.info(f"💡 **'{search_keyword}'** 검색 결과: 총 **{matched_count}회** 등장합니다. (주황색 테두리 표시)")

    for week in month_days:
        workdays = week[:5]
        if sum(workdays) == 0:
            continue
            
        cols = st.columns(5)
        
        for idx, day_num in enumerate(workdays):
            with cols[idx]:
                if day_num == 0:
                    st.write("")
                    continue
                
                curr_date = date(selected_year, selected_month, day_num)
                ymd_str = curr_date.strftime("%Y%m%d")
                
                is_today = (curr_date == today)
                is_recommended = ymd_str in recommended_days
                
                # 검색어 포함 여부 체크
                contains_search = False
                if search_keyword and ymd_str in meal_dict:
                    for dish_str in meal_dict[ymd_str].values():
                        if search_keyword.lower() in dish_str.lower():
                            contains_search = True
                            break
                
                # 카드 스타일 결정
                if contains_search:
                    card_class = "day-card search-highlight-card"
                elif is_recommended:
                    card_class = "day-card recommend-highlight-card"
                elif is_today:
                    card_class = "day-card today-card"
                else:
                    card_class = "day-card"
                    
                today_badge_html = '<span class="today-badge">TODAY</span>' if is_today else ''
                rec_badge_html = '<span class="recommend-badge">👑 강추!</span><br/>' if is_recommended else ''
                
                header_html = f"""
                <div class="{card_class}">
                    {rec_badge_html}
                    <div class="date-header">
                        {selected_month}/{day_num} ({weekday_names[idx]}) {today_badge_html}
                    </div>
                """
                
                body_html = ""
                
                if ymd_str in meal_dict:
                    day_meals = meal_dict[ymd_str]
                    has_matching_meal = False
                    
                    for meal_name, raw_menu in day_meals.items():
                        if meal_type_filter == "중식만 보기" and meal_name != "중식":
                            continue
                        if meal_type_filter == "석식만 보기" and meal_name != "석식":
                            continue
                            
                        has_matching_meal = True
                        
                        if meal_name == "중식":
                            title_class = "meal-title-lunch"
                        elif meal_name == "석식":
                            title_class = "meal-title-dinner"
                        else:
                            title_class = "meal-title-other"
                            
                        # 오직 메뉴 이름만 깔끔하게 정제
                        processed_menu = clean_menu_only_name(raw_menu)
                        
                        # 검색어가 포함된 경우 노란색 하이라이트
                        if search_keyword and search_keyword.lower() in processed_menu.lower():
                            pattern = re.compile(re.escape(search_keyword), re.IGNORECASE)
                            processed_menu = pattern.sub(f"<mark>{search_keyword}</mark>", processed_menu)
                            
                        formatted_menu = processed_menu.replace('\n', '<br/>')
                        
                        body_html += f"""
                        <div class="{title_class}">[{meal_name}]</div>
                        <div class="meal-content">{formatted_menu}</div>
                        """
                        
                    if not has_matching_meal:
                        body_html += '<div class="no-meal">해당 식단 없음</div>'
                else:
                    body_html += '<div class="no-meal">급식 없음</div>'
                    
                footer_html = "</div>"
                st.markdown(header_html + body_html + footer_html, unsafe_allow_html=True)

except Exception as ui_err:
    st.error(f"⚠️ [화면 구성 오류] 달력을 출력하는 동안 오류가 발생했습니다. ({ui_err})")
