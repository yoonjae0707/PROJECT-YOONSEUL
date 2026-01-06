import requests
import json
import time
import schedule
import os

YT_API_KEY = os.environ.get("YT_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# 치지직용 '브라우저 변장' 헤더
CHZZK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://chzzk.naver.com/"
}

def refresh_all_platforms():
    print("🔄 [YOONSEUL] 통합 플랫폼 데이터 업데이트 시작...")

    try:
        # 1. DB에서 데이터 가져오기
        list_url = f"{SUPABASE_URL}/rest/v1/ARTIST?select=name,youtube_id,chzzk_id,live_platform"
        res = requests.get(list_url, headers=headers)
        
        if res.status_code != 200:
            print(f"❌ Disconnected to Supabase DB: {res.text}")
            return

        artists = res.json()

        for artist in artists:
            name = artist.get('name')
            yt_id = artist.get('youtube_id')
            cz_id = artist.get('chzzk_id')
            live_platform = artist.get('live_platform', '')

            payload = {}

            # YouTube UPDATE PART
            if yt_id:
                yt_url = f"https://www.googleapis.com/youtube/v3/channels?part=statistics,snippet&id={yt_id}&key={YT_API_KEY}"
                yt_res = requests.get(yt_url).json()
                items = yt_res.get('items', [])
                if items:
                    stats = items[0].get('statistics', {})
                    snippet = items[0].get('snippet', {})
                    payload["yt_subs"] = int(stats.get('subscriberCount', 0))
                    payload["youtube_views"] = int(stats.get('viewCount', 0))
                    payload["youtube_ch_name"] = snippet.get('title', '')

            # Chzzk UPDATE PART
            if cz_id and live_platform == "치지직":
                try:
                    cz_url = f"https://api.chzzk.naver.com/service/v1/channels/{cz_id}"
                    # 치지직 전용 헤더 사용
                    cz_res = requests.get(cz_url, headers=CHZZK_HEADERS)
                    
                    if cz_res.status_code == 200:
                        content = cz_res.json().get('content', {})
                        if content:
                            payload["chzzk_followers"] = content.get('followerCount', 0)
                            payload["chzzk_ch_name"] = content.get('channelName', '')
                            payload["live"] = content.get('openLive', False)
                    else:
                        print(f"⚠️ {name}: 치지직 호출 실패 (상태코드: {cz_res.status_code})")
                
                except Exception as cz_err:
                    print(f"❌ {name}: Disconnected to Chzzk API - {cz_err}")

            # DB UPDATE PART
            if payload:
                update_url = f"{SUPABASE_URL}/rest/v1/ARTIST?name=eq.{name}"
                patch_res = requests.patch(update_url, headers=headers, data=json.dumps(payload))
                
                if patch_res.status_code in [200, 204]:
                    print(f"✅ {name}: 통합 업데이트 성공!")
                else:
                    print(f"❌ {name}: DB 수정 실패 ({patch_res.status_code})")
            
            # 아티스트 당 0.5초 대기
            time.sleep(0.5)

    except Exception as e:
        print(f"🔥 ERROR: {e}")

refresh_all_platforms()

def job():
    print(f"\n⏰ [정기 업데이트 시작] {time.strftime('%Y-%m-%d %H:%M:%S')}")
    refresh_all_platforms()

# 업데이트 스케줄 설정 
schedule.every(1).hours.do(job) 

print("🚀 윤슬 자동 업데이트 엔진이 가동되었습니다. (1시간마다 체크 중...)")

# 무한 루프로 스케줄러 실행
while True:
    schedule.run_pending() # 예약된 작업이 있는지 확인
    time.sleep(1) 
