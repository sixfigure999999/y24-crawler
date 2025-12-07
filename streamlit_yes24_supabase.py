import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time
import random
from datetime import datetime
from supabase import create_client, Client
import json


# ==========================================
# 페이지 설정
# ==========================================
st.set_page_config(
    page_title="Y24 도서 크롤러",
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

    /* 신규 도서 카드 스타일 */
    .book-card-new {
        background: white;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(255,77,77,0.3);
        margin-bottom: 20px;
        border: 3px solid #ff4d4d;
        background: linear-gradient(135deg, #fff5f5 0%, #ffffff 100%);
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


def save_crawl_data(supabase: Client, all_books, crawl_time):
    """크롤링 데이터를 Supabase에 저장"""
    try:
        data = {
            'crawl_time': crawl_time,
            'books_data': json.dumps(all_books, ensure_ascii=False)
        }
        supabase.table('crawl_history').insert(data).execute()
    except Exception as e:
        st.error(f"크롤링 데이터 저장 에러: {e}")


def load_last_crawl_data(supabase: Client):
    """마지막 크롤링 데이터 불러오기"""
    try:
        response = supabase.table('crawl_history').select('*').order('crawl_time', desc=True).limit(1).execute()
        if response.data:
            last_data = response.data[0]
            return json.loads(last_data['books_data']), last_data['crawl_time']
        return None, None
    except Exception as e:
        st.error(f"데이터 불러오기 에러: {e}")
        return None, None


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

    # 앱 시작 시 마지막 크롤링 데이터 자동 로드
    if 'all_books' not in st.session_state:
        last_books, last_time = load_last_crawl_data(supabase)
        if last_books and last_time:
            st.session_state['all_books'] = last_books
            st.session_state['crawl_time'] = last_time
            st.info(f"✅ 마지막 수집 데이터를 불러왔습니다: {last_time}")

    # 사이드바 설정
    st.sidebar.header("⚙️ 설정")

    # 전체 선택 체크박스
    st.sidebar.subheader("카테고리 선택 (중복 선택 가능)")

    select_elementary = st.sidebar.checkbox("초등", value=True)
    select_middle = st.sidebar.checkbox("중등", value=True)
    select_high = st.sidebar.checkbox("고등", value=True)

    # 한 줄당 책 개수 조절
    cols_per_row = st.sidebar.slider("한 줄당 표시 개수", min_value=2, max_value=8, value=6, step=1)

    # 선택된 카테고리 목록
    selected_categories = []
    if select_elementary:
        selected_categories.append("초등")
    if select_middle:
        selected_categories.append("중등")
    if select_high:
        selected_categories.append("고등")

    # 크롤링 버튼
    if st.sidebar.button("🔄 크롤링 시작", type="primary", use_container_width=True, disabled=len(selected_categories)==0):
        if len(selected_categories) == 0:
            st.warning("⚠️ 최소 1개 카테고리를 선택하세요!")
        else:
            progress_bar = st.progress(0, "크롤링 준비 중...")
            all_books = {}
            crawl_time = datetime.now().strftime('%Y.%m.%d - %H:%M')

            with st.spinner("데이터 수집 중..."):
                for cat in selected_categories:
                    st.info(f"📚 {cat} 카테고리 크롤링 중...")
                    books = crawl_yes24(categories[cat], supabase, progress_bar)
                    all_books[cat] = books

            # 크롤링 데이터 저장
            save_crawl_data(supabase, all_books, crawl_time)

            st.session_state['all_books'] = all_books
            st.session_state['crawl_time'] = crawl_time
            st.session_state['cols_per_row'] = cols_per_row
            progress_bar.empty()

            total_count = sum(len(books) for books in all_books.values())
            st.success(f"✅ 총 {total_count}권의 책을 수집했습니다!")

    # 선택된 열 개수 업데이트
    if 'all_books' in st.session_state:
        st.session_state['cols_per_row'] = cols_per_row

    # 데이터가 있을 때만 표시
    if 'all_books' in st.session_state and st.session_state['all_books']:
        all_books = st.session_state['all_books']
        crawl_time = st.session_state.get('crawl_time', datetime.now().strftime('%Y.%m.%d - %H:%M'))
        cols_per_row = st.session_state.get('cols_per_row', 4)

        # 수집 시간 표시
        st.markdown(f"**📅 수집 시간:** {crawl_time}")

        st.divider()

        # 전체 도서 수 계산
        total_books = sum(len(books) for books in all_books.values())

        # 카테고리 필터 버튼
        st.subheader(f"📖 도서 목록 (총 {total_books}권)")

        filter_cols = st.columns(len(all_books) + 1)

        # 세션 상태 초기화
        if 'selected_view_category' not in st.session_state:
            st.session_state['selected_view_category'] = '전체'

        # 전체 버튼
        with filter_cols[0]:
            if st.button("전체", 
                        key="view_all", 
                        use_container_width=True,
                        type="primary" if st.session_state['selected_view_category'] == '전체' else "secondary"):
                st.session_state['selected_view_category'] = '전체'
                st.rerun()

        # 각 카테고리 버튼
        for idx, category in enumerate(all_books.keys(), 1):
            with filter_cols[idx]:
                if st.button(f"{category} ({len(all_books[category])}권)",
                            key=f"view_{category}",
                            use_container_width=True,
                            type="primary" if st.session_state['selected_view_category'] == category else "secondary"):
                    st.session_state['selected_view_category'] = category
                    st.rerun()

        st.divider()

        # 선택된 카테고리에 따라 표시
        selected_view = st.session_state['selected_view_category']

        if selected_view == '전체':
            # 전체 보기
            for category, books in all_books.items():
                display_category_books(category, books, cols_per_row)
        else:
            # 특정 카테고리만 보기
            if selected_view in all_books:
                display_category_books(selected_view, all_books[selected_view], cols_per_row)

    else:
        st.info("👈 왼쪽 사이드바에서 카테고리를 선택하고 크롤링을 시작하세요!")


# ==========================================
# 카테고리별 도서 표시 함수
# ==========================================
def display_category_books(category, books, cols_per_row):
    """카테고리별로 도서를 표시하는 함수"""
    st.subheader(f"📚 {category} ({len(books)}권)")

    # 세션 상태 초기화
    if f'sort_by_{category}' not in st.session_state:
        st.session_state[f'sort_by_{category}'] = 'sale'
        st.session_state[f'sort_order_{category}'] = 'desc'
        st.session_state[f'filter_new_{category}'] = False
        st.session_state[f'group_by_pub_{category}'] = False

    # 필터 및 정렬 옵션
    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])

    with col1:
        # 판매지수 정렬 버튼
        current_sort = st.session_state[f'sort_by_{category}']
        current_order = st.session_state[f'sort_order_{category}']

        if current_sort == 'sale':
            label = f"📊 판매지수 {'▼' if current_order == 'desc' else '▲'}"
            button_type = "primary"
        else:
            label = "📊 판매지수"
            button_type = "secondary"

        if st.button(label, key=f"btn_sale_{category}", use_container_width=True, type=button_type):
            if current_sort == 'sale':
                st.session_state[f'sort_order_{category}'] = 'asc' if current_order == 'desc' else 'desc'
            else:
                st.session_state[f'sort_by_{category}'] = 'sale'
                st.session_state[f'sort_order_{category}'] = 'desc'
            st.rerun()

    with col2:
        # 발행일 정렬 버튼
        if current_sort == 'date':
            label = f"📅 발행일 {'▼' if current_order == 'desc' else '▲'}"
            button_type = "primary"
        else:
            label = "📅 발행일"
            button_type = "secondary"

        if st.button(label, key=f"btn_date_{category}", use_container_width=True, type=button_type):
            if current_sort == 'date':
                st.session_state[f'sort_order_{category}'] = 'asc' if current_order == 'desc' else 'desc'
            else:
                st.session_state[f'sort_by_{category}'] = 'date'
                st.session_state[f'sort_order_{category}'] = 'desc'
            st.rerun()

    with col3:
        # 신규 도서 필터 버튼
        filter_new = st.session_state[f'filter_new_{category}']
        new_label = "🆕 신규만 ON" if filter_new else "🆕 신규만"
        new_type = "primary" if filter_new else "secondary"

        if st.button(new_label, key=f"btn_new_{category}", use_container_width=True, type=new_type):
            st.session_state[f'filter_new_{category}'] = not filter_new
            st.rerun()

    with col4:
        # 출판사별 그룹 버튼
        group_by_pub = st.session_state[f'group_by_pub_{category}']
        group_label = "🏢 출판사별 ON" if group_by_pub else "🏢 출판사별"
        group_type = "primary" if group_by_pub else "secondary"

        if st.button(group_label, key=f"btn_group_{category}", use_container_width=True, type=group_type):
            st.session_state[f'group_by_pub_{category}'] = not group_by_pub
            st.rerun()

    with col5:
        # 출판사 선택
        selected_publisher = st.selectbox("출판사", 
            ["전체"] + sorted(list(set([b['publisher'] for b in books]))),
            key=f"pub_{category}")

    # 필터링
    filtered_books = books
    if st.session_state[f'filter_new_{category}']:
        filtered_books = [b for b in filtered_books if b['is_new']]
    if selected_publisher != "전체":
        filtered_books = [b for b in filtered_books if b['publisher'] == selected_publisher]

    # 정렬
    sort_by = st.session_state[f'sort_by_{category}']
    sort_order = st.session_state[f'sort_order_{category}']

    if sort_by == 'sale':
        filtered_books = sorted(filtered_books, key=lambda x: x['sale_int'], reverse=(sort_order == 'desc'))
    else:
        filtered_books = sorted(filtered_books, key=lambda x: x['date_int'], reverse=(sort_order == 'desc'))

    st.info(f"📊 필터링 결과: **{len(filtered_books)}권**")

    # 출판사별 그룹핑
    if st.session_state[f'group_by_pub_{category}']:
        publishers = {}
        for book in filtered_books:
            pub = book['publisher']
            if pub not in publishers:
                publishers[pub] = []
            publishers[pub].append(book)

        for pub_name in sorted(publishers.keys()):
            with st.expander(f"📚 {pub_name} ({len(publishers[pub_name])}권)", expanded=True):
                display_books(publishers[pub_name], cols_per_row)
    else:
        display_books(filtered_books, cols_per_row)

    st.divider()


# ==========================================
# 도서 표시 함수
# ==========================================
def display_books(books, cols_per_row=4):
    for i in range(0, len(books), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, book in enumerate(books[i:i+cols_per_row]):
            with cols[j]:
                with st.container():
                    new_badge = '<span class="new-badge">NEW</span>' if book['is_new'] else ''

                    if book['is_new']:
                        st.markdown(f"""
                        <div style="border: 3px solid #ff4d4d; border-radius: 8px; padding: 5px; background: linear-gradient(135deg, #fff5f5 0%, #ffffff 100%);">
                            <img src="{book['img']}" style="width: 100%; border-radius: 5px;">
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.image(book['img'], use_container_width=True)

                    st.markdown(f"**[{book['title']}]({book['link']})**{new_badge}", unsafe_allow_html=True)
                    st.caption(f"{book['publisher']} | {book['date_text']}")

                    color_class = get_sale_color_class(book['sale_int'])
                    st.markdown(f"<div class='{color_class}' style='font-weight:900;'>{book['sale_text']}</div>", unsafe_allow_html=True)

                    st.divider()


if __name__ == "__main__":
    main()
