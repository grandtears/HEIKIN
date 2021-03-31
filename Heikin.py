# coding: utf-8
import bitmex
import time
import json
from datetime import datetime
import ccxt
import sys
 #ここから設定箇所になります 。
API = bitmex.bitmex(test=False, api_key='　', api_secret='　')
Leverage = 2  # この行で保有資金に対するレバレッジを設定してください。(推奨3倍程度、最大80倍)
LossCut = 0  # エントリー価格から損切りまでの距離。(ドル単位、0で省略)
TrailLine = 0  # エントリー価格からトレーリングストップ発動までの距離。(ドル単位、0で省略)
TrailPeg = 0  # トレーリングストップの価格追従距離。(ドル単位) #ここまでが設定箇所になります 。

# 以下はいじらないでください！！
CCXT = ccxt.bitmex({'apiKey': '', 'secret': ''})
TrailStart = 0
TrailSign = 0

def get_heiken_oc():
    OHLCV = CCXT.publicGetTradeBucketed(
        {'symbol': 'XBTUSD', 'binSize': '1d', 'count': 500, 'reverse': True, 'partial': True})
    ohlcv = []
    for row in OHLCV:
        open, high, low, close = row['open'], row['high'], row['low'], row['close']
        vol, timestamp = row['volume'], row['timestamp']
        if close:
            ohlcv.append([open, high, low, close, vol, timestamp])

    ohlcv[-1] = ohlcv[-1] + [ohlcv[-1][0], ohlcv[-1][3]]
    ohlcv[-2] = ohlcv[-2] + [
        (ohlcv[-1][0] + ohlcv[-1][1] + ohlcv[-1][2] + ohlcv[-1][3]) / 4.0,
        (ohlcv[-2][0] + ohlcv[-2][1] + ohlcv[-2][2] + ohlcv[-2][3]) / 4.0
    ]
    for i in reversed(range(len(ohlcv) - 2)):
        heiken_open = round(((ohlcv[i + 1][-2] + ohlcv[i + 1][-1]) / 2.0 - 0.15) * 2) / 2
        heiken_close = round(((ohlcv[i][0] + ohlcv[i][1] + ohlcv[i][2] + ohlcv[i][3]) / 4.0 + 0.01) * 2) / 2
        ohlcv[i] = ohlcv[i] + [heiken_open, heiken_close]

    return ohlcv[1][6], ohlcv[1][7]

def orderset(price, size, buy=True):
    global TrailStart, TrailSign

    if buy:
        size = size
        sign = 1
    else:
        size = -size
        sign = -1

    common_params = {
        'symbol': 'XBTUSD',
        # 'contingencyType': 'OneUpdatesTheOtherAbsolute',
        # 'clOrdLinkID': 'Entry',
        'orderQty': size,
    }
    orders = [
        # dict(common_params,
        #      price=price - sign,
        #      execInst='ParticipateDoNotInitiate',
        #      ),
        # dict(common_params,
        #      price=price - (sign * 7),
        #      ),
        # dict(common_params,
        #      ordType='StopLimit',
        #      execInst='ParticipateDoNotInitiate,LastPrice',
        #      stopPx=price + (sign * 1.5),
        #      price=price + sign,
        #      ),
        dict(common_params,
             price=price + (sign * 50),
             )
    ]
    if LossCut != 0:
        orders.append(dict(common_params,
                           ordType='Stop',
                           stopPx=price - (sign * LossCut),
                           orderQty=-size * 2,
                           execInst='LastPrice, ReduceOnly'
                           ))

    if TrailPeg != 0:
        TrailStart = price
        TrailSign = sign

        # orders.append(dict(contingencyType='OneTriggersTheOther',
        #                    clOrdLinkID='Trail',
        #                    symbol='XBTUSD',
        #                    ordType='LimitIfTouched',
        #                    orderQty=-sign,
        #                    stopPx=price + (sign * (TrailLine - 3)),
        #                    price=price + (sign * TrailLine),
        #                    execInst='LastPrice,ReduceOnly'
        #                    ))
        # orders.append(dict(clOrdLinkID='Trail',
        #                    symbol='XBTUSD',
        #                    pegPriceType='TrailingStopPeg',
        #                    pegOffsetValue=-sign * TrailPeg,
        #                    orderQty=-size * 2,
        #                    execInst='LastPrice,ReduceOnly',
        #                    ))
    return orders

print('初回エントリーは日足更新時(9:00)です。')

