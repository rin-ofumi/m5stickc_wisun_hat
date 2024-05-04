# Wi-SUN HAT-C1（BP35C1-J11-T01用）のサンプルプログラム
# ver 0.0.1 (2024/5/4 Update)
# @rin-ofumi
#
# 確認した機種 (検証時のUIFlow Ver)
# - M5StickC (v1.13.4)
# - M5StickC Plus (v1.13.4
# - M5StickC Plus2 (v1.13.4)
#
# 参照元のプログラム
# ・@regreh氏のm5stickc_bp35c0-j11リポジトリ ( https://github.com/regreh/m5stickc_bp35c0-j11 )

from m5stack import *
import machine
import gc
import utime
#import ure
import binascii
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
rssi                    = ''

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
    global rssi

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
                elif filetxt[0] == 'RSSI' :
                    rssi = filetxt[1]
                    print('- RSSI: ' + rssi)
                elif filetxt[0] == 'COEFFICIENT' :
                    u.power_coefficient = int(filetxt[1])
                    print('- COEFFICIENT: ' + str(u.power_coefficient))
                elif filetxt[0] == 'UNIT' :
                    u.power_unit = float(filetxt[1])
                    print('- UNIT: ' + str(u.power_unit))
        if len(channel) == 2 and len(panid) == 4 and len(macadr) == 16:
            scanfile_flg = True
            channel = int(channel)
            panid = binascii.unhexlify(panid)
            macadr = binascii.unhexlify(macadr)
        else :
            print('>> [Wi-SUN_SCAN.txt] Illegal!!')
            scanfile_flg = False
    else :
        print('>> no [Wi-SUN_SCAN.txt] !')
    return scanfile_flg


# ECHONET-Lite電文Payload用のデータ長とデータの合成関数
def data_with_length(data):
    length = len(data)
    return [ length >> 8, length & 0xff ] + data


# BP35C1の送受信処理
class C1_Read:

    # データの構造は先頭から
    # 4バイト:ユニークコード（応答コマンドなら[0xD0F9EE5D]）
    # 2バイト:コマンドコード
    # 2バイト:メッセージ長
    # 2バイト:ヘッダー部チェックサム
    # 2バイト:データ部チェックサム
    # までがコマンドヘッダ部（12バイト固定）で、以降がコマンドデータ部（可変長）となる。
    # ※ROHMの「BP35C0-J11 Bルート通信について（Applocation Note）」を参照
    # ※ROHMの「J11 UART IFコマンド仕様書」の11ページのコマンドフォーマットを参照

    def __init__(self, uart):
        self.readbuf = b''
        self.line = b''
        self.bp35c1 = uart
        
    def readline(self): # 可変長バイナリ対応のreadline
        if self.bp35c1.any() != 0 : # 可変長バイナリ受信処理
            self.readbuf = self.readbuf + self.bp35c1.read()
        if b'\xd0\xf9\xee\x5d' in self.readbuf: # 応答コマンド[0xD0F9EE5D]かどうか
#            print(' -  readbuf: ' + binascii.hexlify(self.readbuf).decode('utf-8'))
            indent = self.readbuf.index(b'\xd0\xf9\xee\x5d') # 応答コマンド（受信データの先頭となるユニークコード）の場所
#            print(' - indent: ' + str(indent))
            length = self.readbuf[indent + 6] * 256 + self.readbuf[indent + 7] - 4 # データ部のメッセージ長（チェックサム分の4バイトを減らした値）
#            print(' - length: ' + str(length))
            if len(self.readbuf) >= indent + 12 + length: # データ部のメッセージ長分以降の受信データがある場合は次に繋ぐ
                self.line = self.readbuf[indent : indent + 12 + length] # 今回の応答コマンド分の受信データ
#                print(' -     line: ' + binascii.hexlify(self.line).decode('utf-8'))
                self.readbuf = self.readbuf[indent + 12 + length : ] # 残データは次の受信に繋ぐ
