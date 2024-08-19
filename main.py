from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict
from datetime import date, datetime
import httpx
from bs4 import BeautifulSoup
import asyncio
import json
import openai
from dotenv import load_dotenv
import os

# .env 파일에서 환경 변수 로드
load_dotenv()
# OpenAI API 키를 환경 변수에서 가져옵니다
openai.api_key = os.getenv("OPENAI_API_KEY")


app = FastAPI()



## 동덕여대 컴퓨터학과 크롤링 ##
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



## 강남대학교 공지사항 크롤링 ##
async def get_kangnam_post(url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()  # 요청이 실패하면 예외를 발생시킵니다.
        soup = BeautifulSoup(response.text, 'html.parser')
        content_div = soup.find('div', class_='cont')  # 본문이 담긴 div 클래스로 수정
        if not content_div:
            return ''
        content = '\n'.join([p.get_text(strip=True) for p in content_div.find_all('p')])
        return content

async def get_kangnam_posts_with_keyword(keyword: str, base_date_str: str) -> List[Dict[str, str]]:
    url = 'https://web.kangnam.ac.kr/menu/f19069e6134f8f8aa7f689a4a675e66f.do?searchMenuSeq=0'
    base_date = datetime.strptime(base_date_str, '%Y-%m-%d')
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()  # 요청이 실패하면 예외를 발생시킵니다.
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = []
        post_list = soup.select('.tbody ul')
        
        tasks = []
        for post in post_list:
            title_tag = post.select_one('li:nth-of-type(2) a.detailLink')
            date_tag = post.select_one('li:nth-of-type(6)')
            
            if title_tag and date_tag:
                title = title_tag.get_text(strip=True)
                date_str = date_tag.get_text(strip=True)
                try:
                    post_date = datetime.strptime(date_str, '%y.%m.%d')
                except ValueError:
                    continue
                
                if keyword.lower() in title.lower() and post_date > base_date:
                    data_params = title_tag['data-params']
                    params_dict = json.loads(data_params.replace("'", '"'))
                    enc_menu_seq = params_dict.get('encMenuSeq')
                    enc_menu_board_seq = params_dict.get('encMenuBoardSeq')
                    full_link = f"https://web.kangnam.ac.kr/menu/board/info/f19069e6134f8f8aa7f689a4a675e66f.do?scrtWrtiYn=false&encMenuSeq={enc_menu_seq}&encMenuBoardSeq={enc_menu_board_seq}"
                    tasks.append(asyncio.create_task(fetch_kangnam_post_content(full_link, title, date_str)))
        
        results = await asyncio.gather(*tasks)
        return results

async def fetch_kangnam_post_content(url: str, title: str, date_str: str) -> Dict[str, str]:
    content = await get_kangnam_post(url)
    return {
        'title': title,
        'link': url,
        'date': date_str,
        'content': content
    }

# 입력 데이터 모델 정의
class KangnamSearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, description="검색할 키워드")
    start_date: date = Field(..., description="등록시점 (YYYY-MM-DD)")

# 출력 데이터 모델 정의
class KangnamSearchResult(BaseModel):
    title: str
    link: str
    date: str
    content: str

@app.post("/kangnam-notice/", response_model=List[KangnamSearchResult])
async def search_kangnam(request: KangnamSearchRequest):
    try:
        results = await get_kangnam_posts_with_keyword(request.keyword, request.start_date.isoformat())
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 처리 중 오류 발생: {str(e)}")







## 캘린더 이벤트 추출 기능 ##
class TextRequest(BaseModel):
    text: str

@app.post("/extract_events/")
def extract_calendar_events(request: TextRequest):
    text = request.text
    
    try:
        # ChatCompletion 엔드포인트를 사용하여 gpt-3.5-turbo 모델 호출
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "You will read the following text and pick out important events to save to the calendar."
                },
                {
                    "role": "system", 
                    "content": "Please provide the events in the format ['Event Name | Start Date | End Date', 'Event Name | Start Date | End Date']. If a date is preceded by a '~' or the text includes the word '까지' or similar, consider carefully if today is the correct start date."
                },
                {
                    "role": "user", 
                    "content": text
                }
            ],
            max_tokens=150,
            temperature=0.5,
        )

        # 응답에서 캘린더 이벤트를 추출
        events = response.choices[0].message["content"].strip()
        return {"events": eval(events)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

