# Wi-SUN HAT（BP35A1用）のサンプルプログラム
# ver 0.0.1a (2024/5/5 Update)
# @rin-ofumi
#
# 確認した機種 (検証時のUIFlow Ver)
# - M5StickC (v1.13.4)
# - M5StickC Plus (v1.13.4
# - M5StickC Plus2 (v1.13.4)
from m5stack import *
import machine
import gc
import utime
import ure
import uos
import _thread
import wifiCfg
import ntptime
import wisun_udp


#### 変数・関数初期値定義 ####

# 固定値
GET_COEFFICIENT         = b'\x10\x81\x00\x01\x05\xFF\x01\x02\x88\x01\x62\x01\xD3\x00'           #D3     *積算電力量係数の要求
GET_TOTAL_POWER_UNIT    = b'\x10\x81\x00\x01\x05\xFF\x01\x02\x88\x01\x62\x01\xE1\x00'           #E1     *積算電力量単位の要求
GET_NOW_PA              = b'\x10\x81\x00\x01\x05\xFF\x01\x02\x88\x01\x62\x02\xE7\x00\xE8\x00'   #E7&E8  *瞬時電力計測値＆瞬時電流計測値（T/R相）の要求
GET_NOW_P               = b'\x10\x81\x00\x01\x05\xFF\x01\x02\x88\x01\x62\x01\xE7\x00'           #E7     *瞬時電力計測値の要求
GET_TOTAL_POWER_30      = b'\x10\x81\x00\x01\x05\xFF\x01\x02\x88\x01\x62\x01\xEA\x00'           #EA     *30分毎更新の積算電力量の要求

# 変数宣言
SCAN_COUNT              = 6     # ActiveScan試行回数
channel                 = ''
panid                   = ''
macadr                  = ''
lqi                     = ''

Am_st_1                 = 0     # Ambient設定 1 のステータス   [0:無し(WiFiも未使用になる)、1:設定有＆初回通信待ち、2:設定有＆通信OK、3:設定有＆通信NG]
Am_st_2                 = 0     # Ambient設定 2 のステータス   [0:無し(WiFiも未使用になる)、1:設定有＆初回通信待ち、2:設定有＆通信OK、3:設定有＆通信NG]
Disp_angle              = 0     # グローバル 画面方向 [0:電源ボタンが上、1:電源ボタンが下]
lcd_mute                = False # グローバル
data_mute               = False # グローバル
beep                    = True  # グローバル
m5type                  = 0     # 画面サイズ種別 [0:M5StickC、1: M5StickCPlus/2]
bkl_ON                  = 40    # 画面ON時のバックライト輝度 [0 ～ 100]
np_interval             = 5     # 瞬間電力値の要求サイクル（秒）※最短でも5秒以上が望ましい
am_interval             = 30    # Ambientへデータを送るサイクル（秒））※Ambientは3000件/日までなので、丸1日分持たせるには30秒以上にする

AM_ID_1                 = None  # Ambient設定 1 のID（別途の設定ファイルで指定するのでこれはダミー）
AM_WKEY_1               = None  # Ambient設定 1 のライトキー（別途の設定ファイルで指定するのでこれはダミー）
AM_ID_2                 = None  # Ambient設定 2 のID（別途の設定ファイルで指定するのでこれはダミー）
AM_WKEY_2               = None  # Ambient設定 2 のライトキー（別途の設定ファイルで指定するのでこれはダミー）
ESP_NOW_F               = False # ESP_NOWを使うかの設定値のデフォルト値
RES_TOUT                = 10    # スマートメーターからのコマンド応答待ちタイムアウト（秒）のデフォルト値
TIMEOUT                 = 30    # 何らかの事情で更新が止まった時のタイムアウト（秒）のデフォルト値
AMPERE_RED              = 0.7   # 契約ブレーカー値に対し、どれくらいの使用率で赤文字化させるかのデフォルト値 （力率は無視してます）
AMPERE_LIMIT            = 30    # 契約ブレーカー値のデフォルト値


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
        if data_mute or (u.instant_power[0] == 0) : # タイムアウトで表示ミュートされてるか、初期値のままならpass
            pass
        else :
            if (u.instant_power[0] >= (AMPERE_LIMIT * AMPERE_RED * 100)) and (beep == True) :  # 警告閾値超えでBEEP ONなら
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


# 画面向き切替ボタン処理スレッド関数
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

    if m5type == 1 : # M5StickCPlus/2のみ
        draw_beep_status()

    draw_am_status()
    draw_w()


