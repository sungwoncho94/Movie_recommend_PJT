import requests
from pprint import pprint
from decouple import config
import csv
import bs4
from bs4 import BeautifulSoup

import os
import django
from django.db import transaction

# django setting 파일 설정하기 및 장고 셋업
cur_dir = os.path.dirname(__file__)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lastpjt.settings")
django.setup()

# 모델 임포트는 django setup이 끝난 후에 가능하다. 셋업 전에 import하면 에러난다. db connection 정보가 없어서......
from movies.models import Movie

# 네이버에서 영화 줄거리 가져오는 주소
BASE_URL = 'https://openapi.naver.com/v1/search/movie.json'

# 네이버에서 영화 포스터 가져오는 주소
BASE_IMAGE_URL = 'https://movie.naver.com/movie/bi/mi/photoViewPopup.nhn?movieCode='

clientId = config('CLIENT_ID')
clientSecret = config('CLIENT_SECRET')

HEADERS = {
    'X-Naver-Client-Id': clientId,
    'X-Naver-Client-Secret': clientSecret,
}
query_dict = {}
# 빈 qurey_dict 에 XXXXX (영화제목 값) 을 key로, {'영화코드': XXXXXXXX} 를 value 로 하는 자료 추가할 것
with open('movie.csv', 'r', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        query_dict[row['기간순위']] = {
            '순위': row['순위'],
            # '기간': row['기간'],
            '기간시작': row['기간시작'],
            '기간종료': row['기간종료'],
            '영화코드': row['영화코드'],
            '영화명(국문)': row['영화명(국문)'],
            '기간순위': row['기간순위'],
            '감독명(국문)': row['감독명(국문)'],
            '감독명(영문)': row['감독명(영문)'],
        }

# 네이버에서 영화에 맞는 줄거리와 포스터url를 받아와서 dict에 합친 후,
# model.py의 MakeDB모델을 거쳐 우리 DB에 저장한다
fieldnames = ('순위', '기간시작', '기간종료', '썸네일_이미지의_URL', '영화명(국문)',
              '영화명(영문)', '배우', '영화코드', '하이퍼텍스트_링크', '줄거리')

with open('movie_naver.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    for week_rank, movie_dict in query_dict.items():  # key 값에 대한 for문
        movie_title = movie_dict['영화명(국문)']
        modified_movie_title = '<b>' + movie_title + '</b>'
        movie_director = movie_dict['감독명(국문)']
        
        API_URL = f'{BASE_URL}?query={movie_title}'
        response = requests.get(API_URL, headers=HEADERS).json()
        items = response.get('items')
        
        flag_title = 0
        flag_director = 0
        # 비슷한 영화 제목들을 가진 items를 item으로 돈다
        for item in items:
            # 감독 여러명의 이름
            naver_directors = item.get('director')[:-1]
            # 감독들 중 첫번째 사람의 이름만 뽑았다.
            naver_director = naver_directors.split('|')[0]
            # naver_title = item.get('title')
            # print('itmes개수 = ', len(items))
            # print('감독들 = ', naver_directors)
            # print('감독 = ', naver_director)
            # print('제목 = ', naver_title)
            # (1) item들을 돌면서, 동일한 감독명이 있는지 찾는다.
            # 동일한 감독명을 발견하면 데이터 저장하고 break한다.
            if naver_director == movie_director:
                flag_director = 1
                try:
                    link = item.get('link')
                    # print(link)
                    subtitle = item.get('subtitle')
                    # print(subtitle)
                    actor = ', '.join(item.get('actor')[:-1].split('|'))
                    # print(actor)
                    director = item.get('director')[:-1]
                    # print('director', director)
                    temp = link.split('=')
                    naver_poster_code = temp[-1]
                    # print(naver_poster_code)
                    # 왕큰이미지를 띄우는 팝업링크
                    thumb_url = BASE_IMAGE_URL + naver_poster_code
                    hyp_link2 = requests.get(thumb_url)
                    html2 = hyp_link2.text
                    soup2 = bs4.BeautifulSoup(html2, 'html.parser')
                    poster_url = soup2.a.img['src']
                    movie_dict['하이퍼텍스트_링크'] = link
                    movie_dict['영화명(영문)'] = subtitle
                    movie_dict['배우'] = actor
                    # print(poster_url)
                    movie_dict['썸네일_이미지의_URL'] = poster_url
                    # pprint(movie_dict)
                    hyp_link = requests.get(link)
                    # print(hyp_link.status_code)  /  200 -> 요청이 제대로 가짐
                    # print('2', hyp_link)  /  200 -> 요청이 제대로 가짐
                    html = hyp_link.text  # 응답받은 객체에서 html문서를 string으로 바꾸는 것
                    soup = bs4.BeautifulSoup(html, 'html.parser')
                    # print(soup)
                    content = soup.select_one('div.story_area p.con_tx')
                    movie_dict['줄거리'] = content.text
                except:
                    pass
                break
                # print('---------------')
        # 동일한 감독명이 없다면, naver_title을 사용해서 제목으로 거른다
        if flag_director == 0:
            for item in items:
                naver_title = item.get('title')
                if naver_title == modified_movie_title:
                    flag_title = 1
                    try:
                        link = item.get('link')
                        # print(link)
                        subtitle = item.get('subtitle')
                        # print(subtitle)
                        actor = ', '.join(item.get('actor')[:-1].split('|'))
                        # print(actor)
                        director = item.get('director')[:-1]
                        # print('director', director)
                        temp = link.split('=')
                        naver_poster_code = temp[-1]
                        # print(naver_poster_code)
                        # 왕큰이미지를 띄우는 팝업링크
                        thumb_url = BASE_IMAGE_URL + naver_poster_code
                        hyp_link2 = requests.get(thumb_url)
                        html2 = hyp_link2.text
                        soup2 = bs4.BeautifulSoup(html2, 'html.parser')
                        poster_url = soup2.a.img['src']
                        movie_dict['하이퍼텍스트_링크'] = link
                        movie_dict['영화명(영문)'] = subtitle
                        movie_dict['배우'] = actor
                        # print(poster_url)
                        movie_dict['썸네일_이미지의_URL'] = poster_url
                        # pprint(movie_dict)
                        hyp_link = requests.get(link)
                        # print(hyp_link.status_code)  /  200 -> 요청이 제대로 가짐
                        # print('2', hyp_link)  /  200 -> 요청이 제대로 가짐
                        html = hyp_link.text  # 응답받은 객체에서 html문서를 string으로 바꾸는 것
                        soup = bs4.BeautifulSoup(html, 'html.parser')
                        # print(soup)
                        content = soup.select_one('div.story_area p.con_tx')
                        movie_dict['줄거리'] = content.text
                    except:
                        pass
                    break
        # 감독명도, modified_title도 같은게 없다면, 그냥 items[0]을 뽑자
        if flag_title == 0 and flag_director == 0:
            try:
                item = items[0]
                link = item.get('link')
                # print(link)
                subtitle = item.get('subtitle')
                # print(subtitle)
                actor = ', '.join(item.get('actor')[:-1].split('|'))
                # print(actor)
                director = item.get('director')[:-1]
                # print('director', director)
                temp = link.split('=')
                naver_poster_code = temp[-1]
                # print(naver_poster_code)
                # 왕큰이미지를 띄우는 팝업링크
                thumb_url = BASE_IMAGE_URL + naver_poster_code
                hyp_link2 = requests.get(thumb_url)
                html2 = hyp_link2.text
                soup2 = bs4.BeautifulSoup(html2, 'html.parser')
                poster_url = soup2.a.img['src']
                movie_dict['하이퍼텍스트_링크'] = link
                movie_dict['영화명(영문)'] = subtitle
                movie_dict['배우'] = actor
                # print(poster_url)
                movie_dict['썸네일_이미지의_URL'] = poster_url
                # pprint(movie_dict)
                hyp_link = requests.get(link)
                # print(hyp_link.status_code)  /  200 -> 요청이 제대로 가짐
                # print('2', hyp_link)  /  200 -> 요청이 제대로 가짐
                html = hyp_link.text  # 응답받은 객체에서 html문서를 string으로 바꾸는 것
                soup = bs4.BeautifulSoup(html, 'html.parser')
                # print(soup)
                content = soup.select_one('div.story_area p.con_tx')
                movie_dict['줄거리'] = content.text
            except:
                pass
        # movie_naver.csv 만들기
        writer.writerow(movie_dict)
        # pprint(movie_dict)
        # moive.db에 저장하는 부분
        @transaction.atomic
        def make_model():
            movie = Movie()
            try:
                movie.start_date = movie_dict['기간시작']
            except:
                pass
            try:
                movie.end_date = movie_dict['기간종료']
            except:
                pass
            try:
                movie.rank = movie_dict['순위']
            except:
                pass
            try:
                movie.poster_url = movie_dict['썸네일_이미지의_URL']
            except:
                pass
            try:
                movie.title = movie_dict['영화명(국문)']
            except:
                pass
            try:
                movie.subtitle = movie_dict['영화명(영문)']
            except:
                pass
            try:
                movie.actor = movie_dict['배우']
            except:
                pass
            try:
                movie.movie_code = movie_dict['영화코드']
            except:
                pass
            try:
                movie.naver_movie_url = movie_dict['하이퍼텍스트_링크']
            except:
                pass
            try:
                movie.description = movie_dict['줄거리']
            except:
                pass
            movie.save()
        if __name__ == "__main__":
            make_model()