#                print(' - readbuf2: ' + binascii.hexlify(self.readbuf).decode('utf-8'))
                return True # 応答コマンドが最後まで受信できた場合
        return False # 応答コマンドが最後まで受信できなかった、または応答コマンドではなかった場合
        
    def retcmd(self): # コマンドコードの取得
        if b'\xd0\xf9\xee\x5d' in self.line:
            indent = self.line.index(b'\xd0\xf9\xee\x5d')
            return self.line[indent + 4] * 256 + self.line[indent + 5] # 応答コマンドならコマンドコードを抽出して返す
        return -1
        
    def retdata(self): # 受信データの取得
        if b'\xd0\xf9\xee\x5d' in self.line:
            indent = self.line.index(b'\xd0\xf9\xee\x5d')
            len = self.line[indent + 6] * 256 + self.line[indent + 7] - 4 # データ部のメッセージ長（チェックサム分の4バイトを減らした値）
            return self.line[indent + 12 : indent + 12 + len] # 応答コマンドならデータ部を抽出して返す
        return b''
        
    def clearbuf(self): # 受信バッファーのクリア
        if self.bp35c1.any() != 0 :
            self.bp35c1.read()
        self.readbuf = b''
        return 0
        
    def sendcmd(self, cmd, data): # コマンドの送信
        bin = [0xd0, 0xea, 0x83, 0xfc] # ユニークコード（要求コマンド[0xD0EA83FC]固定）
        bin = bin + [ cmd >> 8, cmd & 0xff ] # ユニークコード＋コマンドコード（cmd）
        length = 4 + len(data) # メッセージ長（ヘッダー部・データ部チェックサムとデータ部の長さを足した値）
        bin = bin + [ length >> 8, length & 0xff ] # ユニークコード＋コマンドコード（cmd）＋メッセージ長

        # ヘッダ部（ユニークコード＋コマンドコード＋メッセージ長）のチェックサム計算
        sum = 0
        for b in bin:
            sum = (sum + int(b)) & 0xffff
        bin = bin + [ sum >> 8, sum & 0xff ] # ヘッダ部のチェックサム部を継ぎ足し

        # データ部のチェックサム計算（チェックサム部分は含まない）
        sum = 0
        for b in data:
            sum = (sum + int(b)) & 0xffff
        bin = bin + [ sum >> 8, sum & 0xff ] # データ部のチェックサム部を継ぎ足し

        # チェックサム込みでコマンド送信
        self.bp35c1.write(bytes(bin + data))


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


# BP35C1 UART設定
uart = machine.UART(1, tx=0, rx=36) # Wi-SUN HAT rev0.2用
uart.init(115200, bits=8, parity=None, stop=1, timeout=100, timeout_char=100)
lcd.print('***', 0, 0, lcd.WHITE)
wisun = C1_Read(uart)
print('>> UART init OK')


# BP35C1 起動時ハードウェアリセット（リセットピン制御）
pinout = machine.Pin(26,machine.Pin.OUT) # Wi-SUN HAT rev0.2用
pinout.value(0)
utime.sleep(0.1)
pinout.value(1)
print('>> RESET PIN release')


# UARTの送受信バッファーの塵データをクリア
wisun.clearbuf()
print('>> UART RX/TX Data Clear')


# BP35C1 起動時ハードウェアリセット（コマンド）
wisun.sendcmd(0x00d9, [])  # F1 ハードウェアリセット
utime.sleep(0.5)
while True: # Wait response
    if wisun.readline() == True :
        if wisun.retcmd() == 0x6019 :   # F2 起動完了通知
            break
print('>> BP35C1 Boot OK')
utime.sleep(0.5)


# BP35C1 ファームウェアバージョン確認（参考）
wisun.sendcmd(0x006b, [])  # バージョン情報要求
#utime.sleep(0.1)
fw_id = ''
fw_v1 = ''
fw_v2 = ''
fw_rev = ''
utime.sleep(0.5)
while True: # Wait response
    if wisun.readline() == True :
        if wisun.retcmd() == 0x206b :   # バージョン情報取得応答
            if wisun.retdata()[0] == 0x01 :
                fw_id = wisun.retdata()[1:3]
                fw_v1 = wisun.retdata()[3]
                fw_v2 = wisun.retdata()[4]
                fw_rev = wisun.retdata()[4:]
                print('>> BP35C1 firmware_ver:')
                print(' -  ID: ' + binascii.hexlify(fw_id).decode('utf-8')) # ファームウェアID
                print(' -  v1: ' + '{:02d}'.format(fw_v1)) # メジャーバージョン
                print(' -  v2: ' + '{:02d}'.format(fw_v2)) # マイナーバージョン
                print(' - rev: ' + binascii.hexlify(fw_rev).decode('utf-8')) # リビジョン
                break