# 瞬間電力値表示処理関数
def draw_w():
    global Disp_angle , m5type
    global lcd_mute
    global data_mute
    global AMPERE_LIMIT
    global AMPERE_RED

    if data_mute or (u.instant_power[0] == 0) : # タイムアウトで表示ミュートされてるか、初期値のままなら電力値非表示（黒文字化）
        fc = lcd.BLACK
    else :
        if u.instant_power[0] >= (AMPERE_LIMIT * AMPERE_RED * 100) :  # 警告閾値超え時は文字が赤くなる
            fc = lcd.RED
            if lcd_mute == True :   # 閾値超え時はLCD ON
                bkl_level(bkl_ON)   # バックライト輝度調整（ON）
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
            lcd.print(str(u.instant_power[0]), 25, 24 + (len(str(u.instant_power[0]))* 24), fc)
        if Disp_angle == 1 : # [1:電源ボタンが下]
            lcd.font(lcd.FONT_DejaVu18, rotate = 90) # 単位(W)の表示
            lcd.print('W', 20, 125, fc)
            lcd.font(lcd.FONT_DejaVu40, rotate = 90) # 瞬間電力値の表示
            lcd.print(str(u.instant_power[0]), 56, 128 - (len(str(u.instant_power[0]))* 24), fc)

    # M5StickCPlus/2向け
    if m5type == 1 :
        # 文字列の表示揃え用の位置オフセット
        if len(str(u.instant_power[0])) > 3 :
            str_offset = 0
        else :
            str_offset = 32
        
        if Disp_angle == 0 : # [0:電源ボタンが上]
            lcd.font(lcd.FONT_DejaVu24, rotate = 270) # 単位(W)の表示
            lcd.print('W', 72, 30, fc)
            lcd.font(lcd.FONT_DejaVu56, rotate = 270) # 瞬間電力値の表示
            lcd.print(str(u.instant_power[0]), 45, 185 - str_offset, fc)
        if Disp_angle == 1 : # [1:電源ボタンが下]
            lcd.font(lcd.FONT_DejaVu24, rotate = 90) # 単位(W)の表示
            lcd.print('W', 63, 210, fc)
            lcd.font(lcd.FONT_DejaVu56, rotate = 90) # 瞬間電力値の表示
            lcd.print(str(u.instant_power[0]), 92, 55 + str_offset, fc)


# BEEPステータスマーカー表示処理関数（M5StickCPlus/2のみ）
def draw_beep_status():
    if beep == True : 
        if Disp_angle == 0 :    # [0:電源ボタンが上、1:電源ボタンが下]
            lcd.roundrect(1, 1, 20, 50, 10, 0x66e6ff, 0x2acf00)
            lcd.font(lcd.FONT_Default, rotate = 270)
            lcd.text(6, 40, "BEEP", 0x000000)
        if Disp_angle == 1 :
            lcd.roundrect(114, 189, 20, 50, 10, 0x66e6ff, 0x2acf00)
            lcd.font(lcd.FONT_Default, rotate = 90)
            lcd.text(128, 198, "BEEP", 0x000000)


# Ambient通信ステータスマーカー表示処理関数
def draw_am_status():
    # Ambientステータス [0:設定無し、1:設定有＆初回通信待ち、2:設定有＆通信OK、3:設定有＆通信NG]

    # Ambient設定 1 (瞬間電力値)のステータス表示関係
    if Am_st_1 > 0 :  # Ambient設定有ならAmbient通信ステータスマーカー描画
        if Am_st_1 == 1 :     # Ambient設定有＆初回通信待ち ⇒ 白枠、中黒
            c_o = lcd.WHITE
            c_f = lcd.BLACK
        elif Am_st_1 == 2 :   # Ambient設定有＆通信OK ⇒ 白枠、中緑
            c_o = lcd.WHITE
            c_f = lcd.GREEN
        elif Am_st_1 == 3 :   # Ambient設定有＆通信NG ⇒ 白枠、中赤
            c_o = lcd.WHITE
            c_f = lcd.RED

        c_offset = 3    # Ambient通信ステータスマーカーの画面端からのオフセット量

        # M5StickC(無印)向け
        if m5type == 0 :
            c_r = 7
            if Disp_angle == 0 :    # [0:電源ボタンが上、1:電源ボタンが下]
                c_x = 0 + c_r + c_offset
                c_y = 159 - c_r - c_offset
            if Disp_angle == 1 :
                c_x = 79 - c_r - c_offset
                c_y = 0 + c_r + c_offset
        # M5StickCPlus向け
        if m5type == 1 :
            c_r = 10
            if Disp_angle == 0 :    # [0:電源ボタンが上、1:電源ボタンが下]
                c_x = 0 + c_r + c_offset
                c_y = 239 - c_r - c_offset
            if Disp_angle == 1 :
                c_x = 134 - c_r - c_offset
                c_y = 0 + c_r + c_offset

        # Ambient設定 1 のステータス描画
        lcd.circle(c_x, c_y, c_r, c_o, c_f)

    # Ambient設定 2 (30分毎積算電力値)のステータス表示関係
    if Am_st_2 > 0 :  # Ambient設定有ならAmbient通信ステータスマーカー描画
        if Am_st_2 == 1 :     # Ambient設定有＆初回通信待ち ⇒ 白枠、中黒
            c_o = lcd.WHITE
            c_f = lcd.BLACK
        elif Am_st_2 == 2 :   # Ambient設定有＆通信OK ⇒ 白枠、中緑
            c_o = lcd.WHITE
            c_f = lcd.GREEN
        elif Am_st_2 == 3 :   # Ambient設定有＆通信NG ⇒ 白枠、中赤
            c_o = lcd.WHITE
            c_f = lcd.RED

        c_offset = 3    # Ambient通信ステータスマーカーの画面端からのオフセット量

        # M5StickC(無印)向け
        if m5type == 0 :
            c_r = 7
            if Disp_angle == 0 :    # [0:電源ボタンが上、1:電源ボタンが下]
                c_x = 0 + c_r + c_offset
                c_y = 159 - c_r - c_offset - c_r * 2 - 3
            if Disp_angle == 1 :
                c_x = 79 - c_r - c_offset
                c_y = 0 + c_r + c_offset + c_r * 2 + 3
        # M5StickCPlus向け
        if m5type == 1 :
            c_r = 10
            if Disp_angle == 0 :    # [0:電源ボタンが上、1:電源ボタンが下]
                c_x = 0 + c_r + c_offset
                c_y = 239 - c_r - c_offset - c_r * 2 - 3
            if Disp_angle == 1 :
                c_x = 134 - c_r - c_offset
                c_y = 0 + c_r + c_offset + c_r * 2 + 3

        # Ambient設定 2 のステータス描画
        lcd.circle(c_x, c_y, c_r, c_o, c_f)