D1_stopper = 0
pre_INYOU = 0
IN, YOU = -1, 1
starttime = time.time()
now = int(time.time()) - (int(time.time()) % 86400) + 50  # 最初だけ1日1回タイマーを即突破させる

while True:  ###1日ループ
    try:
        if 10 <= now % 86400 <= 300 and D1_stopper == 0:  # 1日1回タイマー
            HEIKIN_Open, HEIKIN_Close = get_heiken_oc()

            print('確認用_平均足OPEN：', HEIKIN_Open)
            print('確認用_平均足CLOSE：', HEIKIN_Close)
            INYOU = YOU if HEIKIN_Open <= HEIKIN_Close else IN

            try:
                p = API.Position.Position_get(filter=json.dumps({'symbol': 'XBTUSD'})).result()[0][0]
                pos = p['currentQty']
            except Exception:
                pos = 0

            q = API.OrderBook.OrderBook_getL2(symbol='XBTUSD', depth=1).result()[0]
            ask_price, bid_price = q[0]['price'], q[1]['price']
            Balance = API.User.User_getMargin().result()[0]['marginBalance']
            Lot = Balance * ask_price * Leverage // 100000000

            if Lot <= 30:
                print('GAME OVER')
                sys.exit()

            if INYOU == YOU and pos == 0 and pre_INYOU != INYOU:  # ノーポジ初回起動陽線
                API.Order.Order_cancelAll().result()
                orders = orderset(ask_price, Lot, buy=True)
                API.Order.Order_newBulk(orders=json.dumps(orders)).result()
                print('平均足は陽線、ヘーキンの教えを信じるのです')
            if INYOU == IN and pos == 0 and pre_INYOU != INYOU:  # ノーポジ初回起動陰線
                API.Order.Order_cancelAll().result()
                orders = orderset(bid_price, Lot, buy=False)
                API.Order.Order_newBulk(orders=json.dumps(orders)).result()
                print('平均足は陰線、ヘーキンの教えを信じるのです')

            if INYOU == YOU and pos > 0:  # 日足がYOU線かつ+pos
                print('平均足は陽線、ヘーキンの教えを信じるのです')
                print('ポジションを継続します')
            if INYOU == YOU and pos < 0:  # 日足がYOU線かつ-pos
                API.Order.Order_cancelAll().result()
                orders = orderset(ask_price, abs(pos) + Lot, buy=True)
                API.Order.Order_newBulk(orders=json.dumps(orders)).result()
                print('平均足は陽線、ヘーキンの教えを信じるのです')
                print('ポジションを取り直します')

            if INYOU == IN and pos > 0:  # 日足がINN線かつ+pos
                API.Order.Order_cancelAll().result()
                orders = orderset(bid_price, abs(pos) + Lot, buy=False)
                API.Order.Order_newBulk(orders=json.dumps(orders)).result()
                print('平均足は陰線、ヘーキンの教えを信じるのです')
                print('ポジションを取り直します')
            if INYOU == IN and pos < 0:  # 日足がINN線かつ-pos
                print('平均足は陰線、ヘーキンの教えを信じるのです')
                print('ポジションを継続します')

            D1_stopper = 1
            pre_INYOU = INYOU

        elif now % 86400 > 300:
            D1_stopper = 0

        time.sleep(10)

        if TrailPeg != 0:
            TrailOrder = API.Order.Order_getOrders(symbol='XBTUSD', filter=json.dumps({'open': True, 'text': 'Trail'})).result()[0]
            q = API.OrderBook.OrderBook_getL2(symbol='XBTUSD', depth=1).result()[0]
            ask_price, bid_price = q[0]['price'], q[1]['price']
            p = API.Position.Position_get(filter=json.dumps({'symbol': 'XBTUSD'})).result()[0][0]
            pos = p['currentQty']

            if TrailStart != 0 and len(TrailOrder) == 0 and pos != 0:
                if (pos > 0 and TrailStart - ask_price <= -TrailLine) or (pos < 0 and TrailStart - bid_price >= TrailLine):
                    API.Order.Order_new(symbol='XBTUSD', pegPriceType='TrailingStopPeg', pegOffsetValue=-TrailSign * TrailPeg, orderQty=-pos, text='Trail', execInst='LastPrice,ReduceOnly').result()

        now = int(time.time())  # 正しい時間を取得しなおす

    except Exception as e:
        print(e)
        time.sleep(1 - ((time.time() - starttime) % 1))