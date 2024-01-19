from m5stack import *
from m5stack_ui import *
import machine
import gc
import utime
import uos
import _thread
import espnow
import wifiCfg
import ntptime


# 変数初期値定義
lcd_mute                = False         # グローバル
data_mute               = False         # グローバル
disp_mode               = True          # グローバル
beep                    = True          # グローバル
now_power               = 0             # グローバル
now_power_time          = utime.time()
TIME_TB                 = ["00:00:00", "00:30:00", \
                        "01:00:00", "01:30:00", \
                        "02:00:00", "02:30:00", \
                        "03:00:00", "03:30:00", \
                        "04:00:00", "04:30:00", \
                        "05:00:00", "05:30:00", \
                        "06:00:00", "06:30:00", \
                        "07:00:00", "07:30:00", \
                        "08:00:00", "08:30:00", \
                        "09:00:00", "09:30:00", \
                        "10:00:00", "10:30:00", \
                        "11:00:00", "11:30:00", \
                        "12:00:00", "12:30:00", \
                        "13:00:00", "13:30:00", \
                        "14:00:00", "14:30:00", \
                        "15:00:00", "15:30:00", \
                        "16:00:00", "16:30:00", \
                        "17:00:00", "17:30:00", \
                        "18:00:00", "18:30:00", \
                        "19:00:00", "19:30:00", \
                        "20:00:00", "20:30:00", \
                        "21:00:00", "21:30:00", \
                        "22:00:00", "22:30:00", \
                        "23:00:00", "23:30:00"]
TotalPower              = [0] * 97
day_buf                 = ''


# 表示OFFボタン処理スレッド関数
def buttonA_wasPressed():
    global lcd_mute

    if lcd_mute :
        lcd_mute = False
    else :
        lcd_mute = True

    if lcd_mute == True :
        screen.set_screen_brightness(0) #バックライト輝度調整（OFF）
    else :
        screen.set_screen_brightness(50) #バックライト輝度調整（中くらい）

    utime.sleep(0.1)


# 表示モード切替ボタン処理スレッド関数
def buttonB_wasPressed():
    global disp_mode

    if disp_mode :
        disp_mode = False
    else :
        disp_mode = True

    # ボタンエリア以外は一旦画面全消し
    lcd.rect(0 , 0, 320, 205, 0x000000, 0x000000)

    if disp_mode == True :  # 瞬間電力値最大化表示
        draw_w()
    else :                  # 積算電力棒グラフ表示
        draw_w()
        draw_graph_tp()

    utime.sleep(0.1)


# BEEP音ボタン処理スレッド関数
def buttonC_wasPressed():
    global beep

    if beep :
        beep = False
    else :
        beep = True

    if beep == True :   # BEEP ON
        beep_button.set_bg_color(0x2acf00)
        beep_button.set_btn_text_color(0xffffff)
    else :              # BEEP OFF
        beep_button.set_bg_color(0x000000)
        beep_button.set_btn_text_color(0x7b7b7b)

    utime.sleep(0.1)


# 瞬間電力値表示処理関数
def draw_w():
    if data_mute or (now_power == 0) : # 瞬間電力値の更新時刻が30秒以上前なら電力値非表示（黒文字化）
        fc = 0x000000   # 黒色（見えなくする）
    else :
        if now_power >= (AMPERE_LIMIT * AMPERE_RED * 100) :  # 警告閾値超え時は文字が赤くなる
            fc = 0xff0000   # 赤色
            if lcd_mute == True :   # 閾値超え時はLCD ON
                screen.set_screen_brightness(50) #バックライト輝度調整（中くらい）
            if beep == True :       # 閾値越え時、且つ beep == True なら音を鳴らす
                speaker.playTone(220, 1/2)
        else :
            fc = 0xffffff   # 白色
            if lcd_mute == True :
                screen.set_screen_brightness(0) #バックライト輝度調整（OFF）

    if disp_mode == True :  # 瞬間電力値最大化表示モード時
        lcd.rect(0 , 0, 320, 205, 0x000000, 0x000000)
        # 瞬間電力値表示
        label_P_B.set_hidden(False)
        label_P_B.set_text_color(fc)
        label_P_B.set_text(str(now_power))
        # W表示
        label_W_B.set_hidden(False)
        label_W_B.set_text_color(fc)
        label_W_B.set_text('W')
    else :                  # 積算電力棒グラフ表示モード時
        lcd.rect(0 , 0, 320, 63, 0x000000, 0x000000)
        # 瞬間電力値表示
        label_P_A.set_hidden(False)
        label_P_A.set_text_color(fc)
        label_P_A.set_text(str(now_power))
        # W表示
        label_W_A.set_hidden(False)
        label_W_A.set_text_color(fc)
        label_W_A.set_text('W')


