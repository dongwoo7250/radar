# 업비트 일봉 데이터를 받아 52주 최고가·역사적 최고가(일봉 고가 기준)를 계산해 data.json으로 저장
# GitHub Actions에서 하루 한 번(09:07 KST) 실행됨. 표준 라이브러리만 사용.
import json, os, time, datetime, urllib.request, urllib.error

API = 'https://api.upbit.com/v1'
OUT = 'data.json'
QUOTES = ('KRW-', 'BTC-', 'USDT-')
DAY = 86400


def get(path):
    for a in range(8):
        try:
            req = urllib.request.Request(API + path, headers={'Accept': 'application/json', 'User-Agent': 'upbit-radar'})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.load(r)
            time.sleep(0.13)  # 초당 10회 제한 아래로
            return data
        except urllib.error.HTTPError as e:
            if e.code in (429, 418, 500, 502, 503, 504):
                time.sleep(2 * (a + 1)); continue
            raise
        except Exception:
            time.sleep(2 * (a + 1))
    raise RuntimeError('요청 실패: ' + path)


def dnum(s):  # '2026-11-19T00:00:00' (UTC) -> 일 번호
    return int(datetime.datetime.strptime(s[:10], '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc).timestamp() // DAY)


def candles(market, count, to=None):
    q = f'/candles/days?market={market}&count={count}'
    if to:
        q += '&to=' + urllib.request.quote(to)
    return get(q)


def main():
    T = int(time.time() // DAY)  # 업비트 일봉 시작(09:00 KST) = UTC 자정
    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding='utf-8')).get('m', {})
        except Exception:
            old = {}

    markets = [x for x in get('/market/all?isDetails=true') if x['market'].startswith(QUOTES)]
    res = {}
    for i, x in enumerate(markets):
        m = x['market']
        try:
            got, to, full = [], None, False
            for _ in range(2):  # 최근 400일
                arr = candles(m, 200, to)
                got += arr
                if len(arr) < 200:
                    full = True; break
                to = arr[-1]['candle_date_time_utc'] + 'Z'
            closes = {}
            for k in got:
                d = dnum(k['candle_date_time_utc'])
                if d < T:
                    closes[d] = k['high_price']
            o = old.get(m)
            if o and o.get('hv') != 1:  # 예전(종가 기준) 데이터는 버리고 다시 계산
                o = None
            if full:
                first = dnum(got[-1]['candle_date_time_utc']) if got else T
                ath_c, ath_d = 0, None
                for d, c in closes.items():
                    if c > ath_c: ath_c, ath_d = c, d
            elif o and o.get('a'):
                first, ath_c, ath_d = o['f'], o['a'], o['ad']
                for d, c in closes.items():
                    if c > ath_c: ath_c, ath_d = c, d
            else:  # 처음 보는 오래된 코인: 전체 이력 받기
                first = None
                ath_c, ath_d = 0, None
                for d, c in closes.items():
                    if c > ath_c: ath_c, ath_d = c, d
                while True:
                    arr = candles(m, 200, to)
                    for k in arr:
                        if k['high_price'] > ath_c:
                            ath_c, ath_d = k['high_price'], dnum(k['candle_date_time_utc'])
                    if arr:
                        first = dnum(arr[-1]['candle_date_time_utc'])
                        to = arr[-1]['candle_date_time_utc'] + 'Z'
                    if len(arr) < 200:
                        break

            def mx(lo):
                best, bd = 0, None
                for d, c in closes.items():
                    if lo <= d <= T - 1 and c > best: best, bd = c, d
                return best, bd
            h1, h1d = mx(T - 364)   # 오늘 기준 52주(364개 마감 일봉)
            h2, h2d = mx(T - 363)   # 내일 기준(어제 종가 추가 전) 대비용
            ev = x.get('market_event') or {}
            warn = 1 if (x.get('market_warning') == 'CAUTION' or ev.get('warning')) else 0
            res[m] = {'hv': 1, 'n': x.get('korean_name', m), 'w': warn, 'f': first,
                      'h1': h1, 'h1d': h1d, 'h2': h2, 'h2d': h2d, 'a': ath_c, 'ad': ath_d}
        except Exception as e:
            print('skip', m, e)
            if m in old:
                res[m] = old[m]
        if i % 50 == 0:
            print(i, '/', len(markets))

    json.dump({'day': T, 'gen': datetime.datetime.utcnow().isoformat() + 'Z', 'm': res},
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('done', len(res))


if __name__ == '__main__':
    main()