print('>> BP35C1 firmware ver check OK')
utime.sleep(0.5)


# BP35C1 初期設定
wisun.sendcmd(0x005f, [0x05, 0x00, 0x04, 0x00])   # F3 初期設定要求
# ROHMのApplocation Noteと同じ設定(チャネルはスキャン後に改めて再設定する)
# 動作モード:           0x05 [Dual(Bルート&HAN)]
# HAN Sleep 機能設定:   0x00 [無効]
# チャネル:             0x04 [922.5MHz]
# 送信電力:             0x00 [20 mW]
utime.sleep(0.5)
while True: # Wait response
    if wisun.readline() == True :
        if wisun.retcmd() == 0x205f:  # F4 初期設定応答
            if wisun.retdata()[0] == 0x01 :
                break
lcd.print('****', 0, 0, lcd.WHITE)
print('>> BP35C1 Initialize OK')
utime.sleep(0.5)


# BルートPANA認証情報(B-root ID & PASSWORD)設定
wisun.sendcmd(0x0054, list(bytearray(BRID + BRPSWD))) # F5 BルートPANA認証情報設定要求
utime.sleep(0.5)
while True: # Wait response
    if wisun.readline() == True :
        if wisun.retcmd() == 0x2054:  # F6 BルートPANA認証情報設定応答
            if wisun.retdata()[0]==0x01:
                break
            else:
                print('!! BP35C1 B-root ID and PASSWORD set NG !!') # 設定失敗した場合は、3秒後に自動リトライ
                utime.sleep(3.0)
                wisun.sendcmd(0x0054, list(bytearray(BRID + BRPSWD)))
lcd.print('***** **', 0, 0, lcd.WHITE)
print('>> BP35C1 B-root ID and PASSWORD set OK')
gc.collect()
print('heapmemory= ' + str(gc.mem_free()))
utime.sleep(0.5)


