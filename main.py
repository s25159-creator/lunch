import streamlit as st
import requests
import datetime
import calendar
import re

# -----------------------------------------------------------------------------
# 1. 기본 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="월간 학교 급식 달력", page_icon="📅", layout="wide")
st.title("📅 우리 학교 월간 급식 달력")
st.caption("급식 메뉴 검색, 이달의 특식 추천, 탄단지 영양 정보까지 한눈에 확인합니다.")

# -----------------------------------------------------------------------------
# 2. 알레르기 및 영양성분/인기 키워드 데이터 정의
# -----------------------------------------------------------------------------
ALLERGY_MAP = {
    1: "난류", 2: "우유", 3: "메밀", 4: "땅콩", 5: "대두",
    6: "밀", 7: "고등어", 8: "게", 9: "새우", 10: "돼지고기",
    11: "복숭아", 12: "토마토", 13: "아황산류", 14: "호두", 15: "닭고기",
    16: "쇠고기", 17: "오징어", 18: "조개류(굴/전복/홍합 포함)", 19: "잣",
}

# 인기 메뉴 추천용 키워드
POPULAR_KEYWORDS = [
    "돈가스", "돈까스", "치킨", "닭강정", "떡볶이", "마라탕", "스파게티", "파스타",
    "피자", "햄버거", "탕수육", "짜장", "짬뽕", "갈비", "불고기", "삼겹살",
    "우동", "라멘", "카레", "오므라이스", "아이스크림", "케이크", "와플",
    "푸딩", "마카롱", "에이드", "빙수", "소떡소떡"
]

# 대표 식재료 키워드 기반 탄단지(g) 추정 DB (1인분 기준)
NUTRIENT_DB = {
    "밥": (50, 4, 1),
    "돈가스": (30, 20, 18), "돈까스": (30, 20, 18),
    "치킨": (15, 22, 16), "닭": (10, 20, 10),
    "돼지": (5, 18, 15), "제육": (8, 18, 12), "불고기": (8, 18, 10), "갈비": (6, 17, 14),
    "소고기": (3, 20, 12), "쇠고기": (3, 20, 12),
    "생선": (3, 16, 6), "오징어": (2, 15, 2), "새우": (2, 14, 1),
    "두부": (2, 8, 4), "달걀": (1, 6, 5), "계란": (1, 6, 5),
    "스파게티": (55, 12, 10), "파스타": (55, 12, 10), "짜장": (50, 10, 12), "짬뽕": (45, 12, 8),
    "떡볶이": (45, 5, 4), "마라탕": (20, 12, 15), "카레": (35, 8, 7),
    "국": (5, 3, 2), "찌개": (6, 6, 4), "탕": (5, 5, 3),
    "김치": (3, 1, 0), "나물": (4, 2, 2), "샐러드": (5, 2, 4),
    "우유": (10, 6, 6), "케이크": (30, 3, 10), "빵": (25, 4, 5)
}

def estimate_macronutrients(dish_list):
    """메뉴 목록에서 키워드를 분석하여 탄단지(g) 합계를 추정합니다."""
    total_carbs, total_protein, total_fat = 0, 0, 0
    matched = False
    
    for dish in dish_list:
        # 알레르기 수식어 및 괄호 제거 후 순수 메뉴명 추출
        clean_dish = re.sub(r'\(.*?\)|:orange\[.*?\]', '', dish).strip()
        for kw, (c, p, f) in NUTRIENT_DB.items():
            if kw in clean_dish:
                total_carbs += c
                total_protein += p
                total_fat += f
                matched = True
                break
                
    if not matched:
        # 기본 한 끼 표준 급식 추정치 적용
        return 70, 22, 15
        
    return total_carbs, total_protein, total_fat

def replace_allergy_codes(dish_text, convert_to_text=True):
    """메뉴명 뒤의 알레르기 번호를 감지하여 한글 식재료명으로 치환하거나 제거합니다."""
    if not dish_text:
        return dish_text

    def convert_match(match):
        raw = match.group(0)
        nums = re.findall(r"\d+", raw)
        if convert_to_text:
            allergens = [ALLERGY_MAP[int(n)] for n in nums if int(n) in ALLERGY_MAP]
            if allergens:
                return f" :orange[[{', '.join(allergens)}]]"
            return raw
        else:
            return "" # 알레르기 표기 미사용 시 제거

    pattern = r"\(?(\d+\.)+\)?"
    return re.sub(pattern, convert_match, dish_text)

# -----------------------------------------------------------------------------
# 3. 사이드바 설정
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ 학교 정보 설정")
office_code = st.sidebar.text_input("시도교육청코드", value="T10", help="기본값: 제주특별자치도교육청(T10)")
school_code = st.sidebar.text_input("표준학교코드", value="9290088", help="기본값: 제주중앙고등학교(9290088)")