# wisun_set_m.txtの存在/中身チェック関数
def wisun_set_filechk():
    global AMPERE_LIMIT
    global AMPERE_RED
    global TIMEOUT
    global BRID
    global BRPSWD
    global AM_ID_1
    global AM_WKEY_1
    global AM_ID_2
    global AM_WKEY_2
    global ESP_NOW_F

    scanfile_flg = False
    for file_name in uos.listdir('/flash') :
        if file_name == 'wisun_set_m.txt' :
            scanfile_flg = True

    if scanfile_flg :
        print('>> found [wisun_set_m.txt] !')
        with open('/flash/wisun_set_m.txt' , 'r') as f :
            for file_line in f :
                filetxt = file_line.strip().split(':')
                if filetxt[0] == 'AMPERE_RED' :
                    if float(filetxt[1]) >= 0 and float(filetxt[1]) <= 1 :
                        AMPERE_RED = float(filetxt[1])
                        print('- AMPERE_RED: ' + str(AMPERE_RED))
                elif filetxt[0] == 'AMPERE_LIMIT' :
                    if int(filetxt[1]) >= 20 :
                        AMPERE_LIMIT = int(filetxt[1])
                        print('- AMPERE_LIMIT: ' + str(AMPERE_LIMIT))
                elif filetxt[0] == 'TIMEOUT' :
                    if int(filetxt[1]) > 0 :
                        TIMEOUT = int(filetxt[1])
                        print('- TIMEOUT: ' + str(TIMEOUT))
                elif filetxt[0] == 'BRID' :
                    BRID = str(filetxt[1])
                    print('- BRID: ' + str(BRID))
                elif filetxt[0] == 'BRPSWD' :
                    BRPSWD = str(filetxt[1])
                    print('- BRPSWD: ' + str(BRPSWD))
                elif filetxt[0] == 'AM_ID_1' :
                    AM_ID_1 = str(filetxt[1])
                    print('- AM_ID_1: ' + str(AM_ID_1))
                elif filetxt[0] == 'AM_WKEY_1' :
                    if len(filetxt[1]) == 16 :
                        AM_WKEY_1 = str(filetxt[1])
                        print('- AM_WKEY_1: ' + str(AM_WKEY_1))
                elif filetxt[0] == 'AM_ID_2' :
                    AM_ID_2 = str(filetxt[1])
                    print('- AM_ID_2: ' + str(AM_ID_2))
                elif filetxt[0] == 'AM_WKEY_2' :
                    if len(filetxt[1]) == 16 :
                        AM_WKEY_2 = str(filetxt[1])
                        print('- AM_WKEY_2: ' + str(AM_WKEY_2))
                elif filetxt[0] == 'ESP_NOW' :
                    if int(filetxt[1]) == 0 or int(filetxt[1]) == 1 :
                        ESP_NOW_F = int(filetxt[1])
                        print('- ESP_NOW: ' + str(ESP_NOW_F))
                        
        if len(BRID) == 32 and len(BRPSWD) == 12: # BルートIDとパスワードの桁数チェック（NGならプログラム停止）
            scanfile_flg = True
        else :
            print('>> [wisun_set_m.txt] Illegal!!')
            scanfile_flg = False
            
    else :
        print('>> no [wisun_set_m.txt] !')
    return scanfile_flg


