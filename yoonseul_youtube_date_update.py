import os
import requests
import json
import time
from datetime import datetime
import pytz

# 1. 환경 변수 로드 (GitHub Secrets와 연결)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
YT_API_KEY = os.environ.get("YT_API_KEY")

# Supabase 공통 헤더
headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

def update_youtube_data():
    print(f"🔄 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] START YOUTUBE DATA SYNC...")

    try:
        # 1. DB에서 유튜브 ID가 있는 아티스트만 가져오기
        list_url = f"{SUPABASE_URL}/rest/v1/ARTIST?select=name,youtube_id"
        res = requests.get(list_url, headers=headers)
        
        if res.status_code != 200:
            print(f"❌ Supabase 연결 실패: {res.text}")
            return

        artists = res.json()

        for artist in artists:
            name = artist.get('name')
            yt_id = artist.get('youtube_id')

            if not yt_id:
                continue

            payload = {}

            # 2. YouTube API 호출
            try:
                yt_url = f"https://www.googleapis.com/youtube/v3/channels?part=statistics,snippet&id={yt_id}&key={YT_API_KEY}"
                yt_res = requests.get(yt_url).json()
                items = yt_res.get('items', [])
                
                if items:
                    stats = items[0].get('statistics', {})
                    snippet = items[0].get('snippet', {})
                    
                    payload["yt_subs"] = int(stats.get('subscriberCount', 0))
                    payload["youtube_views"] = int(stats.get('viewCount', 0))
                    payload["youtube_ch_name"] = snippet.get('title', '')
                    
                    # 한국 시간 기준 업데이트 기록
                    seoul_tz = pytz.timezone('Asia/Seoul')
                    payload["last_updated"] = datetime.now(seoul_tz).strftime('%Y-%m-%d %H:%M:%S')

                    # 3. Supabase DB 업데이트 (PATCH)
                    update_url = f"{SUPABASE_URL}/rest/v1/ARTIST?name=eq.{name}"
                    patch_res = requests.patch(update_url, headers=headers, data=json.dumps(payload))
                    
                    if patch_res.status_code in [200, 204]:
                        print(f"✅ {name}: 구독자 {payload['yt_subs']:,}명 / 조회수 {payload['youtube_views']:,}회 갱신 완료")
                    else:
                        print(f"❌ {name}: DB 수정 실패 ({patch_res.status_code})")
                
                else:
                    print(f"⚠️ {name}: 유튜브 채널 정보를 찾을 수 없음 (ID: {yt_id})")

            except Exception as e:
                print(f"⚠️ {name}: YouTube 데이터 수집 중 에러 - {e}")

            # API 할당량 및 과부하 방지를 위한 짧은 대기
            time.sleep(0.3)

    except Exception as e:
        print(