# アクティブスキャン（「Wi-SUN_SCAN.txt」の存在しない or 中身が異常値だった場合）
if not wisun_scan_filechk() :
    scanOK = False
    s_c = 1
    
    if m5type == 0 : # M5StickC(無印)の場合の画面オフセット
        offset = 9
    if m5type == 1 : # M5StickC Plus/2の場合の画面オフセット    
        offset = 16

    while not scanOK : # SCAN_COUNTの回数は繰り返しスキャンする
        wisun.sendcmd(0x0051,[0x06,0x00,0x03,0xFF,0xF0,0x01] + list(bytearray(BRID[-8:]))) # F7 アクティブスキャン実行要求
        # ROHMのApplocation Noteと同じ設定
        # スキャン時間:      0x06 [9.64ms×64=約640ms]
        # スキャンチャンネル: 0x0003FFF0 [4～17chスキャン]
        # ID設定:            0x01 [Paring IDあり]

        print('>> Activescan count:' + str(s_c) + ' start!')

        # スキャン1回分のループ処理
        scan_res_end = False
        while not scan_res_end :
            if wisun.readline() == True :
                if wisun.retcmd() == 0x2051:  # F9 アクティブスキャン実行応答（スキャン完了応答？）
                    scan_res_end = True # スキャンが1周完了してるのでループ抜け
                    print('>> Activescan count:' + str(s_c) + ' done!')
                if wisun.retcmd() == 0x4051:  # F8 アクティブスキャン結果通知（スキャン実行要求を一度すると、要求時のチャンネル分が全て通知されるので一通り受信する）
                    data = wisun.retdata()
                    if data[0] == 0x00: # スキャン応答あり
                        channel = data[1]
                        count = data[2]
                        macadr = data[3:11]
                        panid = data[11:13]
                        rssi = data[13]
                        print('>> smartmeter Discovered!')
                        print(' -  Channel: ' + '{:02d}'.format(channel))
                        print(' -   Pan_ID: ' + binascii.hexlify(panid).decode('utf-8'))
                        print(' - MAC_Addr: ' + binascii.hexlify(macadr).decode('utf-8'))
                        print(' -     RSSI: ' + str(rssi))
                        print('>> Activescan end!')
                        lcd.print(str(channel) + 'ch Hit!', 5, (channel-4)*offset+10)  # スマートメーターから応答あり
                        with open('/flash/Wi-SUN_SCAN.txt' , 'w') as f:
                            f.write('Channel:' + '{:02d}'.format(channel) + '\r\n')
                            f.write('Pan_ID:' + binascii.hexlify(panid).decode('utf-8') + '\r\n')
                            f.write('MAC_Addr:' + binascii.hexlify(macadr).decode('utf-8') + '\r\n')
                            f.write('RSSI:' + str(rssi) + '\r\n')
                            print('>> [Wi-SUN_SCAN.txt] wrote')
                        scanOK = True
                        scan_res_end = True # スキャン応答有りなのでループ抜け
                    if data[0] == 0x01: # スキャン応答なし
                        channel = data[1]
                        print('No response from Channel ' + str(channel))
                        lcd.print(str(channel) + 'ch -', 5, (channel-4)*offset+10)
        
        s_c+=1
        
        if s_c > SCAN_COUNT : # アクティブスキャンの試行回数制限を超えた場合は、何らかの事情でスマートメーターが見付からないので環境を見直すべし！
            raise ValueError('Scan retry count over! Please Reboot!')
        
        utime.sleep(0.5)
        gc.collect()

lcd.print('***** ***', 0, 0, lcd.WHITE)
utime.sleep(0.5)
wisun.clearbuf()
gc.collect()
print('heapmemory= ' + str(gc.mem_free()))


# BP35C1 アクティブスキャンの結果を踏まえて改めて初期設定（チャンネル合わせ）
wisun.sendcmd(0x005f, [0x05, 0x00, channel, 0x00])   # F10 初期設定要求（スキャン結果を利用）
# ROHMのApplocation Noteと同じ設定
# 動作モード:           0x05 [Dual(Bルート&HAN)]
# HAN Sleep 機能設定:   0x00 [無効]
# チャネル:             channel [アクティブスキャンで発見されたチャンネル]
# 送信電力:             0x00 [20 mW]
utime.sleep(0.5)
while True: # Wait response
    if wisun.readline() == True :
        if wisun.retcmd() == 0x205f:  # F11 初期設定応答
            if wisun.retdata()[0] == 0x1:
                break
            else :
                print("!! 0x005f FAILED with error code " + str(wisun.retdata()[0]))
                utime.sleep(3.0)
                wisun.sendcmd(0x005f, [0x05, 0x00, channel, 0x00]) # 失敗したらF10再送
        else: # 0x2053以外が返ってきた場合
            print(">> Unknown response cmd " + str(wisun.retcmd()))
print('>> BP35C1 Initialize OK with channel')
utime.sleep(0.5)


# Bルート動作開始要求
wisun.sendcmd(0x0053, []) # F12 Bルート動作開始要求
#utime.sleep(0.5)
while True: # Wait response
    if wisun.readline() == True :
        if wisun.retcmd() == 0x2053:  # F13 Bルート動作開始応答
            if wisun.retdata()[0] == 0x01: # 成功
                break
            elif wisun.retdata()[0] == 0x0e: # MAC接続失敗
                print(">> No response from smartmeter")
#                utime.sleep(0.5)
                wisun.sendcmd(0x0053, []) # 失敗したらF12再送
            else:
                print("!! 0x0053 FAILED with error code " + str(wisun.retdata()[0]))
        else: # 0x2053以外が返ってきた場合
            print(">> Unknown response " + str(wisun.retcmd()))