# Wi-SUN_SCAN.txtの存在/中身チェック関数
def wisun_scan_filechk():
    global channel
    global panid
    global macadr
    global lqi

    scanfile_flg = False
    for file_name in uos.listdir('/flash') :
        if file_name == 'Wi-SUN_SCAN.txt' :
            scanfile_flg = True
    if scanfile_flg :
        print('>> found [Wi-SUN_SCAN.txt] !')
        with open('/flash/Wi-SUN_SCAN.txt' , 'r') as f :
            for file_line in f :
                filetxt = file_line.strip().split(':')
                if filetxt[0] == 'Channel' :
                    channel = filetxt[1]
                    print('- Channel: ' + channel)
                elif filetxt[0] == 'Pan_ID' :
                    panid = filetxt[1]
                    print('- Pan_ID: ' + panid)
                elif filetxt[0] == 'MAC_Addr' :
                    macadr = filetxt[1]
                    print('- MAC_Addr: ' + macadr)
                elif filetxt[0] == 'LQI' :
                    lqi = filetxt[1]
                    print('- LQI: ' + lqi)
                elif filetxt[0] == 'COEFFICIENT' :
                    u.power_coefficient = int(filetxt[1])
                    print('- COEFFICIENT: ' + str(u.power_coefficient))
                elif filetxt[0] == 'UNIT' :
                    u.power_unit = float(filetxt[1])
                    print('- UNIT: ' + str(u.power_unit))
        if len(channel) == 2 and len(panid) == 4 and len(macadr) == 16:
            scanfile_flg = True
        else :
            print('>> [Wi-SUN_SCAN.txt] Illegal!!')
            scanfile_flg = False
    else :
        print('>> no [Wi-SUN_SCAN.txt] !')
    return scanfile_flg


#### メインプログラムはここから（この上はプログラム内関数）####

print('heapmemory= ' + str(gc.mem_free()))


# 基本設定ファイル[wisun_set_m.txt]のチェック 無い場合は例外エラー吐いて終了する
if not wisun_set_filechk() :
    lcd.print('err!! Check [wisun_set_m.txt] and restart!!', 0, 0, lcd.WHITE)
    raise ValueError('err!! Check [wisun_set_m.txt] and restart!!')


# M5StickC/Plus機種判定
if lcd.winsize() == (80,160) :
    m5type = 0
    print('>> M5Type = M5StickC')
if lcd.winsize() == (136,241) :
    m5type = 1
    print('>> M5Type = M5StickCPlus/2')


# WiFi設定
wifiCfg.autoConnect(lcdShow=True)
lcd.clear()
lcd.print('*', 0, 0, lcd.WHITE)
print('>> WiFi init OK')


# UDPデータインスタンス生成
u = wisun_udp.udp_read()
print('>> UDP reader init OK')


# Ambientインスタンス生成
Am_st_1 = 0
if (AM_ID_1 is not None) and (AM_WKEY_1 is not None) : # Ambient_1の設定情報があった場合
    import ambient
    am_now_power = ambient.Ambient(AM_ID_1, AM_WKEY_1)
    print('>> Ambient_1 init OK')
    Am_st_1 = 1

Am_st_2 = 0
if (AM_ID_2 is not None) and (AM_WKEY_2 is not None) : # Ambient_2の設定情報があった場合
    import ambient
    am_total_power = ambient.Ambient(AM_ID_2, AM_WKEY_2)
    print('>> Ambient_2 init OK')
    Am_st_2 = 1

lcd.print('**', 0, 0, lcd.WHITE)


# BP35A1 UART設定
#uart = machine.UART(1, tx=0, rx=36) # Wi-SUN HAT rev0.1用
uart = machine.UART(1, tx=0, rx=26) # Wi-SUN HAT rev0.2用
#uart.init(115200, bits=8, parity=None, stop=1, timeout=2000)
uart.init(115200, bits=8, parity=None, stop=1, timeout=100, timeout_char=100)
lcd.print('***', 0, 0, lcd.WHITE)
print('>> UART init OK')

# UARTの送受信バッファーの塵データをクリア
utime.sleep(0.5)
if uart.any() != 0 :
    dust = uart.read()
uart.write('\r\n')
utime.sleep(1)
if uart.any() != 0 :
    dust = uart.read()
uart.write('\r\n')
utime.sleep(0.5)
print('>> UART RX/TX Data Clear!')


# BP35A1の初期設定 - コマンドエコーバックをオンにする
uart.write('SKSREG SFE 1\r\n')
utime.sleep(0.5)
while True :    #Echo back & OK wait!
    line = None
    if uart.any() != 0 :
        line = uart.readline()
        print('*')
    if line is not None :
        if ure.match('OK' , line.strip()) :
            break
print('>> BA35A1 Echo back ON set OK')
utime.sleep(0.5)