def draw_graph_tp () : # 積算電力量棒グラフ描画関数
    graph_scale = 3.0       # グラフ表示倍率（ややサチる値にしてる）
    graph_red = 0.7         # グラフ赤色閾値（0.0～1.0）
    graph_orange = 0.3      # グラフ橙色閾値（0.0～1.0）
    graph_color = 0x000000  # 初期値はとりあえず黒色
    width = 5

    lcd.line(0, 64, 320, 64, 0xaeaeae)
    lcd.line(0, 186, 320, 186, 0xaeaeae)
    lcd.line(15 + (6 * 0), 186, 15 + (6 * 0), 190, 0xaeaeae)
    lcd.line(15 + (6 * 12), 186, 15 + (6 * 12), 190, 0xaeaeae)
    lcd.line(15 + (6 * 24), 186, 15 + (6 * 24), 190, 0xaeaeae)
    lcd.line(15 + (6 * 36), 186, 15 + (6 * 36), 190, 0xaeaeae)
    lcd.line(15 + (6 * 48), 186, 15 + (6 * 48), 190, 0xaeaeae)

    lcd.rect(0, 65, 320, 120, 0x000000, 0x000000)
    lcd.line(15 + (6 * 0), 65, 15 + (6 * 0), 186, 0x303030)
    lcd.line(15 + (6 * 12), 65, 15 + (6 * 12), 186, 0x303030)
    lcd.line(15 + (6 * 24), 65, 15 + (6 * 24), 186, 0x303030)
    lcd.line(15 + (6 * 36), 65, 15 + (6 * 36), 186, 0x303030)
    lcd.line(15 + (6 * 48), 65, 15 + (6 * 48), 186, 0x303030)

    label_00.set_hidden(False)
    label_06.set_hidden(False)
    label_12.set_hidden(False)
    label_18.set_hidden(False)
    label_24.set_hidden(False)

    for n in range(1, 97, 1) :
        if ( TotalPower[n] == 0 ) or ( TotalPower[n - 1] == 0 ):
            h_power = 0
        else :
            h_power = TotalPower[n] - TotalPower[n - 1]
        
        if h_power > 0 :
            height = int(h_power * graph_scale / AMPERE_LIMIT)
        else :  # 基本、マイナス値は有り得ないが念のため
            height = 0

        if height > 120 :
            height = 120

        if n <= 48 :
            x_start = ((n - 1) * 6) + 16
            if height != 0 :
                graph_color = 0xaeaeae  # 前日分は灰色
        else :
            x_start = (((n - 1) - 48) * 6) + 16
            if height != 0 :
                if height > (120 * graph_red) :
                    graph_color = 0xff0000  # 赤色
                elif height > (120 * graph_orange) :
                    graph_color = 0xffac00  # 橙色
                else :
                    graph_color = 0x2acf00  # 緑色

#        print('h_power[' + str(n) + ']=' + str(h_power))
#        print('height [' + str(n) + ']=' + str(height))
            
        y_start = 185 - height

        if height != 0 :
            lcd.rect(x_start, y_start, width, height, graph_color, graph_color)


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


# WiFi設定
wifiCfg.autoConnect(lcdShow=True)
print('>> WiFi init OK')


# RTC設定
ntp = ntptime.client(host='jp.pool.ntp.org', timezone=9)
print('>> RTC init OK')


# 初期設定ファイル読込み
wisun_set_filechk()


# 画面初期化
screen = M5Screen()
screen.clean_screen()
screen.set_screen_bg_color(0x000000)
screen.set_screen_brightness(50) #バックライト輝度調整（中くらい）


# 基本要素の描画
label_P_A = M5Label('', x=97, y=5, color=0xffffff, font=FONT_MONT_38)
label_W_A = M5Label('w', x=236, y=25, color=0xffffff, font=FONT_MONT_26)
label_P_A.set_hidden(True)
label_W_A.set_hidden(True)

label_P_B = M5Label('', x=99, y=92, color=0xffffff, font=FONT_MONT_38)
label_W_B = M5Label('w', x=228, y=110, color=0xffffff, font=FONT_MONT_26)
label_P_B.set_hidden(True)
label_W_B.set_hidden(True)

label_D = M5Label('', x=2, y=208, color=0xffffff, font=FONT_MONT_18)