print(">> B-root connected")
utime.sleep(0.5)


# UDPポートOPEN要求
wisun.sendcmd(0x0005, [0x0e, 0x1a]) # F14 UDPポートOPEN要求
# ROHMのApplocation Noteと同じ設定
# UDPポート番号:        0x0e1a [ECHONET-Lite UDPポート3610 = 0e1a]
while True: # Wait response
    if wisun.readline() == True :
        if wisun.retcmd() == 0x2005:  # F15 UDPポートOPEN応答
            if wisun.retdata()[0] == 0x01:
                break
print(">> UDP port 0x0e1a opened")
utime.sleep(0.5)


# BルートPANA開始要求
wisun.sendcmd(0x0056, []) # F16 BルートPANA開始要求
while True: # Wait response
    if wisun.readline() == True :
        if wisun.retcmd() == 0x2056:  # F17 BルートPANA開始応答
            if wisun.retdata()[0] == 0x01:
                print(">> F17 received")
            else:
                print(">> No response from smartmeter")
#                utime.sleep(0.5)
                wisun.sendcmd(0x0056, []) # 失敗したらF16再送
        elif wisun.retcmd() == 0x6028:    # F18 PANA認証結果通知
            if wisun.retdata()[0] == 0x01:
                print(">> PANA authentication OK")
                break
            else:
                print(">> PANA authentication NG!")
                for file_name in uos.listdir('/flash') :
                    if file_name == 'Wi-SUN_SCAN.txt' :
                        uos.remove('/flash/Wi-SUN_SCAN.txt') #チャンネルが変わった可能性があるので、ファイル削除
                        print(">> Erase Wi-SUN_SCAN.txt! & Reboot!!")
                        utime.sleep(1)
                        machine.reset() #ファイル削除の後リブートする
lcd.print('***** ****', 0, 0, lcd.WHITE)
utime.sleep(0.5)
wisun.clearbuf()
gc.collect()
print('heapmemory= ' + str(gc.mem_free()))


# ECHONET Lite 積算電力係数(COEFFICIENT)要求コマンド送信
iph=[0xfe, 0x80, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]      # iph = 送信先IPv6アドレス(前半): 0xFE800000 00000000 [ユニキャスト]
ipl=list(macadr)                                    # ipl = 送信先IPv6アドレス(後半): macadr ※MACアドレスの最初の1バイト下位2bit目は反転する
ipl[0] = ipl[0] ^ 0x02
port=[0x0e, 0x1a, 0x0e, 0x1a]                       # port = 送信元＆送信先UDPポート番号: 0x0e1a [ECHONET-Lite UDPポート3610 = 0e1a] ※送信元・先で同じアドレス
if u.power_coefficient == 0: # COEFFICIENTが初期値のままなら
    payload = data_with_length(list(bytearray(GET_COEFFICIENT))) # payload = 送信データサイズと送信データ
    wisun.sendcmd(0x0008, iph+ipl+port+payload) # データ送信要求(Get) - 積算電力係数(COEFFICIENT)
    print('>> [GET_COEFFICIENT] cmd send ' + str(utime.time()))
    cmd_tc = utime.time()   # 受信タイムアウト用カウンタのリセット

    while True :
        if wisun.readline() == True :
            if wisun.retcmd() == 0x6018: # データ受信通知(Get_Res)
                u.read('ERXUDP 1 2 3 4 5 6 7 ' + ''.join('{:02X}'.format(int(x)) for x in list(wisun.retdata())[27:]))
                if u.type == 'D3' : # D3 積算電力量係数(COEFFICIENT)
                    print(" - COEFFICIENT: " + str(u.power_coefficient) + ' ' + str(utime.time()))
                    break
                else:
                    print(">> Unknown type " + u.type + ' ' + str(utime.time()))
            else: # 何か予想外なのが返ってきた場合
                print(">> Unknown response "+str(wisun.retcmd()) + ' ' + str(utime.time()))
        if (utime.time() - cmd_tc) >= RES_TOUT : # 受信タイムアウトした場合はコマンド非対応スマートメータと判断し、固定値とする
            print('>> response timeout! set[COEFFICIENT = 1]' + ' ' + str(utime.time()))
            u.power_coefficient = 1
            break
    
    with open('/flash/Wi-SUN_SCAN.txt' , 'a') as fc:
        fc.write('COEFFICIENT:' + str(u.power_coefficient) + '\r\n')