st.sidebar.markdown("---")
st.sidebar.subheader("🍽️ 급식 및 영양 설정")
show_allergen_names = st.sidebar.toggle(
    "알레르기 식품명 표시", value=True,
    help="체크 시 숫자(예: 1. 5.) 대신 [난류, 대두] 형태로 변환하여 표시합니다.",
)
show_macros = st.sidebar.toggle(
    "탄단지 추정 정보 표시", value=True,
    help="식단 메뉴 기반으로 예상 탄수화물, 단백질, 지방 함량(g)을 표시합니다.",
)

with st.sidebar.expander("📖 나이스 알레르기 번호 안내표"):
    table_md = "\n".join([f"- **{k}번**: {v}" for k, v in ALLERGY_MAP.items()])
    st.markdown(table_md)

# -----------------------------------------------------------------------------
# 4. 필터 및 검색/추천 섹션
# -----------------------------------------------------------------------------
today = datetime.date.today()
col_y, col_m, col_filter = st.columns([1, 1, 2])
with col_y:
    year = st.selectbox("연도 선택", options=list(range(today.year - 1, today.year + 2)), index=1)
with col_m:
    month = st.selectbox("월 선택", options=list(range(1, 13)), index=today.month - 1)
with col_filter:
    meal_filter = st.radio(
        "급식 종류 선택", options=["전체 보기", "중식만 보기", "석식만 보기"], index=0, horizontal=True,
    )

# 🔍 검색 & 추천 UI 추가
col_search, col_rec = st.columns([2, 1])
with col_search:
    search_keyword = st.text_input("🔍 급식 메뉴 검색", placeholder="예: 돈까스, 스파게티, 닭갈비").strip()

with col_rec:
    st.write("✨ **인기 급식 추천**")
    btn_recommend = st.button("👑 이달의 특식/추천 메뉴 보기", use_container_width=True)

# -----------------------------------------------------------------------------
# 5. API 데이터 호출 함수
# -----------------------------------------------------------------------------
def fetch_monthly_meals(key, ofcdc_code, schul_code, yr, mo):
    """선택한 월의 1일부터 말일까지의 급식을 조회합니다."""
    _, last_day = calendar.monthrange(yr, mo)
    from_ymd = f"{yr}{mo:02d}01"
    to_ymd = f"{yr}{mo:02d}{last_day:02d}"

    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "KEY": key, "Type": "json", "pIndex": 1, "pSize": 100,
        "ATPT_OFCDC_SC_CODE": ofcdc_code, "SD_SCHUL_CODE": schul_code,
        "MLSV_FROM_YMD": from_ymd, "MLSV_TO_YMD": to_ymd,
    }
    response = requests.get(url, params=params, timeout=7)
    return response.json()

if "NEIS_KEY" not in st.secrets:
    st.error("⚠️ Streamlit Secrets에 `NEIS_KEY`가 설정되어 있지 않습니다.")
    st.stop()

neis_key = st.secrets["NEIS_KEY"]

