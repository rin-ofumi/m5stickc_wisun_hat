from m5stack import *
import machine
import gc
import utime
import uos
import _thread
import espnow
import wifiCfg
import ntptime


#### 変数・関数初期値定義 ####
Disp_angle              = 0             # 画面方向 [0:電源ボタンが上、1:電源ボタンが下]
lcd_mute                = False         # グローバル
data_mute               = False         # グローバル
beep                    = True          # グローバル
now_power               = 0             # グローバル
now_power_time          = utime.time()
m5type                  = 0             # 画面サイズ種別 [0:M5StickC、1: M5StickCPlus/2]
bkl_ON                  = 40            # 画面ON時のバックライト輝度 [0 ～ 100]


# Plus/2でバックライト制御が違うので対応（PlusはAXPでバックライト制御、Plus2はAXP無し）
def bkl_level( a: int ):
    if (a > 100):   # 輝度指定は0～100まで
        a = 100

    if 'axp' in globals():   # M5StickC無印、またはM5StickC Plusの場合
        axp.setLcdBrightness(a)
    else :                   # M5StickC Plus2の場合
        M5pwr.brightness(a)


# BEEP音鳴らしスレッド関数
def beep_sound():
    while True:
        if data_mute or (now_power == 0) : # タイムアウトで表示ミュートされてるか、初期値のままならpass
            pass
        else :
            if (now_power >= (AMPERE_LIMIT * AMPERE_RED * 100)) and (beep == True) :  # 警告閾値超えでBEEP ONなら
                speaker.tone(220, 200)
                utime.sleep(2)
        utime.sleep(0.1)


# 表示OFFボタン処理スレッド関数
def buttonA_wasPressed():
    global lcd_mute

    if lcd_mute :
        lcd_mute = False
    else :
        lcd_mute = True

    if lcd_mute == True :
        bkl_level(0)        # バックライト輝度調整（OFF）
    else :
        bkl_level(bkl_ON)    # バックライト輝度調整（ON）


# BEEP音ボタン処理スレッド関数
def buttonA_wasDoublePress():
    global beep

    if beep :
        beep = False
    else :
        beep = True

    draw_lcd()


# 表示切替ボタン処理スレッド関数
def buttonB_wasPressed():
    global Disp_angle

    if Disp_angle == 1 :
        Disp_angle = 0
    else :
        Disp_angle = 1
    
    draw_lcd()


# 表示モード切替時の描画処理関数
def draw_lcd():
    lcd.clear()

    if m5type == 1 : # M5StickCPlusのみ
        draw_status()

    draw_w()


# 瞬間電力値表示処理関数
def draw_w():
    if data_mute or (now_power == 0) : # タイムアウトで表示ミュートされてるか、初期値のままなら電力値非表示（黒文字化）
        fc = lcd.BLACK
    else :
        if now_power >= (AMPERE_LIMIT * AMPERE_RED * 100) :  # 警告閾値超え時は文字が赤くなる
            fc = lcd.RED
            if lcd_mute == True :   # 閾値超え時はLCD ON
                bkl_level(bkl_ON)    # バックライト輝度調整（ON）
        else :
            fc = lcd.WHITE
            if lcd_mute == True :
                bkl_level(0)        # バックライト輝度調整（OFF）

    # M5StickC(無印)向け
    if m5type == 0 :
        if Disp_angle == 0 : # [0:電源ボタンが上]
            lcd.font(lcd.FONT_DejaVu18, rotate = 270) # 単位(W)の表示
            lcd.print('W', 60, 30, fc)
            lcd.font(lcd.FONT_DejaVu40, rotate = 270) # 瞬間電力値の表示
            lcd.print(str(now_power), 25, 24 + (len(str(now_power))* 24), fc)
        if Disp_angle == 1 : # [1:電源ボタンが下]
            lcd.font(lcd.FONT_DejaVu18, rotate = 90) # 単位(W)の表示
            lcd.print('W', 20, 125, fc)
            lcd.font(lcd.FONT_DejaVu40, rotate = 90) # 瞬間電力値の表示
            lcd.print(str(now_power), 56, 128 - (len(str(now_power))* 24), fc)

    # M5StickCPlus向け
    if m5type == 1 :
        # 文字列の表示揃え用の位置オフセット
        if len(str(now_power)) > 3 :
            str_offset = 0
        else :
            str_offset = 32
        
        if Disp_angle == 0 : # [0:電源ボタンが上]
            lcd.font(lcd.FONT_DejaVu24, rotate = 270) # 単位(W)の表示
            lcd.print('W', 72, 30, fc)
            lcd.font(lcd.FONT_DejaVu56, rotate = 270) # 瞬間電力値の表示
            lcd.print(str(now_power), 45, 185 - str_offset, fc)
        if Disp_angle == 1 : # [1:電源ボタンが下]
            lcd.font(lcd.FONT_DejaVu24, rotate = 90) # 単位(W)の表示
            lcd.print('W', 63, 210, fc)
            lcd.font(lcd.FONT_DejaVu56, rotate = 90) # 瞬間電力値の表示
            lcd.print(str(now_power), 92, 55 + str_offset, fc)


