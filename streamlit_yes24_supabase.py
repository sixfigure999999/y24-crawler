import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time
import random
from datetime import datetime
from supabase import create_client, Client

# ==========================================
# 페이지 설정
# ==========================================
st.set_page_config(
    page_title="Yes24 도서 크롤러",
    page_icon="📚",
    layout="wide"
)

# ==========================================
# CSS 스타일
# ==========================================
st.markdown("""
<style>
    .book-card {
        background: white;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        margin-bottom: 20px;
        border: 1px solid #ddd;
    }
    .new-badge {
        background: #ff4d4d;
        color: white;
        padding: 4px 8px;
        border-radius: 12px;
        font-weight: 800;
        font-size: 11px;
        display: inline-block;
        margin-left: 8px;
    }
    .sale-10k { color: #888; }
    .sale-30k { color: #28a745; }
    .sale-50k { color: #007bff; }
    .sale-100k { color: #fd7e14; }
    .sale-high { color: #e91e63; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# Supabase 연결
# ==========================================
@st.cache_resource
def init_supabase():
    """Supabase 클라이언트 초기화"""
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

def check_and_save_book(supabase: Client, goods_no):
    """신규 도서 확인 및 저장"""
    try:
        # 기존 데이터 확인
        response = supabase.table('seen_books').select('goods_no').eq('goods_no', goods_no).execute()

        if response.data:
            return False  # 이미 본 책
        else:
            # 새 책 저장
            supabase.table('seen_books').insert({'goods_no': goods_no}).execute()
            return True  # 신규 책
    except Exception as e:
        st.error(f"DB 에러: {e}")
        return False

# ==========================================
# 크롤링 함수
# ==========================================
def crawl_yes24(urls, supabase, progress_bar=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    crawled_data = []
    seen_in_this_run = set()
    total_urls = len(urls)

    for idx, url in enumerate(urls):
        if progress_bar:
            progress_bar.progress((idx + 1) / total_urls, f"크롤링 중... ({idx + 1}/{total_urls})")

        wait_time = random.uniform(1, 2)
        time.sleep(wait_time)

        try:
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.select('li[data-goods-no]')

            for item in items:
                try:
                    goods_no = item['data-goods-no']

                    if goods_no in seen_in_this_run:
                        continue
                    seen_in_this_run.add(goods_no)

                    img_tag = item.select_one('.img_grp img')
                    img_src = img_tag.get('data-original') if img_tag.get('data-original') else img_tag.get('src')

                    title_tag = item.select_one('.gd_name')
                    title = title_tag.text.strip()
                    link = "https://www.yes24.com" + title_tag['href']

                    sale_num_tag = item.select_one('.saleNum')
                    sale_num_text = sale_num_tag.text.strip() if sale_num_tag else "판매지수 0"
                    sale_num_int = int(re.sub(r'[^0-9]', '', sale_num_text)) if re.search(r'\d', sale_num_text) else 0

                    pub_tag = item.select_one('.info_pub a')
                    publisher = pub_tag.text.strip() if pub_tag else "기타"

                    date_tag = item.select_one('.info_date')
                    date_text = date_tag.text.strip() if date_tag else ""
                    date_match = re.search(r'(\d{4})년\s*(\d{1,2})월', date_text)
                    if date_match:
                        date_int = int(date_match.group(1)) * 100 + int(date_match.group(2))
                    else:
                        date_int = 0

                    is_new = check_and_save_book(supabase, goods_no)

                    crawled_data.append({
                        'goods_no': goods_no,
                        'img': img_src,
                        'title': title,
                        'link': link,
                        'sale_text': sale_num_text,
                        'sale_int': sale_num_int,
                        'publisher': publisher,
                        'date_text': date_text,
                        'date_int': date_int,
                        'is_new': is_new
                    })

                except Exception as e:
                    continue

        except Exception as e:
            st.error(f"URL 접속 에러: {e}")

    return crawled_data

def get_sale_color_class(sale_num):
    if sale_num <= 10000: return "sale-10k"
    elif sale_num <= 30000: return "sale-30k"
    elif sale_num <= 50000: return "sale-50k"
    elif sale_num <= 100000: return "sale-100k"
    else: return "sale-high"

# ==========================================
# 메인 앱
# ==========================================
def main():
    st.title("📚 Yes24 도서 크롤러")
    st.markdown(f"**업데이트 시간:** {datetime.now().strftime('%Y.%m.%d - %H:%M')}")

    # 카테고리 URL 정의
    categories = {
        "초등": [
            "https://www.yes24.com/product/category/bestseller?categoryNumber=001001044&pageNumber=1&pageSize=120",
            "https://www.yes24.com/product/category/more/001001044?ElemNo=208&ElemSeq=1",
            "https://www.yes24.com/product/category/more/001001044?ElemNo=208&ElemSeq=6"
        ],
        "중등": [
            "https://www.yes24.com/product/category/bestseller?categoryNumber=001001049",
            "https://www.yes24.com/product/category/more/001001049?ElemNo=208&ElemSeq=4",
            "https://www.yes24.com/product/category/more/001001049?ElemNo=208&ElemSeq=3"
        ],
        "고등": [
            "https://www.yes24.com/product/category/bestseller?categoryNumber=001001050&pageNumber=1&pageSize=120",
            "https://www.yes24.com/product/category/more/001001050?ElemNo=208&ElemSeq=3",
            "https://www.yes24.com/product/category/more/001001050?ElemNo=208&ElemSeq=9"
        ]
    }

    # Supabase 초기화
    try:
        supabase = init_supabase()
    except Exception as e:
        st.error(f"⚠️ Supabase 연결 실패: {e}")
        st.info("Streamlit Cloud의 Secrets 설정을 확인하세요!")
        return

    # 사이드바 설정
    st.sidebar.header("⚙️ 설정")
    selected_category = st.sidebar.selectbox("카테고리 선택", list(categories.keys()))

    # 크롤링 버튼
    if st.sidebar.button("🔄 크롤링 시작", type="primary", use_container_width=True):
        progress_bar = st.progress(0, "크롤링 준비 중...")

        with st.spinner("데이터 수집 중..."):
            books = crawl_yes24(categories[selected_category], supabase, progress_bar)
            st.session_state['books'] = books
            st.session_state['category'] = selected_category

        progress_bar.empty()
        st.success(f"✅ {len(books)}권의 책을 수집했습니다!")

    # 데이터가 있을 때만 표시
    if 'books' in st.session_state and st.session_state['books']:
        books = st.session_state['books']
        category = st.session_state.get('category', '도서')

        st.divider()
        st.subheader(f"📖 {category} 도서 목록 ({len(books)}권)")

        # 필터 및 정렬 옵션
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

        with col1:
            sort_option = st.selectbox("정렬 기준", ["판매지수 높은순", "판매지수 낮은순", "최신순", "오래된순"])

        with col2:
            filter_new = st.checkbox("🆕 신규 도서만 보기")

        with col3:
            selected_publisher = st.selectbox("출판사 필터", ["전체"] + sorted(list(set([b['publisher'] for b in books]))))

        with col4:
            group_by_publisher = st.checkbox("출판사별 그룹")

        # 필터링
        filtered_books = books
        if filter_new:
            filtered_books = [b for b in filtered_books if b['is_new']]
        if selected_publisher != "전체":
            filtered_books = [b for b in filtered_books if b['publisher'] == selected_publisher]

        # 정렬
        if "판매지수 높은순" in sort_option:
            filtered_books = sorted(filtered_books, key=lambda x: x['sale_int'], reverse=True)
        elif "판매지수 낮은순" in sort_option:
            filtered_books = sorted(filtered_books, key=lambda x: x['sale_int'])
        elif "최신순" in sort_option:
            filtered_books = sorted(filtered_books, key=lambda x: x['date_int'], reverse=True)
        else:
            filtered_books = sorted(filtered_books, key=lambda x: x['date_int'])

        st.info(f"📊 필터링 결과: **{len(filtered_books)}권**")

        # 출판사별 그룹핑
        if group_by_publisher:
            publishers = {}
            for book in filtered_books:
                pub = book['publisher']
                if pub not in publishers:
                    publishers[pub] = []
                publishers[pub].append(book)

            for pub_name in sorted(publishers.keys()):
                with st.expander(f"📚 {pub_name} ({len(publishers[pub_name])}권)", expanded=True):
                    display_books(publishers[pub_name])
        else:
            display_books(filtered_books)
    else:
        st.info("👈 왼쪽 사이드바에서 카테고리를 선택하고 크롤링을 시작하세요!")

# ==========================================
# 도서 표시 함수
# ==========================================
def display_books(books):
    cols_per_row = 4
    for i in range(0, len(books), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, book in enumerate(books[i:i+cols_per_row]):
            with cols[j]:
                # 신규 뱃지
                new_badge = '<span class="new-badge">NEW</span>' if book['is_new'] else ''

                # 이미지
                st.image(book['img'], use_container_width=True)

                # 제목 (링크 포함)
                st.markdown(f"**[{book['title']}]({book['link']})**{new_badge}", unsafe_allow_html=True)

                # 출판사 및 날짜
                st.caption(f"{book['publisher']} | {book['date_text']}")

                # 판매지수 (색상 적용)
                color_class = get_sale_color_class(book['sale_int'])
                st.markdown(f"<div class='{color_class}' style='font-weight:900;'>{book['sale_text']}</div>", unsafe_allow_html=True)

                st.divider()

if __name__ == "__main__":
    main()