beep_button = M5Btn(text='BEEP', x=230, y=210, w=70, h=25, bg_c=0x000000, text_c=0x7b7b7b, font=FONT_MONT_14, parent=None)
if beep == True :   # BEEP ON
    beep_button.set_bg_color(0x2acf00)
    beep_button.set_btn_text_color(0xffffff)
else :              # BEEP OFF
    beep_button.set_bg_color(0x000000)
    beep_button.set_btn_text_color(0x7b7b7b)

label_00 = M5Label('00:00', x=0, y=188, color=0xffffff, font=FONT_MONT_10)
label_06 = M5Label('06:00', x=72, y=188, color=0xffffff, font=FONT_MONT_10)
label_12 = M5Label('12:00', x=144, y=188, color=0xffffff, font=FONT_MONT_10)
label_18 = M5Label('18:00', x=216, y=188, color=0xffffff, font=FONT_MONT_10)
label_24 = M5Label('24:00', x=286, y=188, color=0xffffff, font=FONT_MONT_10)
label_00.set_hidden(True)
label_06.set_hidden(True)
label_12.set_hidden(True)
label_18.set_hidden(True)
label_24.set_hidden(True)
print('>> Disp init OK')


# ボタン検出スレッド起動
btnA.wasPressed(buttonA_wasPressed)
btnB.wasPressed(buttonB_wasPressed)
btnC.wasPressed(buttonC_wasPressed)
print('>> Button Check thread ON')


# ESP NOW設定
wifiCfg.wlan_ap.active(True)
#wifiCfg.wlan_sta.active(False)
espnow.init(0)  # UIFlow Ver1.10.2以降への対応
print('>> ESP NOW init')


# メインループ
while True:
    update_count = utime.time() - now_power_time
    if update_count >= TIMEOUT : # 瞬間電力値の更新時刻が[TIMEOUT]秒以上前なら電力値非表示（黒文字化）
        data_mute = True
        draw_w()

    d = espnow.recv_data()
    if len(d[2]) > 0 :
        r_key = str(d[2][:4].decode('utf-8').strip())   # ESPNOW受信データの先頭4文字は、データ種別
        r_data = d[2][4:].decode('utf-8').strip()       # ESPNOW受信データの先頭4文字より後が、データ
        if r_key == 'NPD=' :   # 瞬間電力値受信処理（サンプルプログラム版）
            if not now_power == int(r_data) :
                now_power = int(r_data)
                data_mute = False
                now_power_time = utime.time()
                draw_w()
                print(str(now_power) + ' W')
        elif r_key == 'INST':   # 瞬間電力値受信処理（yonmas氏のsmm3版）
            inst_data = r_data.strip().split('/')
            if not now_power == int(inst_data[0]) :
                now_power = int(inst_data[0])
                data_mute = False
                now_power_time = utime.time()
                draw_w()
                print(str(now_power) + ' W')
        elif r_key == 'TPD=' : # 積算電力量受信処理（仮）
            tpd_t = r_data.strip().split('/')
            tpd_wh = int(float(tpd_t[0]) * 1000)
            tpd_tt = tpd_t[1].strip().split(' ')
            tpd_date = tpd_tt[0]
            tpd_time = tpd_tt[1]
            print(tpd_wh)
            print(tpd_date)
            print(tpd_time)
#            print(TIME_TB.index(tpd_time))

            # 日跨ぎ処理
            if day_buf == '' :  # 初回時処理
                day_buf = tpd_date
                if TIME_TB.index(tpd_time) == 0 :
                    TotalPower[48] = tpd_wh
            else :
                if day_buf != tpd_date : # 日跨ぎなのでリストを1日分インクリメント
                    if TIME_TB.index(tpd_time) >= 1 :
                        day_buf = tpd_date
                        for n in range(48, 97 ,1) :
                            TotalPower[n - 48] = TotalPower[n]
                        for n in range(49, 97 ,1) :
                            TotalPower[n] = 0

            if TIME_TB.index(tpd_time) == 0 :
                TotalPower[96] = tpd_wh
            else :
                TotalPower[TIME_TB.index(tpd_time) + 48] = tpd_wh

#            for i in range(97) :
#                print(str(i) + '=' + str(TotalPower[i]))

            # 積算電力量の最終受信日付表示（デバッグ用）
            label_D.set_text(tpd_date + ' ' + tpd_time)

            # 棒グラフ描画
            if disp_mode != True :  # 積算電力量棒グラフ表示モードなら
                draw_graph_tp()

    gc.collect()
    utime.sleep(0.1)