# ステータスマーカー表示処理関数（M5StickCPlusのみ）
def draw_status():
    if beep == True : 
        if Disp_angle == 0 :    # [0:電源ボタンが上、1:電源ボタンが下]
            lcd.roundrect(1, 1, 20, 50, 10, 0x66e6ff, 0x2acf00)
            lcd.font(lcd.FONT_Default, rotate = 270)
            lcd.text(6, 40, "BEEP", 0x000000)
        if Disp_angle == 1 :
            lcd.roundrect(114, 189, 20, 50, 10, 0x66e6ff, 0x2acf00)
            lcd.font(lcd.FONT_Default, rotate = 90)
            lcd.text(128, 198, "BEEP", 0x000000)


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
        if AMPERE_RED > 0 and AMPERE_RED <= 1 and AMPERE_LIMIT >= 10 and TIMEOUT > 0 :
            scanfile_flg = True
        else :
            print('>> [wisun_set_r.txt] Illegal!!')
            scanfile_flg = False
    else :
        print('>> no [wisun_set_r.txt] !')

    if scanfile_flg == False : # [wisun_set_r.txt]が読めないまたは異常値の場合はデフォルト値が設定される
        print('>> Illegal [wisun_set_r.txt] !')
        AMPERE_RED = 0.7    # デフォルト値：契約アンペア数の何割を超えたら警告 [0.1～1.0]
        AMPERE_LIMIT = 30   # デフォルト値：アンペア契約値（ブレーカー落ち警報目安で使用）
        TIMEOUT = 30        # デフォルト値：電力値更新のタイムアウト設定値(秒) この秒数以上更新無ければ電力値非表示となる

    return scanfile_flg


#### 以降、プログラム本文 ####

# WiFi設定
wifiCfg.autoConnect(lcdShow=True)
print('>> WiFi init OK')


# RTC設定
ntp = ntptime.client(host='jp.pool.ntp.org', timezone=9)
print('>> RTC init OK')


# 画面初期化 & 初期設定ファイル読込み
bkl_level(bkl_ON)   # バックライト輝度調整（ON）
wisun_set_filechk()

if lcd.winsize() == (80,160) :  # M5StickC/Plus機種判定
    m5type = 0
    print('>> M5Type = M5StickC')
if lcd.winsize() == (136,241) :
    m5type = 1
    print('>> M5Type = M5StickCPlus/2')

draw_lcd()
print('>> Disp init OK')


# BEEP音鳴らしスレッド起動
if m5type == 1 : # M5StickCPlusのみ
    _thread.start_new_thread(beep_sound, ())
    print('>> BEEP Sound thread ON')


# ボタン検出スレッド起動
btnA.wasPressed(buttonA_wasPressed)
btnB.wasPressed(buttonB_wasPressed)
btnA.wasDoublePress(buttonA_wasDoublePress)
print('>> Button Check thread ON')


# ESP NOW設定
wifiCfg.wlan_ap.active(True)
espnow.init(0)  # UIFlow Ver1.10.2以降への対応
print('>> ESP NOW init')


# メインループ
while True:
    update_count = utime.time() - now_power_time
    if update_count >= TIMEOUT : # 瞬間電力値の更新時刻が[TIMEOUT]秒以上前なら電力値非表示（黒文字化）
        data_mute = True
        draw_lcd()

    d = espnow.recv_data()
    if len(d[2]) > 0 :
        r_txt = str(d[2].strip(), 'utf-8')
        if r_txt.strip().startswith('NPD=') :   # 瞬間電力値受信処理
            if not now_power == int(r_txt[4:]) :
                now_power = int(r_txt[4:])
                data_mute = False
                now_power_time = utime.time()
                draw_lcd()
                print(str(now_power) + ' W')

    gc.collect()
    utime.sleep(0.1)