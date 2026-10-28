import json
import base64
import requests
import pandas as pd
from PIL import Image
import streamlit as st

st.set_page_config(
    page_title="領収書自動読み取り ＆ 青色申告管理アプリ",
    page_icon="🧾",
    layout="wide"
)

st.title("🧾 領収書自動読み取り ＆ 青色申告管理アプリ")
st.write("複数のレシート写真を同時に選択してアップロードしてください。AIが自動で1枚の画像にまとめて一撃で解析し、やよいの青色申告用CSVを出力します。")

if "receipts_data" not in st.session_state:
    st.session_state.receipts_data = []

# 複数ファイルを同時に選択可能
uploaded_files = st.file_uploader(
    "レシート・領収書の画像を複数選択してください（複数選択可 / JPEG・PNG）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

if uploaded_files:
    st.subheader(f"📁 選択された画像: {len(uploaded_files)}枚")
    
    # 選択された画像をプレビュー表示
    cols = st.columns(min(len(uploaded_files), 4))
    for idx, uploaded_file in enumerate(uploaded_files):
        with cols[idx % len(cols)]:
            image = Image.open(uploaded_file)
            st.image(image, use_container_width=True, caption=f"画像 {idx+1}")
            
    st.markdown("---")
    
    api_key = ""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass
        
    if not api_key:
        st.error("⚠️ Streamlit Secrets に `GEMINI_API_KEY` が設定されていません。")
    else:
        st.success("🔑 APIキーは正常に読み込まれています。")
        if st.button(f"🚀 選択した {len(uploaded_files)}枚を合体して一括AI解析する", type="primary"):
            with st.spinner("画像を綺麗に並べてAIが一括解析しています..."):
                try:
                    # 1. 複数画像を読み込んでリサイズ・統一
                    imgs = []
                    for f in uploaded_files:
                        img = Image.open(f).convert("RGB")
                        target_height = 800
                        aspect_ratio = img.width / img.height
                        target_width = int(target_height * aspect_ratio)
                        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                        imgs.append(img)
                    
                    # 2. 2列のグリッド状に自動合成（コラージュ）
                    cols_count = 2
                    rows_count = (len(imgs) + cols_count - 1) // cols_count
                    
                    max_w = max(im.width for im in imgs)
                    max_h = max(im.height for im in imgs)
                    
                    grid_w = max_w * cols_count
                    grid_h = max_h * rows_count
                    
                    combined_image = Image.new("RGB", (grid_w, grid_h), (255, 255, 255))
                    
                    for idx, im in enumerate(imgs):
                        r = idx // cols_count
                        c = idx % cols_count
                        x = c * max_w + (max_w - im.width) // 2
                        y = r * max_h + (max_h - im.height) // 2
                        combined_image.paste(im, (x, y))
                    
                    # 3. 合成した画像をさらに全体最適化してBase64化
                    combined_image.thumbnail((1600, 1600))
                    import io as py_io
                    buffered = py_io.BytesIO()
                    combined_image.save(buffered, format="JPEG", quality=80)
                    img_bytes = buffered.getvalue()
                    img_base64 = base64.b64encode(img_bytes).decode("utf-8")
                    
                    # 4. Gemini APIへ1回だけリクエスト送信（モデルを gemini-3.8-flash に指定）
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"
                    
                    prompt_text = f"""
                    あなたはプロの経理アシスタント兼AI税理士です。
                    提供された画像には、{len(uploaded_files)}枚のレシートが綺麗に並べて配置されています。
                    画像内にあるすべてのレシートをもれなく認識し、それぞれのデータを以下のJSONフォーマットのルールに従って配列（リスト）形式ですべて抽出してください。
                    
                    【抽出ルール】
                    - date: 日付 (YYYY-MM-DD形式)
                    - vendor: 支払先 (店舗名・会社名)
                    - amount: 合計金額 (数字のみの整数)
                    - account_title: 勘定科目 (「消耗品費」「旅費交通費」「接待交際費」「通信費」「水道光熱費」「地代家賃」「新聞図書費」「車両費」「雑費」のいずれか)
                    - description: 摘要 (購入した品目や内容)
                    
                    必ず以下のJSON配列形式のみを ```json ... ``` の中に出力してください。
                    [
                      {{
                        "date": "YYYY-MM-DD",
                        "vendor": "支払先名称",
                        "amount": 1000,
                        "account_title": "消耗品費",
                        "description": "購入品目"
                      }}
                    ]
                    """
                    
                    payload = {
                        "contents": [
                            {
                                "parts": [
                                    {"text": prompt_text},
                                    {
                                        "inline_data": {
                                            "mime_type": "image/jpeg",
                                            "data": img_base64
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                    
                    headers = {"Content-Type": "application/json"}
                    response = requests.post(url, json=payload, headers=headers)
                    result_json = response.json()
                    
                    if "error" in result_json:
                        err_msg = result_json["error"].get("message", "不明なエラー")
                        st.error(f"❌ APIエラー: {err_msg}")
                    elif "candidates" in result_json:
                        response_text = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                        
                        if "```json" in response_text:
                            response_text = response_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in response_text:
                            response_text = response_text.split("```")[1].split("```")[0].strip()
                            
                        new_items = json.loads(response_text)
                        
                        if isinstance(new_items, list):
                            st.session_state.receipts_data.extend(new_items)
                            st.success(f"✨ 処理完了！ {len(new_items)}件のレシートデータを一括追加しました！")
                        else:
                            st.session_state.receipts_data.append(new_items)
                            st.success("✨ レシートデータを追加しました！")
                        st.rerun()
                    else:
                        st.error("❌ 応答形式が予期せぬものです。")
                        
                except Exception as e:
                    st.error(f"❌ エラーが発生しました: {str(e)}")

st.markdown("---")
st.subheader("📊 登録済み経費データ一覧 & やよい連携")

if len(st.session_state.receipts_data) > 0:
    df = pd.DataFrame(st.session_state.receipts_data)
    st.dataframe(df, use_container_width=True)
    
    csv_data = []
    for item in st.session_state.receipts_data:
        csv_data.append({
            "取引日": item.get("date", ""),
            "借方勘定科目": item.get("account_title", "消耗品費"),
            "借方金額": item.get("amount", 0),
            "貸方勘定科目": "現金",
            "貸方金額": item.get("amount", 0),
            "摘要": f"{item.get('vendor', '')} - {item.get('description', '')}"
        })
    
    df_yayoi = pd.DataFrame(csv_data)
    csv_string = df_yayoi.to_csv(index=False)
    csv_bytes = csv_string.encode("shift_jis", errors="ignore")
    
    col_dl, col_cl = st.columns([1, 1])
    with col_dl:
        st.download_button(
            label="📥 やよいの青色申告用CSVをダウンロード",
            data=csv_bytes,
            file_name="yayoi_keikhi.csv",
            mime="text/csv",
            type="primary"
        )
    with col_cl:
        if st.button("🗑️ データをすべてクリア"):
            st.session_state.receipts_data = []
            st.rerun()
else:
    st.info("💡 まだデータが登録されていません。上のアップロードボタンから複数枚の写真を選択してください。")
