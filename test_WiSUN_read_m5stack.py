from m5stack import *
import machine
import gc
import utime
import ure
import uos
import _thread
import espnow
import ntptime


# 変数初期値定義
lcd_mute                = False         # グローバル
data_mute               = False         # グローバル
now_power               = 0             # グローバル
now_power_time          = utime.time()


# 時計表示スレッド関数
def time_count():
    while True:
        lcd.rect(0 , 0, 320, 31, lcd.BLACK, lcd.BLACK)
        lcd.font(lcd.FONT_DejaVu24)
        lcd.print('{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(*utime.localtime()[:6]), lcd.CENTER, 6, lcd.WHITE)
        utime.sleep(0.5)


# 表示OFFボタン処理スレッド関数
def buttonA_wasPressed():
    global lcd_mute

    if lcd_mute :
        lcd_mute = False
    else :
        lcd_mute = True

    if lcd_mute == True :
        lcd.setBrightness(0)   #バックライト輝度調整（OFF）
    else :
        lcd.setBrightness(128) #バックライト輝度調整（中くらい）


# 表示モード切替時の枠描画処理関数
def draw_lcd():
    lcd.clear()
    lcd.line(0, 32, 320, 32, lcd.LIGHTGREY)   
    draw_w()


# 瞬間電力値表示処理関数
def draw_w():
    global AMPERE_LIMIT
    global AMPERE_RED
    global lcd_mute
    global data_mute
    global now_power

    if data_mute or (now_power == 0) : # 瞬間電力値の更新時刻が30秒以上前なら電力値非表示（黒文字化）
        fc = lcd.BLACK
    else :
        if now_power >= (AMPERE_LIMIT * AMPERE_RED * 100) :  # 警告閾値超え時は文字が赤くなる
            fc = lcd.RED
            if lcd_mute == True :   # 閾値超え時はLCD ON
                lcd.setBrightness(128)  # バックライト輝度調整（中くらい）
        else :
            fc = lcd.WHITE
            if lcd_mute == True :
                lcd.setBrightness(0)    # バックライト輝度調整（OFF）
    lcd.rect(0 , 33, 320, 240, lcd.BLACK, lcd.BLACK)
    lcd.font(lcd.FONT_7seg, dist=32, width=5) # 瞬時電力値の表示
    lcd.print(str(now_power) + ' ', lcd.RIGHT, 80, fc)
    lcd.font(lcd.FONT_DejaVu24) # 単位(W)の表示
    lcd.print('W', 280, 155, fc)


# wisun_set_r.txtの存在/中身チェック関数
def wisun_set_filechk():
    global AMPERE_LIMIT
    global AMPERE_RED
    global TIMEOUT

    scanfile_flg = False
    for file_name in uos.listdir('/flash') :
        if file_name == 'wisun_set_r.txt' :
            scanfile_flg = True
    if scanfile_flg :
        print('>> found [wisun_set_r.txt] !')
        with open('/flash/wisun_set_r.txt' , 'r') as f :
            for file_line in f :
                filetxt = file_line.strip().split(':')
                if filetxt[0] == 'AMPERE_RED' :
                    AMPERE_RED = float(filetxt[1])
                    print('- AMPERE_RED: ' + str(AMPERE_RED))
                elif filetxt[0] == 'AMPERE_LIMIT' :
                    AMPERE_LIMIT = int(filetxt[1])
                    print('- AMPERE_LIMIT: ' + str(AMPERE_LIMIT))
                elif filetxt[0] == 'TIMEOUT' :
                    TIMEOUT = int(filetxt[1])
                    print('- TIMEOUT: ' + str(TIMEOUT))
        if AMPERE_RED > 0 and AMPERE_RED <= 1 and AMPERE_LIMIT >= 20 and TIMEOUT > 0 :
            scanfile_flg = True
        else :
            print('>> [wisun_set_r.txt] Illegal!!')
            scanfile_flg = False
    else :
        print('>> no [wisun_set_r.txt] !')

    if scanfile_flg == False : # [wisun_set_r.txt]が読めないまたは異常値の場合はデフォルト値が設定される
        AMPERE_RED = 0.7    # デフォルト値：契約アンペア数の何割を超えたら警告 [0.1～1.0]
        AMPERE_LIMIT = 30   # デフォルト値：アンペア契約値（ブレーカー落ち警報目安で使用）
        TIMEOUT = 30        # デフォルト値：電力値更新のタイムアウト設定値(秒) この秒数以上更新無ければ電力値非表示となる

    return scanfile_flg


# WiFi設定
import wifiCfg
wifiCfg.autoConnect(lcdShow=True)
print('>> WiFi init OK')


# RTC設定
ntp = ntptime.client(host='jp.pool.ntp.org', timezone=9)
print('>> RTC init OK')


# 画面初期化 & 初期設定ファイル読込み
lcd.setBrightness(128) #バックライト輝度調整（中くらい）
wisun_set_filechk()
draw_lcd()
print('>> Disp init OK')


# 時刻表示スレッド起動
_thread.start_new_thread(time_count, ())
print('>> Time Count thread ON')


# ボタン検出スレッド起動
btnA.wasPressed(buttonA_wasPressed)
print('>> Button Check thread ON')


# ESP NOW設定
wifiCfg.wlan_ap.active(True)
#wifiCfg.wlan_sta.active(False)
espnow.init()
print('>> ESP NOW init')


# メインループ
while True:
    update_count = utime.time() - now_power_time
    if update_count >= TIMEOUT : # 瞬間電力値の更新時刻が[TIMEOUT]秒以上前なら電力値非表示（黒文字化）
        data_mute = True
        draw_w()

    d = espnow.recv_data()
    if len(d[2]) > 0 :
        r_txt = str(d[2].strip(), 'utf-8')
        if ure.match('NPD=' , r_txt.strip()) : # 瞬間電力値受信処理
            if not now_power == int(r_txt[4:]) :
                now_power = int(r_txt[4:])
                data_mute = False
                now_power_time = utime.time()
                draw_w()
                print(str(now_power) + ' W')
        elif ure.match('TPD=' , r_txt.strip()) : # 積算電力量受信処理（仮）
            print(r_txt[4:])

    gc.collect()
    utime.sleep(0.1)