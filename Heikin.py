# coding: utf-8
import bitmex
import time
import json
from datetime import datetime
import ccxt
import sys
 #��������ݒ�ӏ��ɂȂ�܂� �B
API = bitmex.bitmex(test=False, api_key='�@', api_secret='�@')
Leverage = 2  # ���̍s�ŕۗL�����ɑ΂��郌�o���b�W��ݒ肵�Ă��������B(����3�{���x�A�ő�80�{)
LossCut = 0  # �G���g���[���i���瑹�؂�܂ł̋����B(�h���P�ʁA0�ŏȗ�)
TrailLine = 0  # �G���g���[���i����g���[�����O�X�g�b�v�����܂ł̋����B(�h���P�ʁA0�ŏȗ�)
TrailPeg = 0  # �g���[�����O�X�g�b�v�̉��i�Ǐ]�����B(�h���P��) #�����܂ł��ݒ�ӏ��ɂȂ�܂� �B

# �ȉ��͂�����Ȃ��ł��������I�I
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

print('����G���g���[�͓����X�V��(9:00)�ł��B')

D1_stopper = 0
pre_INYOU = 0
IN, YOU = -1, 1
starttime = time.time()
now = int(time.time()) - (int(time.time()) % 86400) + 50  # �ŏ�����1��1��^�C�}�[�𑦓˔j������

while True:  ###1�����[�v
    try:
        if 10 <= now % 86400 <= 300 and D1_stopper == 0:  # 1��1��^�C�}�[
            HEIKIN_Open, HEIKIN_Close = get_heiken_oc()

            print('�m�F�p_���ϑ�OPEN�F', HEIKIN_Open)
            print('�m�F�p_���ϑ�CLOSE�F', HEIKIN_Close)
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

            if INYOU == YOU and pos == 0 and pre_INYOU != INYOU:  # �m�[�|�W����N���z��
                API.Order.Order_cancelAll().result()
                orders = orderset(ask_price, Lot, buy=True)
                API.Order.Order_newBulk(orders=json.dumps(orders)).result()
                print('���ϑ��͗z���A�w�[�L���̋�����M����̂ł�')
            if INYOU == IN and pos == 0 and pre_INYOU != INYOU:  # �m�[�|�W����N���A��
                API.Order.Order_cancelAll().result()
                orders = orderset(bid_price, Lot, buy=False)
                API.Order.Order_newBulk(orders=json.dumps(orders)).result()
                print('���ϑ��͉A���A�w�[�L���̋�����M����̂ł�')

            if INYOU == YOU and pos > 0:  # ������YOU������+pos
                print('���ϑ��͗z���A�w�[�L���̋�����M����̂ł�')
                print('�|�W�V�������p�����܂�')
            if INYOU == YOU and pos < 0:  # ������YOU������-pos
                API.Order.Order_cancelAll().result()
                orders = orderset(ask_price, abs(pos) + Lot, buy=True)
                API.Order.Order_newBulk(orders=json.dumps(orders)).result()
                print('���ϑ��͗z���A�w�[�L���̋�����M����̂ł�')
                print('�|�W�V��������蒼���܂�')

            if INYOU == IN and pos > 0:  # ������INN������+pos
                API.Order.Order_cancelAll().result()
                orders = orderset(bid_price, abs(pos) + Lot, buy=False)
                API.Order.Order_newBulk(orders=json.dumps(orders)).result()
                print('���ϑ��͉A���A�w�[�L���̋�����M����̂ł�')
                print('�|�W�V��������蒼���܂�')
            if INYOU == IN and pos < 0:  # ������INN������-pos
                print('���ϑ��͉A���A�w�[�L���̋�����M����̂ł�')
                print('�|�W�V�������p�����܂�')

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

        now = int(time.time())  # ���������Ԃ��擾���Ȃ���

    except Exception as e:
        print(e)
        time.sleep(1 - ((time.time() - starttime) % 1))