# BP35A1の初期設定 - ユーザーIDとパスワードの入手（必須では無い）
uart.write('SKINFO\r\n')
utime.sleep(0.5)
while True :    #Echo back & OK wait!
    line = None
    if uart.any() != 0 :
        line = uart.readline()
        print(line)
    if line is not None :
        if ure.match('OK' , line.strip()) :
            break
print('>> BA35A1 Info OK')
utime.sleep(0.5)


# BP35A1の初期設定 - ERXUDPデータ部表示形式をASCIIへ変更（デフォはバイナリ）
uart.write('ROPT\r\n')
utime.sleep(0.5)
mode_flg = False
while True :    #Echo back & OK wait!
    line = uart.readline()
#    print(line)
    if ure.match("OK" , line) :
        print(' - BP35A1 ASCII mode')
        break

if ure.match("OK 00" , line) :
    print(' - BP35A1 Binary Mode')
    mode_flg = True
utime.sleep(0.5)

if mode_flg :
    uart.write('WOPT 01\r\n')
    print('>> BP35A1 ASCII mode set')
    utime.sleep(0.5)
    while True :    #Echo back & OK wait!
        line = uart.readline()
#        print(line)
        if ure.match("OK" , line) :
            print('>> BP35A1 ASCII mode set OK')
            break
lcd.print('****', 0, 0, lcd.WHITE)


# 以前のPANAセッションを解除
# 前セッションが残ってると接続出来ない？場合の対策 前セッション無しでも、ER10が返ってくるだけ
uart.write('SKTERM\r\n')
utime.sleep(0.5)
while True :    #Echo back & OK wait!
    line = uart.readline()
#    print(line)
    if ure.match("OK" , line) :
        print(' -Old Session Clear!')
        break
    elif ure.match("FAIL ER10" , line) :
        print(' -Non Old Session')
        break
lcd.print('*****', 0, 0, lcd.WHITE)


# B-root PASSWORDを送信
uart.write("SKSETPWD C " + BRPSWD + "\r\n")
utime.sleep(0.5)
while True :    #Echo back & OK wait!
    line = None
    if uart.any() != 0 :
        line = uart.readline()
        print('*')
    if line is not None :
        if ure.match('OK' , line.strip()) :
            print('>> BA35A1 B-root PASSWORD set OK')
            break
lcd.print('***** *', 0, 0, lcd.WHITE)
utime.sleep(0.5)


# B-root IDを送信
uart.write("SKSETRBID " + BRID + "\r\n")
utime.sleep(0.5)
while True :    #Echo back & OK wait!
    line = None
    if uart.any() != 0 :
        line = uart.readline()
        print('*')
    if line is not None :
        if ure.match('OK' , line.strip()) :
            print('>> BA35A1 B-root ID set OK')
            break
lcd.print('***** **', 0, 0, lcd.WHITE)
utime.sleep(1)
gc.collect()


# Wi-SUNチャンネルスキャン（「Wi-SUN_SCAN.txt」の存在しない or 中身が異常値だった場合）
if not wisun_scan_filechk() :
    #<Channel Scan>
    scanOK = False
    s_c = 1
    while not scanOK :
        uart.write('SKSCAN 2 FFFFFFFF 6\r\n')
        # ROHMのBP35A1コマンドリファレンスより
        # MODE         : 2（Paring IDあり）
        # CHANNEL_MASK : FFFFFFFF（全チャンネルのスキャン）
        # DURATION     : 6（0.624sec） [各チャンネルのスキャン時間 有効範囲:0-14 計算式:0.0096*(2^DURATION+1)sec]
        utime.sleep(0.1)
        while True :    #Echo back & OK wait!
            line = None
            if uart.any() != 0 :
                line = uart.readline()
            if line is not None :
                if ure.match('OK' , line.strip()) : # アクティブスキャンコマンドを受付た
                    print('>> Activescan count:' + str(s_c) + ' start!')
                    break
        
        #スキャン要求1回分の受信ループ処理
        scan_res_end = False
        while not scan_res_end :
            line = None
            if uart.any() != 0 :
                line = uart.readline()
                if line is not None :
                    if ure.match("EVENT 22" , line.strip()) : # スキャン1周分が完了（見付かったかは別）
                        print('>> Activescan count:' + str(s_c) + ' done!')
                        scan_res_end = True                   # スキャンが1周完了してるのでループ抜け
                    elif ure.match("Channel:" , line.strip()) :
                        pickuptext = ure.compile(':') 
                        pickt = pickuptext.split(line.strip())
                        channel = str(pickt[1].strip(), 'utf-8')
                        print(" Channel= " + str(channel))
                    elif ure.match("Pan ID:" , line.strip()) :
                        pickuptext = ure.compile(':') 
                        pickt = pickuptext.split(line.strip())
                        panid = str(pickt[1].strip(), 'utf-8')
                        print(" Pan_ID= " + str(panid))
                    elif ure.match("Addr:" , line.strip()) :
                        pickuptext = ure.compile(':') 
                        pickt = pickuptext.split(line.strip())
                        macadr = str(pickt[1].strip(), 'utf-8')
                        print(" MAC_Addr= " + str(macadr))
                    elif ure.match("LQI:" , line.strip()) :
                        pickuptext = ure.compile(':') 
                        pickt = pickuptext.split(line.strip())
                        lqi = str(pickt[1].strip(), 'utf-8')
                        print(" LQI= " + str(lqi))
                    print(line.strip())
            utime.sleep(0.1)
            gc.collect()
        
        s_c+=1
        
        if s_c > SCAN_COUNT : # アクティブスキャンの試行回数制限を超えた場合は、何らかの事情でスマートメーターが見付からないので環境を見直すべし！
            raise ValueError('Scan retry count over! Please Reboot!')
        
        # スキャン結果の全ての情報が揃ってるかチェック
        if len(channel) == 2 and len(panid) == 4 and len(macadr) == 16 and len(lqi) == 2 :
            with open('/flash/Wi-SUN_SCAN.txt' , 'w') as f:
                f.write('Channel:' + str(channel) + '\r\n')
                f.write('Pan_ID:' + str(panid) + '\r\n')
                f.write('MAC_Addr:' + str(macadr) + '\r\n')
                f.write('LQI:' + str(lqi) + '\r\n')
                print('>> [Wi-SUN_SCAN.txt] maked!!')
            print('Scan All Clear!')
            scanOK = True