lcd.print('***** *****', 0, 0, lcd.WHITE)
utime.sleep(0.5)


# ECHONET Lite 積算電力単位(UNIT)要求コマンド送信
if u.power_unit == 0.0 : # UNITが初期値のままなら
    payload = data_with_length(list(bytearray(GET_TOTAL_POWER_UNIT)))
    wisun.sendcmd(0x0008, iph+ipl+port+payload)
    print('>> [GET_UNIT] cmd send ' + str(utime.time()))
    cmd_tc = utime.time()   # 受信タイムアウト用カウンタのリセット

    while True :
        if wisun.readline() == True :
            if wisun.retcmd() == 0x6018: # データ受信通知(Get_Res)
                u.read('ERXUDP 1 2 3 4 5 6 7 ' + ''.join('{:02X}'.format(int(x)) for x in list(wisun.retdata())[27:]))
                if u.type == 'E1' : #E1 積算電力量単位(UNIT)
                    print(" - UNIT: " + str(u.power_unit) + ' ' + str(utime.time()))
                    break
                else:
                    print(">> Unknown type " + u.type + ' ' + str(utime.time()))
            else: # 何か予想外なのが返ってきた場合
                print(">> Unknown response "+str(wisun.retcmd()) + ' ' + str(utime.time()))
        if (utime.time() - cmd_tc) >= RES_TOUT : # 受信タイムアウトした場合はコマンド非対応スマートメータと判断し、固定値とする
            print('>> response timeout! set[UNIT = 0.1] ' + str(utime.time()))
            u.power_unit = 0.1
            break
    
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
wisun.clearbuf()
gc.collect()
print('heapmemory= ' + str(gc.mem_free()))
print(">> Start mainloop! " + str(utime.time()))


# メインループ
while True:
    # スマートメーターへのコマンド送信処理
    if cmd_w == False : # コマンド重送しない為の排他制御
        if ((utime.time() - tp_tc) >= (30 * 60)) or ((not tp_f) and ((utime.time() - tp_tc) >= 10)) : # 30分毎に積算電力量要求コマンド送信（受信出来ない時のコマンド再送信は10秒開ける）
            wisun.clearbuf()
            payload = data_with_length(list(bytearray(GET_TOTAL_POWER_30)))
            wisun.sendcmd(0x0008, iph+ipl+port+payload)
            print('>> [GET_TOTAL_POWER_30] cmd send ' + str(utime.time()))
            tp_tc = utime.time()
            tp_f = False # 積算電力量要求を出したので、受信してない扱いでFalse
            cmd_tc = utime.time()
            cmd_w = True # コマンド送信したので排他状態にする
            cmd_rc += 1
        elif (utime.time() - np_tc) >= np_interval : # 瞬時電力計測値要求コマンド送信
            wisun.clearbuf()
            payload = data_with_length(list(bytearray(GET_NOW_P)))
            wisun.sendcmd(0x0008, iph+ipl+port+payload)
            print('>> [GET_NOW_P] cmd send ' + str(utime.time()))
            np_tc = utime.time()
            cmd_tc = utime.time()
            cmd_w = True # コマンド送信したので排他状態にする
            cmd_rc += 1

    # スマートメーターからの受信処理
    if cmd_w == True :
        if wisun.readline() == True :
            if wisun.retcmd() == 0x6018: # データ受信通知(Get_Res)
                u.read('ERXUDP 1 2 3 4 5 6 7 ' + ''.join('{:02X}'.format(int(x)) for x in list(wisun.retdata())[27:]))
                if u.type == 'E7' :  # [E7]なら受信データは瞬時電力計測値
                    cmd_w = False    # 受信したらコマンド排他フラグ解除
                    cmd_rc = 0       # コマンド再送カウンタもゼロに
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
