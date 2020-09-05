# wisun_hat
MicroPython project / Wi-SUN HAT & M5StickC / Data storage uses Ambient

<br>

# <概要>

![Ambient_WISUN_0](https://kitto-yakudatsu.com/wp/wp-content/uploads/2019/10/Wi-SUN構成イメージ2.png)

<br>

* M5StickCとRHOM製Wi-SUN通信モジュール「BP35A1」を使って、家庭用スマートメーターをハックするプログラムです。
* 「BP35A1」をM5StickCへ簡単に装着する為の「Wi-SUN HATキット」（[BOOTHで販売中](https://kitto-yakudatsu.booth.pm/items/1650727)）を使えば、半田付けもジャンパー線配線も無しで使えます。
* AmbientというIoTデータ可視化サービスを使って、記録を残すことも可能です。（無料枠で使えます）
* MicroPythonで記述しています。（ファームウェアは UIFlow-v1.6.2 を推奨）

<br>
<br>

この様な電力データグラフを取得出来るようになります。

![Ambient_WISUN_1](https://kitto-yakudatsu.com/wp/wp-content/uploads/2019/10/瞬間電力計測値.png)

![Ambient_WISUN_2](https://kitto-yakudatsu.com/wp/wp-content/uploads/2019/10/30分毎積算電力量.png)

<br>

洗面所のドライヤー近くや、キッチンなどの大電力家電を使う場所にモニター子機を設置することで、うっかりブレーカーを落とす危険を排除します。

![Ambient_ENV_3](https://kitto-yakudatsu.com/wp/wp-content/uploads/2019/10/P1180703.jpg)

![Ambient_ENV_4](https://kitto-yakudatsu.com/wp/wp-content/uploads/2019/10/P1180702.jpg)

![Ambient_ENV_5](https://kitto-yakudatsu.com/wp/wp-content/uploads/2019/10/P1180705.jpg)

<br>

# <実行に必要なファイル>

## Ambientライブラリ「ambient.py」※オプション
Ambientへのデータ送信（記録）を使う場合は、[こちら](https://github.com/AmbientDataInc/ambient-python-lib)のライブラリが必要です。<br>
「ambient.py」を親機のM5StickCのルートに保存して下さい。<br>
※【2020.9.5】最新のAmbient.pyライブラリだと送信エラーになる症状が報告されています。エラーになる場合は、[Mar 17.2018版](https://github.com/AmbientDataInc/ambient-python-lib/tree/751afc4ad2ac5b6d37f236c5660e010a53cf670f)でお試し下さい。<br>

<br>

## 親機用Wi-SUNのUDPデータ解析ライブラリ「wisun_udp.py」**※必須**
親機のM5StickCのルートに保存して下さい。<br>

<br>

## 親機用プログラム本体「test_WiSUN_Ambient.py」**※必須**
M5StickC・M5StickCPlus用です。（プログラム内で機種自動判別させてます）<br>
※基板RevUpに伴い、UARTのピン割当てが変更されています。（[rev0.1] tx=0,rx=36 ⇒ [rev0.2] tx=0,rx=26）<br>
Rev0.1（2020/8/30以前の販売分）の方は、341行目をアクティブにして、342行目をコメントアウトして下さい。<br>
Rev0.2（2020/8/31以降の販売分）の方は、GitHubからダウンロードしたままで基本OKです。（341行目がコメントアウト、342行目がアクティブになっている筈）<br>
M5StickCのプログラム選択モード「APP.List」から起動させる為、親機のM5StickCの「Apps」配下に保存して下さい。<br>

<br>

## 親機用の設定ファイル「wisun_set_m.txt」**※必須**

* Bルートの「認証ID」を「BRID:」以降に、「パスワード」を「BRPSWD:」以降に追記して下さい。※必須です！
* Ambientで瞬間電力計測値を記録する場合は、「チャネルID」を「AM_ID_1:」以降に、「ライトキー」を「AM_WKEY_1:」以降に追記して下さい。
* Ambientで30分毎積算電力量を記録する場合は、「チャネルID」を「AM_ID_2:」以降に、「ライトキー」を「AM_WKEY_2:」以降に追記して下さい。
* 電力契約のアンペアブレーカー値を「AMPERE_LIMIT:」以降に追記して下さい。
* 電力使用過多警告の係数を「AMPERE_RED:」以降に追記して下さい。
* 子機向けのESN_NOW発信を止めたい場合は、「ESP_NOW:1」を「ESP_NOW:0」に修正して下さい。

※全てにおいて、空白文字、"などは含まない様にして下さい<br>
修正後、親機のM5StickCのルートに保存して下さい。<br>

<br>

## 子機用プログラム本体「test_WiSUN_read_m5stickc.py」/「test_WiSUN_read_m5stack.py」**※オプション**
「test_WiSUN_read_m5stickc.py」がM5StickC・M5StickCPlus用（プログラム内で機種自動判別させてます）で、「test_WiSUN_read_m5stack.py」がM5Stack用です。<br>
プログラム選択モード「APP.List」から起動させる場合は、「Apps」配下に保存して下さい。<br>

<br>

## 子機用の設定ファイル「wisun_set_r.txt」**※オプション**

* 電力契約のアンペアブレーカー値を「AMPERE_LIMIT:」以降に追記して下さい。
* 電力使用過多警告の係数を「AMPERE_RED:」以降に追記して下さい。

※全てにおいて、空白文字、"などは含まない様にして下さい<br>
修正後、子機のM5StickC（あるいはM5Stack）のルートに保存して下さい。<br>

<br>

# <使い方>

## 基本動作

- 親機のプログラム起動させると、M5StickCの画面に「*」が表示して積み上がっていきます。数十秒から数分すると時刻が、更に数十秒で電力値が表示されます。
- 5秒毎に瞬間電力計測値をスマートメーターから取得しています。（通信が重なったりした場合は数回途切れることもあります）
- 30分毎に積算電力量をスマートメーターから取得しています。
- 30秒毎に瞬間電力計測値を、30分毎に積算電力量をAmbientへ送信しています。（オプション設定した場合）
- 時刻が赤文字の時はAmbientへの通信が出来ていない事を示します。（**初回通信してない起動直後は時計は赤文字**）
- ESP_NOWにより、子機へ瞬間電力計測値を一斉同報しています。（オプションで一斉同報OFFにも出来ます）
- 親機はスマートメーターからの通信が[TIMEOUT]秒以上無かった場合に、子機は親機からのESP_NOW同報が[TIMEOUT]秒以上無かった場合に電力値表示が消えます。

<br>

## M5StickC/Plus版のボタン操作

- Aボタン（M5ロゴの有るボタン）を押すと画面消灯します。もう一度押すと画面点灯します。（電力が警告値を超えてる場合は、強制点灯されます）
- Bボタン（電源ボタンじゃない方の側面ボタン）を押すと表示が180度回転しますので、設置向きに合わせてお選び下さい。

![M5StickC_1](https://kitto-yakudatsu.com/wp/wp-content/uploads/2019/10/P1180699.jpg)

![M5StickC_2](https://kitto-yakudatsu.com/wp/wp-content/uploads/2019/10/P1180700.jpg)

<br>

## M5Stack版のボタン操作

- Aボタン（3ボタンの左のボタンです）を押すと画面消灯します。もう一度押すと画面点灯します。（電力が警告値を超えてる場合は、強制点灯されます）

<br>

# <参考ページ>
その他の情報については[ブログ](https://kitto-yakudatsu.com/archives/7206)をご参照下さい。<br>

<br>

# <アップデート履歴>

## 【2020.09.05】 [test_WiSUN_Ambient.py][test_WiSUN_read_m5stickc.py][test_WiSUN_read_m5stack.py] Update!

* 基板Rev0.2対応。（Rev0.2からUARTピン割当てが変更されました）
* UIFlow-v1.6.2 ファームへの対応。
* UIFlowファーム内にてntptimeライブラリが含まれる様になったので、ntptime.pyライブラリの転送が不要になりました
* M5StickCPlus対応（M5StickC版と同じソースコードで動作します）併せて[test_WiSUN_read.py]から[test_WiSUN_read_m5stickc.py]に改名。
* その他バグFix。
* ファイル毎の改行コード混在の是正。（LFに統一しました）

<br>

## 【2019.12.13】 [test_WiSUN_Ambient.py] Update!

* UIFlow-v1.4.2 ファームへの対応。（但し、ESP NOW同報で不具合が出てます。ESP NOW同報を使いたい場合はUIFlow-v1.4.1-betaファームをお使いください）
* 初回起動時にUARTの塵が出るケースへの対応。
* AmbientのチャネルID桁数チェックの削除。（5桁縛りだと勘違いしてました）

<br>

## 【2019.12.13】 [test_WiSUN_read.py] Update!

* UIFlow-v1.4.2 ファームへの対応。（但し、ESP NOW同報で不具合が出てます。ESP NOW同報を使いたい場合はUIFlow-v1.4.1-betaファームをお使いください）
* その他バグFix

<br>

## 【2019.10.31】

* 最初のリリース