lcd.print('***** ***', 0, 0, lcd.WHITE)


# PANA接続処理
while True :    
    #<Channel set>
    uart.write("SKSREG S2 " + channel + "\r\n")
    utime.sleep(0.5)
    while True :    #Echo back & OK wait!
        line = None
        if uart.any() != 0 :
            line = uart.readline()
            print('*')
        if line is not None :
            if ure.match('OK' , line.strip()) :
                break
    
    #<Pan ID set>
    uart.write("SKSREG S3 " + panid + "\r\n")
    utime.sleep(0.5)
    while True :    #Echo back & OK wait!
        line = None
        if uart.any() != 0 :
            line = uart.readline()
            print('*')
        if line is not None :
            if ure.match('OK' , line.strip()) :
                break    
    
    #<MACアドレスをIPV6アドレスに変換>
    uart.write("SKLL64 " + macadr + "\r\n")
    utime.sleep(0.5)
    while True :    #Echo back & OK wait!
        line = None
        if uart.any() != 0 :
            line = uart.readline()
            print('*')
        if line is not None :
            if len(line.strip()) == 39 :
                ipv6Addr = str(line.strip(), 'utf-8')
                print('IPv6 Addr = ' + str(ipv6Addr))
                break
    
    gc.collect()
    utime.sleep(1)

    #<BP35A1のコマンドエコーバックをオフにする>
    uart.write('SKSREG SFE 0\r\n')
    utime.sleep(0.5)
    while True :    #Echo back & OK wait!
        line = uart.readline()
        print(line)
        if ure.match("OK" , line) :
            print('>> BA35A1 Echo back OFF set OK')
            break
    
    #<PANA接続要求>
    print('PANA authentication start!!')
    uart.write("SKJOIN " + ipv6Addr + "\r\n")
    utime.sleep(0.1)
    bConnected = False
    while not bConnected :
        line = None
        if uart.any() != 0 :
            line = uart.readline()
            print('*')
            if line is not None :
                if ure.match("EVENT 24" , line.strip()) :
                    print(">> PANA authentication NG!  ...scan retry")
                    utime.sleep(1)
                    for file_name in uos.listdir('/flash') :
                        if file_name == 'Wi-SUN_SCAN.txt' :
                            uos.remove('/flash/Wi-SUN_SCAN.txt') #チャンネルが変わった可能性があるので、ファイル削除
                            scanfile_flg = False
                            channel = ''
                            panid = ''
                            macadr = ''
                            u.power_coefficient = 0
                            u.power_unit = 0.0
                            print(">> Erase Wi-SUN_SCAN.txt! & Reboot!!")
                            utime.sleep(1)
                            machine.reset() #ファイル削除の後リブートする
                elif ure.match("EVENT 25" , line.strip()) :
                    print(">> PANA authentication OK!")
                    bConnected = True
                    utime.sleep(1)
                gc.collect()
    if bConnected :
        break
lcd.print('***** ****', 0, 0, lcd.WHITE)
gc.collect()