try:
    with st.spinner(f"{year}년 {month}월 급식 정보를 불러오는 중..."):
        res_data = fetch_monthly_meals(neis_key, office_code, school_code, year, month)

    meal_dict = {}
    recommended_days = {} # {ymd: [인기키워드]}

    if "mealServiceDietInfo" in res_data:
        rows = res_data["mealServiceDietInfo"][1]["row"]
        for row in rows:
            ymd = row.get("MLSV_YMD")
            meal_type = row.get("MMEAL_SC_NM", "급식")
            dish = row.get("DDISH_NM", "")

            # 인기 특식 키워드 감지
            found_popular = [kw for kw in POPULAR_KEYWORDS if kw in dish]
            if found_popular:
                recommended_days.setdefault(ymd, []).extend(found_popular)

            formatted_dish = replace_allergy_codes(dish, convert_to_text=show_allergen_names)
            dish_lines = [d.strip() for d in formatted_dish.replace("<br/>", "\n").split("\n") if d.strip()]

            meal_dict.setdefault(ymd, {})[meal_type] = dish_lines

    # 추천 버튼 클릭 이벤트 처리
    if btn_recommend:
        if recommended_days:
            st.balloons()
            st.subheader(f"🎉 {year}년 {month}월 추천 특식 제공일")
            rec_text = []
            for r_ymd, kws in sorted(recommended_days.items()):
                m_val = int(r_ymd[4:6])
                d_val = int(r_ymd[6:8])
                unique_kws = list(set(kws))
                rec_text.append(f"• **{m_val}월 {d_val}일**: {', '.join(unique_kws)}")
            st.success("\n".join(rec_text))
        else:
            st.info("이달에는 등록된 대표 인기 특식 메뉴가 없습니다.")

    month_cal = calendar.monthcalendar(year, month)
    weekdays_kr = ["월", "화", "수", "목", "금"]

    # 검색 결과 안내
    if search_keyword:
        match_count = sum(
            1 for day_meals in meal_dict.values()
            for dishes in day_meals.values()
            for d in dishes if search_keyword.lower() in d.lower()
        )
        st.info(f"🔍 **'{search_keyword}'** 검색 결과: 총 **{match_count}개**의 메뉴가 검색되었습니다.")

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 6. 주간 달력 출력
    # -------------------------------------------------------------------------
    for week in month_cal:
        cols = st.columns(5)
        has_school_day = False

        for i in range(5):
            day = week[i]
            with cols[i]:
                if day == 0:
                    st.empty()
                else:
                    has_school_day = True
                    ymd_str = f"{year}{month:02d}{day:02d}"
                    day_meals = meal_dict.get(ymd_str, {})
                    is_today = (year == today.year and month == today.month and day == today.day)
                    is_rec_day = ymd_str in recommended_days

                    # 검색어 일치 여부 확인
                    has_search_match = False
                    if search_keyword and day_meals:
                        for dishes in day_meals.values():
                            if any(search_keyword.lower() in d.lower() for d in dishes):
                                has_search_match = True
                                break

                    with st.container(border=True):
                        # 날짜 헤더 및 배지 표시
                        header_str = f"**{month}월 {day}일 ({weekdays_kr[i]})**"
                        if is_today:
                            header_str += " :orange-background[**TODAY**]"
                        if is_rec_day:
                            header_str += " ⭐"
                        if has_search_match:
                            header_str += " 🔍"
                        
                        st.markdown(header_str)
                        st.divider()

                        if not day_meals:
                            st.caption("급식 없음 (휴업/방학)")
                        else:
                            displayed_count = 0

                            # 중식 출력
                            if meal_filter in ["전체 보기", "중식만 보기"] and "중식" in day_meals:
                                displayed_count += 1
                                st.markdown(":blue[**🍚 중식**]")
                                for dish in day_meals["중식"]:
                                    if search_keyword and search_keyword.lower() in dish.lower():
                                        st.markdown(f"<span style='font-size:0.85rem; background-color:#FFE082;'>• {dish}</span>", unsafe_allow_html=True)
                                    else:
                                        st.markdown(f"<span style='font-size:0.85rem;'>• {dish}</span>", unsafe_allow_html=True)
                                
                                # 탄단지 함량 추정 표시
                                if show_macros:
                                    c, p, f = estimate_macronutrients(day_meals["중식"])
                                    st.caption(f"📊 예상 탄: {c}g | 단: {p}g | 지: {f}g")

                            # 석식 출력
                            if meal_filter in ["전체 보기", "석식만 보기"] and "석식" in day_meals:
                                displayed_count += 1
                                if meal_filter == "전체 보기" and "중식" in day_meals:
                                    st.write("")
                                st.markdown(":red[**🌙 석식**]")
                                for dish in day_meals["석식"]:
                                    if search_keyword and search_keyword.lower() in dish.lower():
                                        st.markdown(f"<span style='font-size:0.85rem; background-color:#FFE082;'>• {dish}</span>", unsafe_allow_html=True)
                                    else:
                                        st.markdown(f"<span style='font-size:0.85rem;'>• {dish}</span>", unsafe_allow_html=True)
                                
                                # 탄단지 함량 추정 표시
                                if show_macros:
                                    c, p, f = estimate_macronutrients(day_meals["석식"])
                                    st.caption(f"📊 예상 탄: {c}g | 단: {p}g | 지: {f}g")

                            # 기타 급식(조식 등) 출력
                            if meal_filter == "전체 보기":
                                for m_type, dishes in day_meals.items():
                                    if m_type not in ["중식", "석식"]:
                                        displayed_count += 1
                                        st.markdown(f":green[**🍴 {m_type}**]")
                                        for dish in dishes:
                                            if search_keyword and search_keyword.lower() in dish.lower():
                                                st.markdown(f"<span style='font-size:0.85rem; background-color:#FFE082;'>• {dish}</span>", unsafe_allow_html=True)
                                            else:
                                                st.markdown(f"<span style='font-size:0.85rem;'>• {dish}</span>", unsafe_allow_html=True)
                                        if show_macros:
                                            c, p, f = estimate_macronutrients(dishes)
                                            st.caption(f"📊 예상 탄: {c}g | 단: {p}g | 지: {f}g")

                            if displayed_count == 0:
                                st.caption("해당 식단 없음")

        if has_school_day:
            st.write("")

except requests.exceptions.RequestException as e:
    st.error(f"⚠️ 나이스 API 통신 오류: 네트워크 상태를 확인해 주세요. ({e})")
except Exception as e:
    st.error(f"⚠️ 화면 구성 중 오류가 발생했습니다: {e}")
