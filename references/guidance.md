# 多语言沟通与提示示例（zh-CN / ja / en）

本文件为 agent 提供三语沟通参考。与用户对话时跟随用户的语言；构建个人 HTML 的 `--lang "$session_lang"` 和 `mountSession(html, language)` 优先采用用户显式指定的语言，否则跟随对话语言。

## 1. 语言参数、默认猫名与界面范围对照

| 项目 | 简体中文 (`zh-CN`) | 日本語 (`ja`) | English (`en`) |
| --- | --- | --- | --- |
| `--lang` / `language` | `zh-CN` | `ja` | `en` |
| 未给猫名时的默认名 | `我家的猫` | `うちの猫` | `My cat` |
| 猫主人提供了名字 | 原样使用用户给定的名字 | ユーザー指定の名前をそのまま使用 | Use the owner-provided name verbatim |
| 多语言生效范围 | 对话、文档、书签向导/弹窗、技能自有提示 | 会話、ドキュメント、ブックマークガイド/ダイアログ、スキル固有の案内表示 | Conversation, docs, bookmarklet wizard/dialogs, skill's own prompts |
| 原站游戏控件 | 保留原站原有日文（选猫、体型、声音、快捷键等） | 本家サイトの日本語UIをそのまま保持 | Keep upstream site's original Japanese UI controls |

## 2. 要图与补拍引导

当用户未附照片，或只有正脸/侧拍照、需要确认走「补拍俯拍照」还是「AI 生成俯视姿势」时：

- **`zh-CN`**：
  > 请发一张猫咪的照片（还能顺便告诉我它的名字，不填我就叫它「我家的猫」）。如果有从正上方拍到整个背部和整条尾巴的照片，可以直接在本机抠图保留真实花纹；如果手边只有正脸或侧拍生活照，我可以参考照片生成俯视姿势，或者你也可以补拍一张俯拍照走纯实拍路线。
- **`ja`**：
  > 猫ちゃんの写真を送ってください（名前も教えていただければボタンに表示します。省略時は「うちの猫」になります）。真上から背中全体としっぽが写っている写真があれば、端末内でそのまま切り抜いて実際の模様を残せます。正面や横からの写真しかない場合は、写真を参考に真上からの姿勢をAI生成するか、真上からの写真を1枚追加して実写切り抜きにするかを選べます。
- **`en`**：
  > Please share a photo of your cat (and let me know their name if you'd like it on the button; otherwise I'll use "My cat"). If you have a top-down photo showing the full back and tail, I can cut it out locally to keep the exact markings. If you only have front or side snapshots, we can either synthesize a top-down view from your photos or use a quick top-down shot you take for a pure real-photo cutout.

## 3. 云端 AI 生图的服务告知与同意确认

当需要使用云端图像工具时，先确认当前环境实际可用的服务。把下列占位符换成该服务的真实名称。若用户已经明确同意把这组照片交给该服务，直接沿用其选择。

- **`zh-CN`**：
  > 这张照片是侧面角度，要生成俯视全身图需要调用云端图像服务 `<具体服务名称>`，届时会将你提供的参考照片发送到该服务。你同意使用 `<具体服务名称>` 处理这张照片吗？如果希望照片完全留在本机，也可以补拍一张能看清背部和尾巴的俯拍照，我用本机脚本直接抠图。
- **`ja`**：
  > この写真から真上の全身ポーズを作るには、クラウド画像生成サービス `<具体的なサービス名>` に参照写真を送信する必要があります。`<具体的なサービス名>` を使用してよろしいでしょうか？写真を端末の外に出したくない場合は、背中としっぽが見える真上からの写真を1枚いただければ、ローカル処理だけで切り抜けます。
- **`en`**：
  > Generating a top-down full-body view from this angle requires sending your reference photo to the cloud image service `<Specific Service Name>`. Would you like me to proceed with `<Specific Service Name>`? If you prefer to keep your photos strictly on your device, you can share a top-down photo showing the back and tail and I'll cut it out locally.

## 4. 俯视参考生图提示词模板（供图像生成工具使用）

无论用户使用哪种语言对话，调用生图工具时均可根据该工具效果最好的语言填入参考照中真实可见的特征：

- **`zh-CN`**：
  > 参考所附照片中的同一只猫，制作一张写实的垂直俯视全身图。自然趴卧，头向左，臀向右，耳朵和整个背部清楚。尾巴从臀部自然伸向右侧，与身体只在尾根相接，让尾尖完整入画。保留参考照里的体型、左右不对称的斑纹和毛色。用柔和均匀的光，四周留白，背景透明。
- **`ja`**：
  > 添付写真の同じ猫を参考に、真上から見た写実的な全身画像を作成してください。自然に伏せた姿勢で、頭が左、お尻が右、両耳と背中全体がはっきり見えるようにします。しっぽはお尻から右側へ自然に伸び、付け根だけで体とつながり、しっぽの先まで収まるようにしてください。参考写真の体型、左右非対称の模様や毛色を維持し、柔らかく均一な光で、周囲に余白をとり背景は透過（または単色）にしてください。
- **`en`**：
  > Referencing the same cat in the attached photo(s), create a realistic, directly top-down full-body view. The cat is lying naturally with its head on the left and rump on the right, both ears and the entire back clearly visible. The tail extends naturally to the right from the rump, connecting to the body only at the tail base with the tail tip fully in frame. Preserve the body proportions, asymmetric coat markings, and fur colors visible in the reference photo(s). Use soft, even lighting with padding around the cat and a transparent background.

## 5. 交付说明与局部修边反馈引导

这些是完成验收后的交付示例。按本次实际文件、浏览器和已验证的功能填写。刚收到照片时，先说下一步要做什么。

- **`zh-CN`**：
  > 已用你提供的俯拍照生成个人网页 `my-cat.html`，并在浏览器当前原站标签页完成挂载和验收：选猫栏已出现「豆包」，摸背、拨尾和切换其他猫咪都正常（若为参考生图则补充：其中未拍到的后背右侧花纹与尾尖色带为根据参考照做的近似还原）。原站的选猫、体型和声音等控件保持原有日文。关闭临时视图或刷新页面即可回到原站。如果抚摸时发现哪一处边缘还有抓板或地板跟着毛动，直接告诉我具体位置，我帮你放大修掉。
- **`ja`**：
  > お預かりした写真から個人用HTML `my-cat.html` を作成し、ブラウザで表示と動作を確認しました。猫選択バーに「きなこ」が追加され、背中をなでる操作やしっぽの動き、他の猫との切り替えも正常です（※AI生成を使った場合は補足：写真に写っていなかった背中中央の模様は参考写真からの近似表現です）。本家サイトのゲームUIは元の日本語のまま利用できます。一時ビューを閉じるかページを更新すると元の画面に戻ります。もしなでたときに輪郭の一部へ床や爪とぎの背景が残って動いて見える箇所があれば、場所を教えていただければ部分修正します。
- **`en`**：
  > I've built your personal webpage `my-cat.html` from your photo and verified it in the browser: "Mochi" now appears in the cat selector with working back-petting, tail-swishing, and switching back to the original cats (if AI-synthesized, add: the unseen lower-back markings were approximated from your reference photos). The upstream game controls remain in their original Japanese, and you can close the temporary view or refresh the page anytime to exit. If you notice any small patch of floor or scratcher moving along an edge while petting, just tell me which spot and I'll trim it against the original photo.