# ECHONET Lite 積算電力係数(COEFFICIENT)要求コマンド送信
if u.power_coefficient == 0 :
    command = bytes('SKSENDTO 1 {0} 0E1A 1 {1:04X} '.format(ipv6Addr, len(GET_COEFFICIENT)), 'utf-8')
    uart.write(command)
    uart.write(GET_COEFFICIENT)
    print('>> [GET_COEFFICIENT] cmd send ' + str(utime.time()))
    cmd_tc = utime.time()   # 受信タイムアウト用カウンタのリセット
    utime.sleep(0.5)
    
    while u.power_coefficient == 0 : #D3（積算電力量係数）受信待ち
        line = None
        if uart.any() != 0 :
            line = uart.readline()
            u.read(line)
            if u.type == 'D3' : # D3 積算電力量係数(COEFFICIENT)
                print(' - COEFFICIENT: ' + str(u.power_coefficient))
                break
            else:
                print(">> Unknown type " + u.type + ' ' + str(utime.time()))
        if (utime.time() - cmd_tc) >= RES_TOUT : # 受信タイムアウトした場合はコマンド非対応スマートメータと判断し、固定値とする
            print('>> response timeout! set[COEFFICIENT = 1]' + ' ' + str(utime.time()))
            u.power_coefficient = 1
        utime.sleep(0.1)
    
    with open('/flash/Wi-SUN_SCAN.txt' , 'a') as fc:
        fc.write('COEFFICIENT:' + str(u.power_coefficient) + '\r\n')
lcd.print('***** *****', 0, 0, lcd.WHITE)
utime.sleep(0.5)


# ECHONET Lite 積算電力単位(UNIT)要求コマンド送信
if u.power_unit == 0.0 :
    command = bytes('SKSENDTO 1 {0} 0E1A 1 {1:04X} '.format(ipv6Addr, len(GET_TOTAL_POWER_UNIT)), 'utf-8')
    uart.write(command)
    uart.write(GET_TOTAL_POWER_UNIT)
    print('>> [GET_TOTAL_POWER_UNIT] cmd send ' + str(utime.time()))
    cmd_tc = utime.time()   # 受信タイムアウト用カウンタのリセット
    utime.sleep(0.5)
    
    while u.power_unit == 0.0 : #E1（積算電力量単位）受信待ち
        line = None
        if uart.any() != 0 :
            line = uart.readline()
            u.read(line)
            if u.type == 'E1' : #E1 積算電力量単位(UNIT)
                print(' - UNITT: ' + str(u.power_unit))
                break
            else:
                print(">> Unknown type " + u.type + ' ' + str(utime.time()))
        if (utime.time() - cmd_tc) >= RES_TOUT : # 受信タイムアウトした場合はコマンド非対応スマートメータと判断し、固定値とする
            print('>> response timeout! set[UNIT = 0.1] ' + str(utime.time()))
            u.power_unit = 0.1
        utime.sleep(0.1)
    
    with open('/flash/Wi-SUN_SCAN.txt' , 'a') as fu:
        fu.write('UNIT:' + str(u.power_unit) + '\r\n')
gc.collect()
lcd.print('***** ***** *', 0, 0, lcd.WHITE)


# ESP NOW設定
if ESP_NOW_F :
    import espnow
    espnow.init(0)  # UIFlow Ver1.10.2以降への対応
    print('>> ESP NOW init')
lcd.print('***** ***** **', 0, 0, lcd.WHITE)


print('heapmemory= ' + str(gc.mem_free()))


# RTC設定
ntp = ntptime.client(host='jp.pool.ntp.org', timezone=9)
print('>> RTC init OK')


# 画面初期化
bkl_level(bkl_ON) # バックライト輝度調整（ON）
draw_lcd()
print('>> Disp init OK')


# BEEP音鳴らしスレッド起動
if m5type == 1 : # M5StickCPlus/2のみ
    _thread.start_new_thread(beep_sound, ())
    print('>> BEEP Sound thread ON')


# ボタン検出スレッド起動
btnA.wasPressed(buttonA_wasPressed)
btnB.wasPressed(buttonB_wasPressed)
btnA.wasDoublePress(buttonA_wasDoublePress)
print('>> Button Check thread ON')


# タイムカウンタ初期値設定
np_tc = utime.time()
tp_tc = utime.time()
am_tc = utime.time()
cmd_tc = utime.time()  # コマンド受信タイムアウト用カウンタ
tp_f = False    # 積算電力量応答の有無フラグ
cmd_w = False   # コマンド受信待機待ちフラグ（コマンド重送しない為の排他制御）Trueは受信待ち
cmd_rc = 0      # コマンド再送信回数カウンタ


# 一旦、お掃除
gc.collect()
print('heapmemory= ' + str(gc.mem_free()))
print(">> Start mainloop! " + str(utime.time()))


