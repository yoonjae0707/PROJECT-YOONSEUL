import requests
import json
import time
from datetime import datetime
import pytz
import os

YT_API_KEY = os.environ.get("YT_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# 치지직용 '브라우저 변장' 헤더
CHZZK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://chzzk.naver.com/"
}

def refresh_all_platforms():
    print(f"🔄 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] YOONSEUL DATA UPDATE...")

    try:
        # 1. DB에서 아티스트 목록 가져오기
        # select 문에 들어가는 컬럼명들은 본인의 Supabase 테이블과 일치해야 합니다.
        list_url = f"{SUPABASE_URL}/rest/v1/ARTIST?select=name,youtube_id,live_id,live_platform"
        res = requests.get(list_url, headers=headers)
        
        if res.status_code != 200:
            print(f"❌ Disconnected to Supabase DB: {res.text}")
            return

        artists = res.json()

        for artist in artists:
            name = artist.get('name')
            yt_id = artist.get('youtube_id')
            l_id = artist.get('live_id') 
            l_platform = artist.get('live_platform', '')

            payload = {}

            # Youtube DATA UPDATE
            if yt_id:
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
                except Exception as e:
                    print(f"⚠️ {name}: YouTube Data Collect Error - {e}")

            # LIVE STRAMING DATA UPDATE - CHZZK (치지직)
            if l_id and l_platform == "치지직":
                try:
                    # 1. 채널 기본 정보 (이름, 팔로워)
                    cz_ch_url = f"https://api.chzzk.naver.com/service/v1/channels/{l_id}"
                    cz_ch_res = requests.get(cz_ch_url, headers=CHZZK_HEADERS).json()
                    ch_content = cz_ch_res.get('content', {})
                    
                    if ch_content:
                        payload["live_ch_name"] = ch_content.get('channelName', '')
                        payload["live_followers"] = ch_content.get('followerCount', 0)

                    # 2. 실시간 라이브 정보 (상태, 시청자 수)
                    cz_live_url = f"https://api.chzzk.naver.com/service/v2/channels/{l_id}/live-detail"
                    cz_live_res = requests.get(cz_live_url, headers=CHZZK_HEADERS).json()
                    live_content = cz_live_res.get('content', {})

                    if live_content:
                        live = live_content.get('status') == "OPEN"
                        payload["live"] = live
                        # 방송 중일 때만 시청자 수 기록, 아니면 0
                        payload["viewer_count"] = live_content.get('concurrentUserCount', 0) if live else 0
                    else:
                        payload["live"] = False
                        payload["viewer_count"] = 0

                except Exception as cz_err:
                    print(f"❌ {name}: Disconnect to Chzzk API - {cz_err}")

            # DB UPATE
            if payload:
                # 업데이트 완료한 한국 시간 추가
                seoul_tz = pytz.timezone('Asia/Seoul')
                payload["last_updated"] = datetime.now(seoul_tz).strftime('%Y-%m-%d %H:%M:%S')

                update_url = f"{SUPABASE_URL}/rest/v1/ARTIST?name=eq.{name}"
                patch_res = requests.patch(update_url, headers=headers, data=json.dumps(payload))
                
                if patch_res.status_code in [200, 204]:
                    # .get(키, 기본값) 형식을 사용하면 데이터가 없어도 에러가 나지 않습니다.
                    is_live = payload.get("live", False)
                    status_icon = "🔴" if is_live else "⚪"
                    
                    # 모든 수치에 .get() 방어막 설치
                    subs = payload.get('yt_subs', 0)
                    yt_views = payload.get('youtube_views', 0)
                    v_count = payload.get('viewer_count', 0)

                    print(f"✅ {name} 업데이트 성공!")
                    print(f"   └ [YouTube] 구독자: {subs:,}명 | 조회수: {yt_views:,}회")
                    print(f"   └ [Live   ] 상태: {status_icon} | 시청자: {v_count:,}명")
                    print("-" * 50)
                else:
                    print(f"❌ {name}: DB 수정 실패 ({patch_res.status_code})")
                    print(f"   └ 원인: {patch_res.text}")
                    
            
            # API 과부하 방지를 위한 미세한 대기
            time.sleep(0.5)

    except Exception as e:
        print(f"🔥 전체 프로세스 에러: {e}")

# 실행부
if __name__ == "__main__":
    refresh_all_platforms()
