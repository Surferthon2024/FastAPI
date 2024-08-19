from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict
from datetime import date, datetime
import httpx
from bs4 import BeautifulSoup
import asyncio

app = FastAPI()

async def get_post(url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()  # 요청이 실패하면 예외를 발생시킵니다.
        soup = BeautifulSoup(response.text, 'html.parser')
        content_div = soup.find('div', id='conbody')
        if not content_div:
            return ''
        content = '\n'.join([p.get_text(strip=True) for p in content_div.find_all('p')])
        return content

async def get_posts_with_keyword(keyword: str, base_date_str: str) -> List[Dict[str, str]]:
    url = 'https://cs.dongduk.ac.kr/bbs_shop/list.htm?board_code=board3'
    base_date = datetime.strptime(base_date_str, '%Y-%m-%d').date()
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()  # 요청이 실패하면 예외를 발생시킵니다.
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = []
        post_list = soup.select('ul.lst-board.lst-body > li')  # 게시글이 있는 <li> 요소 선택
        
        tasks = []
        for post in post_list:
            title_tag = post.select_one('div.td.col_subject a span')
            date_tag = post.select_one('div.td.inf.col_date')
            
            if title_tag and date_tag:
                title = title_tag.get_text(strip=True)
                date_str = date_tag.get_text(strip=True)
                try:
                    post_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    continue
                
                if keyword.lower() in title.lower() and post_date > base_date:
                    link = post.select_one('div.td.col_subject a')['href']
                    full_link = f"https://cs.dongduk.ac.kr{link}"
                    tasks.append(asyncio.create_task(fetch_post_content(full_link, title, date_str)))
        
        results = await asyncio.gather(*tasks)
        return results

async def fetch_post_content(url: str, title: str, date_str: str) -> Dict[str, str]:
    content = await get_post(url)
    return {
        'title': title,
        'link': url,
        'date': date_str,
        'content': content
    }

# 입력 데이터 모델 정의
class SearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, description="검색할 키워드")
    start_date: date = Field(..., description="등록시점 (YYYY-MM-DD)")

# 출력 데이터 모델 정의
class SearchResult(BaseModel):
    title: str
    link: str
    date: str
    content: str

@app.post("/dongduk-notice/", response_model=List[SearchResult])
async def search_dongduk(request: SearchRequest):
    try:
        results = await get_posts_with_keyword(request.keyword, request.start_date.isoformat())
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 처리 중 오류 발생: {str(e)}")
