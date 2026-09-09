import streamlit as st
import requests
import calendar
from datetime import datetime, date
import re

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 디자인 CSS 적용
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="한 달 급식 달력 & 검색기",
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
        min-height: 240px;
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
    .highlight-card {
        border: 2px solid #FF9800 !important;
        background-color: #FFF8E1 !important;
    }
    .meal-title-lunch { color: #1976D2; font-weight: bold; margin-top: 6px; }
    .meal-title-dinner { color: #D32F2F; font-weight: bold; margin-top: 6px; }
    .meal-title-other { color: #388E3C; font-weight: bold; margin-top: 6px; }
    .meal-content { font-size: 0.85rem; line-height: 1.35; color: #333333; }
    .nutr-badge {
        font-size: 0.75rem;
        color: #2E7D32;
        background-color: #E8F5E9;
        border-radius: 4px;
        padding: 4px 6px;
        margin-top: 6px;
        border: 1px solid #C8E6C9;
        line-height: 1.3;
    }
    .no-meal { color: #9E9E9E; font-size: 0.85rem; font-style: italic; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. 알레르기 및 영양성분 파싱 함수 (강화 버전)
# -----------------------------------------------------------------------------
ALLERGY_DICT = {
    "1": "난류", "2": "우유", "3": "메밀", "4": "땅콩", "5": "대두",
    "6": "밀", "7": "고등어", "8": "게", "9": "새우", "10": "돼지고기",
    "11": "복숭아", "12": "토마토", "13": "아황산류", "14": "호두", "15": "닭고기",
    "16": "쇠고기", "17": "오징어", "18": "조개류", "19": "잣"
}

def replace_allergy_numbers(menu_text, convert=True):
    """메뉴 문자열 내 알레르기 번호를 식재료명으로 치환합니다."""
    if not menu_text:
        return ""
    
    menu_text = menu_text.replace("<br/>", "\n")
    if not convert:
        return menu_text

    def convert_match(match):
        numbers = re.findall(r'\d+', match.group())
        converted_names = [ALLERGY_DICT.get(num, num) for num in numbers]
        return f"({','.join(converted_names)})"

    lines = menu_text.split('\n')
    converted_lines = []
    for line in lines:
        line_converted = re.sub(r'[\d\.]+$', convert_match, line.strip())
        line_converted = re.sub(r'\([\d\.]+\)', convert_match, line_converted)
        converted_lines.append(line_converted)
        
    return '\n'.join(converted_lines)

def parse_nutrition_info(nutr_str, cal_str):
    """
    NEIS API 영양정보(NUTR_INFO)와 칼로리정보(CAL_INFO)를 파싱하여 탄단지 및 칼로리를 반환합니다.
    다양한 예외 포맷(줄바꿈, 띄어쓰기 등)을 모두 지원합니다.
    """
    if not nutr_str and not cal_str:
        return "영양정보 없음"
    
    # 태그 및 불필요 문법 정리
    clean_nutr = nutr_str.replace("<br/>", " ").replace("\n", " ").replace("\r", " ") if nutr_str else ""
    
    # 탄수화물, 단백질, 지방 유연한 정규표현식 추출 (유닛 g 및 공백 유무에 유연하게 대응)
    carb = re.search(r'탄수화물\s*\(?[gG]?\)?\s*[:\s]\s*([\d\.]+)', clean_nutr)
    protein = re.search(r'단백질\s*\(?[gG]?\)?\s*[:\s]\s*([\d\.]+)', clean_nutr)
    fat = re.search(r'지방\s*\(?[gG]?\)?\s*[:\s]\s*([\d\.]+)', clean_nutr)
    
    carb_val = f"{carb.group(1)}g" if carb else None
    protein_val = f"{protein.group(1)}g" if protein else None
    fat_val = f"{fat.group(1)}g" if fat else None
    cal_val = cal_str if cal_str else ""

    # 세 파라미터가 모두 정상 추출된 경우
    if carb_val and protein_val and fat_val:
        return f"🔥 {cal_val}<br/>🌾탄: {carb_val} | 🥩단: {protein_val} | 🥑지: {fat_val}"
    
    # 만약 정규식 파싱 실패 시 원본 문자열에서 주요 단어만 요약하여 보여줌
    if clean_nutr:
        # 주요 영양소 항목 텍스트 축약
        short_info = clean_nutr
        for old, new in [("탄수화물(g)", "탄"), ("단백질(g)", "단"), ("지방(g)", "지"), (" : ", ":")]:
            short_info = short_info.replace(old, new)
        return f"🔥 {cal_val}<br/>{short_info[:60]}..." if cal_val else short_info[:80]

    return f"🔥 {cal_val}" if cal_val else "영양정보 없음"

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

st.sidebar.markdown("---")

# 기능 옵션 토글
show_nutrition = st.sidebar.toggle("영양성분(탄·단·지) 표시", value=True)
convert_allergy = st.sidebar.toggle("알레르기 식품명으로 변환", value=False)

# 알레르기 대응표 안내
with st.sidebar.expander("ℹ️ 알레르기 번호-식재료 대응표"):
    st.caption("식품위생법에 따른 19가지 알레르기 유발 성분 번호입니다.")
    for code, name in ALLERGY_DICT.items():
        st.text(f"{code:2s} : {name}")

# -----------------------------------------------------------------------------
# 5. 상단 메뉴 설정 (연도, 월, 급식 종류, 메뉴 검색)
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

# 🔍 메뉴 검색 입력창
search_keyword = st.text_input("🔍 급식 메뉴 검색 (예: 돈까스, 닭갈비, 케이크)", "").strip()

st.markdown("---")

# -----------------------------------------------------------------------------
# 6. 달력 데이터 조회 및 파싱
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
        
        # NEIS API 필드 추출 (없을 경우 빈값 처리)
        nutr_info = row.get("NUTR_INFO", "")
        cal_info = row.get("CAL_INFO", "")
        
        if ymd not in meal_dict:
            meal_dict[ymd] = {}
            
        meal_dict[ymd][meal_name] = {
            "dish": dish_name,
            "nutr": parse_nutrition_info(nutr_info, cal_info)
        }

except Exception as api_err:
    st.error(f"❌ [API 통신 오류] {api_err}")
    st.stop()

# -----------------------------------------------------------------------------
# 7. 주간 달력 렌더링
# -----------------------------------------------------------------------------
try:
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(selected_year, selected_month)
    weekday_names = ["월", "화", "수", "목", "금"]

    # 검색 결과 요약 안내
    if search_keyword:
        matched_count = sum(
            1 for day_meals in meal_dict.values()
            for meal_info in day_meals.values()
            if search_keyword.lower() in meal_info["dish"].lower()
        )
        st.info(f"💡 **'{search_keyword}'** 검색 결과: 총 **{matched_count}회** 등장합니다. (해당 날짜 강조 표시)")

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
                
                # 검색어 포함 여부 체크
                contains_search = False
                if search_keyword and ymd_str in meal_dict:
                    for meal_info in meal_dict[ymd_str].values():
                        if search_keyword.lower() in meal_info["dish"].lower():
                            contains_search = True
                            break
                
                # 카드 CSS 클래스 결정
                if contains_search:
                    card_class = "day-card highlight-card"
                elif is_today:
                    card_class = "day-card today-card"
                else:
                    card_class = "day-card"
                    
                today_badge_html = '<span class="today-badge">TODAY</span>' if is_today else ''
                
                header_html = f"""
                <div class="{card_class}">
                    <div class="date-header">
                        {selected_month}/{day_num} ({weekday_names[idx]}) {today_badge_html}
                    </div>
                """
                
                body_html = ""
                
                if ymd_str in meal_dict:
                    day_meals = meal_dict[ymd_str]
                    has_matching_meal = False
                    
                    for meal_name, meal_info in day_meals.items():
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
                            
                        raw_menu = meal_info["dish"]
                        processed_menu = replace_allergy_numbers(raw_menu, convert_allergy)
                        
                        # 검색어가 포함된 메뉴명 하이라이트
                        if search_keyword and search_keyword.lower() in processed_menu.lower():
                            pattern = re.compile(re.escape(search_keyword), re.IGNORECASE)
                            processed_menu = pattern.sub(f"<mark>{search_keyword}</mark>", processed_menu)
                            
                        formatted_menu = processed_menu.replace('\n', '<br/>')
                        
                        body_html += f"""
                        <div class="{title_class}">[{meal_name}]</div>
                        <div class="meal-content">{formatted_menu}</div>
                        """
                        
                        # 영양성분 표시 옵션
                        if show_nutrition and meal_info["nutr"]:
                            body_html += f'<div class="nutr-badge">{meal_info["nutr"]}</div>'
                        
                    if not has_matching_meal:
                        body_html += '<div class="no-meal">해당 식단 없음</div>'
                else:
                    body_html += '<div class="no-meal">급식 없음</div>'
                    
                footer_html = "</div>"
                st.markdown(header_html + body_html + footer_html, unsafe_allow_html=True)

except Exception as ui_err:
    st.error(f"⚠️ [화면 구성 오류] 달력을 출력하는 동안 오류가 발생했습니다. ({ui_err})")