# メインループ
while True:
    # スマートメーターへのコマンド送信処理
    if cmd_w == False : # コマンド重送しない為の排他制御
        if ((utime.time() - tp_tc) >= (30 * 60)) or ((not tp_f) and ((utime.time() - tp_tc) >= 10)) : # 30分毎に積算電力量要求コマンド送信（受信出来ない時のコマンド再送信は10秒開ける）
            command = bytes('SKSENDTO 1 {0} 0E1A 1 {1:04X} '.format(ipv6Addr, len(GET_TOTAL_POWER_30)), 'utf-8')
            uart.write(command)
            uart.write(GET_TOTAL_POWER_30)
            print('>> [GET_TOTAL_POWER_30] cmd send ' + str(utime.time()))
            tp_tc = utime.time()
            tp_f = False	# 積算電力量要求を出したので、受信してない扱いでFalse
            cmd_tc = utime.time()
            cmd_w = True	# コマンド送信したので排他状態にする
            cmd_rc += 1
            utime.sleep(0.5)
        elif (utime.time() - np_tc) >= np_interval : # 瞬時電力計測値要求コマンド送信（コマンド頻度が多くなるので、受信できない時のコマンド再送信処理は無し）
            command = bytes('SKSENDTO 1 {0} 0E1A 1 {1:04X} '.format(ipv6Addr, len(GET_NOW_P)), 'utf-8')
            uart.write(command)
            uart.write(GET_NOW_P)
            print('>> [GET_NOW_P] cmd send ' + str(utime.time()))
            np_tc = utime.time()
            cmd_tc = utime.time()
            cmd_w = True # コマンド送信したので排他状態にする
            cmd_rc += 1
            utime.sleep(0.5)

    # スマートメーターからの受信処理
    if cmd_w == True :
        line = None # UDPデータの受信処理
        if uart.any() != 0 :
            line = uart.readline()
            u.read(line)
        #        print(line) #全ログ取得デバッグ用
            if u.type == 'E7' :    # [E7]なら受信データは瞬時電力計測値
                cmd_w = False      # 受信したらコマンド排他フラグ解除
                cmd_rc = 0         # コマンド再送カウンタもゼロに
                data_mute = False
                draw_lcd()
                if ESP_NOW_F : # ESP NOW一斉同報発信を使う場合
                    espnow.broadcast(data=str('NPD=' + str(u.instant_power[0])))
                if (utime.time() - am_tc) >= am_interval :
                    if (AM_ID_1 is not None) and (AM_WKEY_1 is not None) :  # Ambient_1が設定されてる場合
                        try :                                               # ネットワーク不通発生などで例外エラー終了されない様に try except しとく
                            rn = am_now_power.send({'d1': u.instant_power[0]})
                            print('Ambient send OK!  / ' + str(rn.status_code) + ' / ' + str(Am_st_1))
                            Am_st_1 = 2
                            am_tc = utime.time()
                            rn.close()
                        except :
                            print('Ambient send ERR! / ' + str(Am_st_1))
                            Am_st_1 = 3
                        draw_am_status()
            elif u.type == 'EA72' : # [EA72]なら受信データは積算電力量
                cmd_w = False       # 受信したらコマンド排他フラグ解除
                cmd_rc = 0          # コマンド再送カウンタもゼロに
                tp_f = True         # 積算電力量を受信したのでTrue
                if ESP_NOW_F :      # ESP NOW一斉同報発信を使う場合
                    espnow.broadcast(data=str('TPD=' + str(u.total_power[0]) + '/' + u.total_power[1]))
                if (AM_ID_2 is not None) and (AM_WKEY_2 is not None) :  # Ambient_2が設定されてる場合
                    try :                                               # ネットワーク不通発生などで例外エラー終了されない様に try except しとく
                        rt = am_total_power.send({'created': u.total_power[1], 'd1': u.total_power[0]})
                        print('Ambient send OK! (Total Power) / ' + str(rt.status_code) + ' / ' + str(Am_st_2))
                        Am_st_2 = 2
                        rt.close()
                    except :
                        print('Ambient send ERR! (Total Power) / ' + str(Am_st_2))
                        Am_st_2 = 3
                    draw_am_status()

        if cmd_rc <= 10 : # コマンド再送信回数内なら
            if (utime.time() - cmd_tc) >= RES_TOUT : # コマンド送信後の受信待ちタイムアウトを越えたら、コマンド再送信
                print(">> cmd response timeout " + str(utime.time()))
                cmd_w = False  # コマンド排他フラグ解除
                cmd_tc = utime.time()
        else :
            print('>> cmd send retry count over! Reboot!! ' + str(utime.time()))
            machine.reset()

    # スマートメーターから長期間受信出来なかった場合の処理
    if not u.instant_power[1] == '' :
        if (utime.time() - u.instant_power[1]) >= TIMEOUT : # スマートメーターから瞬時電力計測値の応答が一定時間無い場合は電力値表示のみオフ
            data_mute = True
            draw_lcd()
        if (utime.time() - u.instant_power[1]) >= (TIMEOUT * 4) : # スマートメーターから瞬時電力計測値の応答が一定時間無い場合（TIMEOUTの4倍）はスマートメーターとの通信異常としてリブートする
            print('>> Communication failure?? Reboot!! ' + str(utime.time()))
            machine.reset()

    utime.sleep(0.1)
    gc.collect()
